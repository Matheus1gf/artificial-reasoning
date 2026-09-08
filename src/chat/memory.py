"""Transactional local memory. Generated answers never become factual evidence."""
import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from .domain import claim_text


def now():
    return datetime.now(timezone.utc).isoformat()


class Memory:
    def __init__(self, path):
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(str(path), check_same_thread=False, timeout=30)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
                role TEXT NOT NULL CHECK(role IN ('user','assistant')), content TEXT NOT NULL,
                created_at TEXT NOT NULL, metadata TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS turns (
                request_id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL REFERENCES conversations(id),
                user_content TEXT NOT NULL, result TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY, subject TEXT NOT NULL, predicate TEXT NOT NULL,
                object TEXT NOT NULL, polarity INTEGER NOT NULL, scope TEXT NOT NULL,
                status TEXT NOT NULL, origin TEXT NOT NULL, method TEXT NOT NULL DEFAULT '',
                explanation TEXT NOT NULL DEFAULT '', validation TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                UNIQUE(subject,predicate,object,polarity,scope));
            CREATE TABLE IF NOT EXISTS sources (
                claim_id INTEGER NOT NULL REFERENCES claims(id), message_id INTEGER NOT NULL REFERENCES messages(id),
                quote TEXT NOT NULL, PRIMARY KEY(claim_id,message_id));
            CREATE TABLE IF NOT EXISTS dependencies (
                conclusion_id INTEGER NOT NULL REFERENCES claims(id), premise_id INTEGER NOT NULL REFERENCES claims(id),
                PRIMARY KEY(conclusion_id,premise_id), CHECK(conclusion_id != premise_id));
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY, kind TEXT NOT NULL, claim_id INTEGER REFERENCES claims(id),
                detail TEXT NOT NULL, created_at TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS message_conversation ON messages(conversation_id,id);
            CREATE INDEX IF NOT EXISTS dependency_premise ON dependencies(premise_id);
        """)

    @contextmanager
    def transaction(self):
        with self.lock:
            with self.db:
                yield self

    def close(self):
        self.db.close()

    def conversation(self, conversation_id):
        row = self.db.execute("SELECT * FROM conversations WHERE id=?", (conversation_id,)).fetchone()
        if row is None:
            raise ValueError("Conversa não encontrada.")
        return dict(row)

    def create_conversation(self, title="Nova conversa"):
        with self.transaction():
            cid = uuid.uuid4().hex
            self.db.execute("INSERT INTO conversations VALUES (?,?,?)", (cid, title[:80], now()))
            return self.conversation(cid)

    def conversations(self):
        return [dict(r) for r in self.db.execute("SELECT * FROM conversations ORDER BY created_at DESC")]

    def messages(self, cid):
        self.conversation(cid)
        rows = self.db.execute("SELECT * FROM messages WHERE conversation_id=? ORDER BY id", (cid,))
        return [dict(r, metadata=json.loads(r["metadata"])) for r in rows]

    def add_message(self, cid, role, content, metadata=None):
        cur = self.db.execute("INSERT INTO messages(conversation_id,role,content,created_at,metadata) VALUES(?,?,?,?,?)",
                              (cid, role, content, now(), json.dumps(metadata or {}, ensure_ascii=False)))
        if role == "user":
            self.db.execute("UPDATE conversations SET title=? WHERE id=? AND title='Nova conversa'", (content[:60], cid))
        return cur.lastrowid

    def cached_turn(self, request_id, cid, text):
        row = self.db.execute("SELECT * FROM turns WHERE request_id=?", (request_id,)).fetchone()
        if row:
            if row["conversation_id"] != cid or row["user_content"] != text:
                raise ValueError("Identificador de envio já utilizado para outra mensagem.")
            return json.loads(row["result"])

    def save_turn(self, request_id, cid, text, result):
        self.db.execute("INSERT INTO turns VALUES(?,?,?,?)", (request_id, cid, text, json.dumps(result, ensure_ascii=False)))

    def event(self, kind, claim_id, detail):
        self.db.execute("INSERT INTO events(kind,claim_id,detail,created_at) VALUES(?,?,?,?)", (kind, claim_id, detail, now()))

    def claims(self, include_inactive=False):
        sql = "SELECT * FROM claims" + ("" if include_inactive else " WHERE status != 'retracted'") + " ORDER BY id DESC"
        return [self._enrich(dict(r)) for r in self.db.execute(sql)]

    def claim(self, claim_id):
        row = self.db.execute("SELECT * FROM claims WHERE id=?", (claim_id,)).fetchone()
        if row is None:
            raise ValueError("Conhecimento não encontrado.")
        return self._enrich(dict(row))

    def _enrich(self, row):
        row["polarity"] = bool(row["polarity"])
        row["text"] = claim_text(row)
        row["sources"] = [dict(r) for r in self.db.execute(
            "SELECT s.message_id,s.quote,m.conversation_id FROM sources s JOIN messages m ON s.message_id=m.id WHERE s.claim_id=?", (row["id"],))]
        row["premises"] = [r[0] for r in self.db.execute("SELECT premise_id FROM dependencies WHERE conclusion_id=?", (row["id"],))]
        return row

    def invalidate_dependents(self, premise_id):
        pending, invalidated = [premise_id], []
        visited = set(pending)
        while pending:
            pid = pending.pop()
            rows = list(self.db.execute("SELECT c.id,c.origin,c.status FROM dependencies d JOIN claims c ON c.id=d.conclusion_id WHERE d.premise_id=?", (pid,)))
            for row in rows:
                if row["id"] in visited or row["origin"] == "user":
                    continue
                visited.add(row["id"])
                if row["status"] != "retracted":
                    self.db.execute("UPDATE claims SET status='retracted',updated_at=? WHERE id=?", (now(), row["id"]))
                    self.event("dependency_invalidated", row["id"], f"Premissa M{premise_id} alterada.")
                    invalidated.append(row["id"])
                pending.append(row["id"])
        return invalidated

    def retract(self, claim_id, reason="Retirado pelo usuário"):
        self.claim(claim_id)
        self.db.execute("UPDATE claims SET status='retracted',updated_at=? WHERE id=?", (now(), claim_id))
        self.event("retracted", claim_id, reason)
        return self.invalidate_dependents(claim_id)

    def learn(self, assertion, message_id, correction=False):
        a = assertion.clean()
        key = (a.subject, a.predicate, a.object, int(a.polarity), a.scope)
        old = self.db.execute("SELECT * FROM claims WHERE subject=? AND predicate=? AND object=? AND polarity=? AND scope=?", key).fetchone()
        corrected = []
        if old and a.tentative and not correction and old["status"] in {"asserted", "deduced", "disputed"}:
            # An uncertain repetition is not independent evidence for a conclusion.
            self.event("tentative_reference", old["id"], f"Menção incerta na mensagem {message_id}; origem e dependências preservadas.")
            return old["id"], [], []
        if correction:
            # Explicit correction only: a predicate may normally have multiple objects.
            for row in list(self.db.execute("SELECT id FROM claims WHERE subject=? AND predicate=? AND scope=? AND status!='retracted'", (a.subject, a.predicate, a.scope))):
                if old is None or row["id"] != old["id"]:
                    corrected.extend([row["id"]] + self.retract(row["id"], "Correção explícita em uma mensagem."))
        status = "hypothesis" if a.tentative else "asserted"
        if old:
            cid = old["id"]
            if status == "hypothesis" and old["status"] in {"asserted", "deduced"}:
                corrected.extend(self.invalidate_dependents(cid))
            # Merely repeating an assertion does not resolve an existing conflict.
            if old["status"] == "disputed" and not correction:
                status = "disputed"
            self.db.execute("UPDATE claims SET status=?,origin='user',method='',explanation='',validation='',updated_at=? WHERE id=?", (status, now(), cid))
            self.db.execute("DELETE FROM dependencies WHERE conclusion_id=?", (cid,))
        else:
            cur = self.db.execute("INSERT INTO claims(subject,predicate,object,polarity,scope,status,origin,created_at,updated_at) VALUES(?,?,?,?,?,?,'user',?,?)", (*key, status, now(), now()))
            cid = cur.lastrowid
        self.db.execute("INSERT OR IGNORE INTO sources VALUES(?,?,?)", (cid, message_id, a.quote))
        self.event("corrected" if correction else "learned", cid, "Hipótese informada" if a.tentative else "Afirmação do usuário; sem verificação externa.")
        conflicts = []
        if not a.tentative:
            for row in list(self.db.execute("SELECT id FROM claims WHERE subject=? AND predicate=? AND object=? AND polarity=? AND scope=? AND status='hypothesis'", (a.subject, a.predicate, a.object, int(not a.polarity), a.scope))):
                corrected.extend([row["id"]] + self.retract(row["id"], "Hipótese contrariada por nova afirmação do usuário."))
            opposite = list(self.db.execute("SELECT id FROM claims WHERE subject=? AND predicate=? AND object=? AND polarity=? AND scope=? AND status IN ('asserted','deduced','disputed')", (a.subject, a.predicate, a.object, int(not a.polarity), a.scope)))
            if opposite:
                conflicts = [cid] + [r["id"] for r in opposite]
                for conflict_id in conflicts:
                    self.db.execute("UPDATE claims SET status='disputed',updated_at=? WHERE id=?", (now(), conflict_id))
                    corrected.extend(self.invalidate_dependents(conflict_id))
                    self.event("conflict", conflict_id, "Há afirmações incompatíveis; preciso de uma correção.")
        return cid, corrected, conflicts

    def propose(self, proposal):
        key = (proposal.subject, proposal.predicate, proposal.object, int(proposal.polarity), proposal.scope)
        old = self.db.execute("SELECT * FROM claims WHERE subject=? AND predicate=? AND object=? AND polarity=? AND scope=?", key).fetchone()
        if old and old["status"] != "retracted" and not (old["status"] == "hypothesis" and proposal.status == "deduced"):
            return self.claim(old["id"]), False
        if old and old["status"] == "retracted" and old["origin"] == "user":
            return self.claim(old["id"]), False  # Do not resurrect a user's retracted assertion.
        if old and old["status"] == "retracted":
            last_event = self.db.execute("SELECT kind FROM events WHERE claim_id=? ORDER BY id DESC LIMIT 1", (old["id"],)).fetchone()
            if last_event and last_event["kind"] == "retracted":
                return self.claim(old["id"]), False
        opposite = list(self.db.execute("SELECT id FROM claims WHERE subject=? AND predicate=? AND object=? AND polarity=? AND scope=? AND status IN ('asserted','deduced','disputed')", (proposal.subject, proposal.predicate, proposal.object, int(not proposal.polarity), proposal.scope)))
        if opposite and proposal.status == "hypothesis":
            return self.claim(opposite[0]["id"]), False
        if old:
            cid = old["id"]
            self.db.execute("UPDATE claims SET status=?,origin='reasoner',method=?,explanation=?,validation=?,updated_at=? WHERE id=?", (proposal.status, proposal.method, proposal.explanation, proposal.validation, now(), cid))
            self.db.execute("DELETE FROM dependencies WHERE conclusion_id=?", (cid,))
        else:
            cur = self.db.execute("INSERT INTO claims(subject,predicate,object,polarity,scope,status,origin,method,explanation,validation,created_at,updated_at) VALUES(?,?,?,?,?,?,'reasoner',?,?,?,?,?)", (*key, proposal.status, proposal.method, proposal.explanation, proposal.validation, now(), now()))
            cid = cur.lastrowid
        for pid in set(proposal.premises):
            if pid != cid:
                self.db.execute("INSERT INTO dependencies VALUES(?,?)", (cid, pid))
        self.event("inferred", cid, proposal.method)
        if opposite and proposal.status == "deduced":
            for conflict_id in [cid] + [r["id"] for r in opposite]:
                self.db.execute("UPDATE claims SET status='disputed',updated_at=? WHERE id=?", (now(), conflict_id))
                self.invalidate_dependents(conflict_id)
                self.event("conflict", conflict_id, "Uma regra geral conflita com uma afirmação específica.")
        return self.claim(cid), True

    def stats(self):
        counts = {r[0]: r[1] for r in self.db.execute("SELECT status,COUNT(*) FROM claims GROUP BY status")}
        return {"messages": self.db.execute("SELECT COUNT(*) FROM messages WHERE role='user'").fetchone()[0],
                "conversations": self.db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0],
                "claims": counts, "assertions": counts.get("asserted", 0),
                "hypotheses": counts.get("hypothesis", 0), "deductions": counts.get("deduced", 0),
                "conflicts": counts.get("disputed", 0)}
