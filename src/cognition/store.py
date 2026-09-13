"""Scoped, versioned experience memory. Statements and generated text are not truth.

This sidecar never migrates the chat's legacy SQLite tables. Migration of this
store is backed up with SQLite's online backup API before schema changes.
"""
import hashlib
import json
import math
import sqlite3
import threading
import uuid
from urllib.parse import quote
from ..chat.domain import predicate as canonical_predicate
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


SCHEMA_VERSION = 2
KINDS = {"episode", "entity", "attribute", "relation", "event", "state", "rule",
         "equation", "action", "goal", "model", "experiment", "procedure",
         "preference", "question", "correction", "assertion", "hypothesis", "test_result"}
SCOPES = {"conversation", "user", "laboratory"}
STATUSES = {"asserted", "verified", "hypothesis", "disputed", "retracted"}
EVIDENCE = {"user", "observation", "experiment", "deduction", "generated", "imported"}
REQUIRED = {"entity": {"name"}, "attribute": {"entity", "name", "value"},
            "relation": {"predicate", "arguments"}, "event": {"event", "time"},
            "state": {"values"}, "rule": {"conditions", "effects"},
            "equation": {"expression", "variables"}, "action": {"preconditions", "effects"},
            "goal": {"target"}}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def text_id(value, name, maximum=256):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(name + " must be a nonempty bounded string")
    return value


def encode(value):
    try:
        result = json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError("Only finite JSON data is accepted") from exc
    if len(result.encode("utf-8")) > 131072:
        raise ValueError("Record exceeds 128 KiB")
    return result


def uncertainty(value=None):
    result = {"extraction": None, "source": None, "event": None, "derivation": "unchecked"}
    if value is not None:
        if not isinstance(value, dict) or not set(value) <= set(result):
            raise ValueError("Uncertainty dimensions must be separate")
        result.update(value)
    for key in ("extraction", "source", "event"):
        number = result[key]
        if number is not None and (type(number) not in (float, int) or not math.isfinite(number) or not 0 <= number <= 1):
            raise ValueError("Probability must be finite and in [0, 1]")
    if result["derivation"] not in ("unchecked", "conditional", "verified", "invalid"):
        raise ValueError("Unknown derivation status")
    return result


def same_bound_value(left, right):
    """Numeric equality permits 1 == 1.0, but never conflates booleans."""
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    if isinstance(left, dict):
        return (isinstance(right, dict) and left.keys() == right.keys()
                and all(same_bound_value(left[k], right[k]) for k in left))
    if isinstance(left, list):
        return (isinstance(right, list) and len(left) == len(right)
                and all(same_bound_value(a, b) for a, b in zip(left, right)))
    return left == right


def structural_match(pattern, value, bindings=None, field=None):
    """Match typed goals/relations, with shared variables and declared verb aliases.

    This is semantic normalization of explicit predicates, not learned embeddings
    or a guarantee that a matching action is applicable in the current state.
    """
    bindings = {} if bindings is None else bindings
    if isinstance(pattern, str) and pattern.startswith("?"):
        if pattern in bindings:
            return same_bound_value(bindings[pattern], value)
        bindings[pattern] = value
        return True
    if isinstance(pattern, dict):
        return isinstance(value, dict) and all(k in value and structural_match(v, value[k], bindings, k)
                                                for k, v in pattern.items())
    if isinstance(pattern, list):
        return (isinstance(value, list) and len(pattern) == len(value)
                and all(structural_match(p, v, bindings) for p, v in zip(pattern, value)))
    if field in {"predicate", "verb"} and isinstance(pattern, str) and isinstance(value, str):
        return canonical_predicate(pattern) == canonical_predicate(value)
    if isinstance(pattern, bool) != isinstance(value, bool):
        return False
    return pattern == value


class ExperienceStore:
    def __init__(self, path):
        self.path = str(path)
        self.lock = threading.RLock()
        self.closed = False
        if self.path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=10, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        tables = {r[0] for r in self.db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if tables and "store_meta" not in tables:
            self.db.close()
            raise ValueError("Not a cognition sidecar database; chat data must not be migrated here")
        version = 0
        if "store_meta" in tables:
            row = self.db.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
            version = int(row[0]) if row else -1
            if version not in (1, SCHEMA_VERSION):
                self.db.close()
                raise ValueError("Unsupported cognition schema version")
        self.migration_backup = None
        if version and version < SCHEMA_VERSION and self.path != ":memory:":
            target = Path(self.path).with_name(Path(self.path).name + ".migration-" + uuid.uuid4().hex + ".backup")
            self.backup(target)
            self.migration_backup = str(target)
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        with self.db:
            if version == 0:
                self.db.executescript("""
                    CREATE TABLE store_meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
                    CREATE TABLE records(id TEXT PRIMARY KEY, conversation_id TEXT NOT NULL,
                      owner_id TEXT NOT NULL, kind TEXT NOT NULL, scope TEXT NOT NULL,
                      status TEXT NOT NULL, evidence TEXT NOT NULL, payload TEXT NOT NULL,
                      source_ids TEXT NOT NULL, created_at TEXT NOT NULL);
                """)
            if version < 2:
                for field in ("uncertainties TEXT NOT NULL DEFAULT '{}'", "logical_key TEXT",
                              "valid_time TEXT", "version INTEGER NOT NULL DEFAULT 1", "parent_id TEXT",
                              "updated_at TEXT NOT NULL DEFAULT ''", "dedupe_key TEXT"):
                    self.db.execute("ALTER TABLE records ADD COLUMN " + field)
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS dependencies(premise_id TEXT NOT NULL,
                    conclusion_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
                    PRIMARY KEY(premise_id, conclusion_id));
                CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY, kind TEXT NOT NULL,
                    record_id TEXT, detail TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS models(id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    owner_id TEXT NOT NULL, artifact TEXT NOT NULL, training_ids TEXT NOT NULL,
                    metrics TEXT NOT NULL, active INTEGER NOT NULL, invalidated INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS record_scope ON records(owner_id,conversation_id,scope,status);
                CREATE INDEX IF NOT EXISTS dependent_records ON dependencies(premise_id);
                CREATE UNIQUE INDEX IF NOT EXISTS record_dedupe ON records(owner_id,conversation_id,dedupe_key);
            """)
            if version < 2:
                for row in self.db.execute("SELECT id,source_ids FROM records").fetchall():
                    for premise in json.loads(row["source_ids"]):
                        self.db.execute("INSERT OR IGNORE INTO dependencies VALUES(?,?)", (premise, row["id"]))
            self.db.execute("INSERT OR REPLACE INTO store_meta VALUES('schema_version',?)", (str(SCHEMA_VERSION),))

    @contextmanager
    def transaction(self):
        with self.lock:
            if self.closed:
                raise RuntimeError("Store is closed")
            nested = self.db.in_transaction
            savepoint = "tx_" + uuid.uuid4().hex
            self.db.execute("SAVEPOINT " + savepoint if nested else "BEGIN")
            try:
                yield
            except BaseException:
                if nested:
                    self.db.execute("ROLLBACK TO " + savepoint)
                    self.db.execute("RELEASE " + savepoint)
                else:
                    self.db.rollback()
                raise
            else:
                if nested:
                    self.db.execute("RELEASE " + savepoint)
                else:
                    self.db.commit()

    def close(self):
        with self.lock:
            if not self.closed:
                self.db.close()
                self.closed = True

    def _event(self, kind, rid, detail):
        self.db.execute("INSERT INTO events(kind,record_id,detail,created_at) VALUES(?,?,?,?)",
                        (kind, rid, encode(detail), utcnow()))

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        item = dict(row)
        for name in ("payload", "source_ids", "uncertainties"):
            item[name] = json.loads(item[name])
        return item

    def get(self, record_id, owner_id="local", conversation_id=None):
        with self.lock:
            item = self._decode(self.db.execute("SELECT * FROM records WHERE id=?", (record_id,)).fetchone())
            if item is None or (item["owner_id"] != owner_id and item["scope"] != "laboratory"):
                raise ValueError("Record not found in this scope")
            if conversation_id is not None and item["scope"] == "conversation" and item["conversation_id"] != conversation_id:
                raise ValueError("Record not found in this conversation")
            return item

    def record(self, conversation_id, kind, payload, source_ids, scope="conversation", owner_id="local",
               status="asserted", evidence="user", uncertainties=None, logical_key=None, valid_time=None,
               dedupe_key=None):
        text_id(conversation_id, "conversation_id")
        text_id(owner_id, "owner_id")
        if not isinstance(kind, str) or kind not in KINDS:
            raise ValueError("Unknown knowledge kind")
        if (not isinstance(scope, str) or scope not in SCOPES or not isinstance(status, str)
                or status not in STATUSES or not isinstance(evidence, str) or evidence not in EVIDENCE):
            raise ValueError("Unknown scope/status/evidence")
        if not isinstance(payload, dict) or not REQUIRED.get(kind, set()) <= set(payload):
            raise ValueError("Typed record lacks required fields")
        for key in {"entity": ["name"], "attribute": ["entity", "name"], "relation": ["predicate"]}.get(kind, []):
            text_id(payload[key], key)
        for key in {"relation": ["arguments"], "rule": ["conditions", "effects"],
                    "equation": ["variables"], "action": ["preconditions", "effects"]}.get(kind, []):
            if not isinstance(payload[key], list) or len(payload[key]) > 128:
                raise ValueError(key + " must be a bounded list")
        if kind == "state" and not isinstance(payload["values"], dict):
            raise ValueError("State values must be a mapping")
        payload_json = encode(payload)
        if not isinstance(source_ids, list) or len(source_ids) > 128:
            raise ValueError("source_ids must be a bounded list")
        sources = list(dict.fromkeys(text_id(s, "source_id") for s in source_ids))
        for value, name in ((logical_key, "logical_key"), (valid_time, "valid_time"), (dedupe_key, "dedupe_key")):
            if value is not None:
                text_id(value, name)
        u = uncertainty(uncertainties)
        # Verification is a controlled observation/test role, not a high confidence score.
        if status == "verified" and evidence not in {"observation", "experiment", "deduction"}:
            raise ValueError("A user assertion or generated text cannot be automatically verified")
        if status == "verified" and not sources:
            raise ValueError("Verified observations require provenance")
        if evidence == "generated" and status not in {"hypothesis", "retracted", "disputed"}:
            raise ValueError("Generated content remains a hypothesis")
        with self.transaction():
            if dedupe_key:
                row = self.db.execute("SELECT * FROM records WHERE owner_id=? AND conversation_id=? AND dedupe_key=?",
                                      (owner_id, conversation_id, dedupe_key)).fetchone()
                if row:
                    if row["payload"] != payload_json or row["kind"] != kind:
                        raise ValueError("Idempotency key reused with different experience")
                    return row["id"]
            for sid in sources:
                if sid.startswith("E-"):
                    premise = self.get(sid, owner_id, conversation_id)
                    if premise["status"] in {"retracted", "disputed"}:
                        raise ValueError("Inactive premise cannot support new knowledge")
                    if premise["status"] == "hypothesis" and status == "verified":
                        raise ValueError("A hypothesis cannot certify a conclusion")
            rid, stamp = "E-" + uuid.uuid4().hex, utcnow()
            self.db.execute("""INSERT INTO records VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (rid, conversation_id, owner_id, kind, scope, status, evidence, payload_json,
                             encode(sources), stamp, encode(u), logical_key, valid_time, 1, None, stamp, dedupe_key))
            for sid in sources:
                self.db.execute("INSERT INTO dependencies VALUES(?,?)", (sid, rid))
            if logical_key and status in {"asserted", "verified"}:
                conflicts = self.db.execute("""SELECT id FROM records WHERE logical_key=? AND owner_id=?
                    AND scope=? AND (scope!='conversation' OR conversation_id=?) AND valid_time IS ?
                    AND id!=? AND status IN ('asserted','verified','disputed') AND payload!=?""",
                    (logical_key, owner_id, scope, conversation_id, valid_time, rid, payload_json)).fetchall()
                if conflicts:
                    self.db.execute("UPDATE records SET status='disputed' WHERE id=?", (rid,))
                    for other in conflicts:
                        self.db.execute("UPDATE records SET status='disputed' WHERE id=?", (other["id"],))
                        self._invalidate([other["id"]], "conflicting assertion", include_roots=False)
            self._event("recorded", rid, {"kind": kind, "evidence": evidence})
            return rid

    def retrieve(self, conversation_id, query, limit=20, owner_id="local"):
        if not isinstance(query, dict) or type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Query must be structured; limit in [1,1000]")
        if not isinstance(query.get("where", {}), dict):
            raise ValueError("where must contain structured field constraints")
        with self.lock:
            rows = self.db.execute("""SELECT * FROM records WHERE status NOT IN ('retracted','disputed')
                AND (scope='laboratory' OR (owner_id=? AND (scope='user' OR conversation_id=?)))
                ORDER BY created_at DESC,id DESC""", (owner_id, conversation_id)).fetchall()
            selected = []
            for row in rows:
                item = self._decode(row)
                if query.get("kind") and item["kind"] != query["kind"]:
                    continue
                if query.get("logical_key") and item["logical_key"] != query["logical_key"]:
                    continue
                if query.get("valid_time") is not None and item["valid_time"] != query["valid_time"]:
                    continue
                if not structural_match(query.get("where", {}), item["payload"]):
                    continue
                if "goal" in query:
                    options = item["payload"].get("effects", [])
                    if not isinstance(options, list):
                        options = []
                    options = options + [item["payload"].get("target", {}), item["payload"]]
                    if not any(structural_match(query["goal"], candidate) for candidate in options):
                        continue
                # Structure matching, with a lexical aid whose score is not truth.
                terms = str(query.get("text", "")).casefold().split()
                corpus = encode(item["payload"]).casefold()
                if terms and not any(term in corpus for term in terms):
                    continue
                item["retrieval_basis"] = "canonical_predicates_and_structural_goals_with_lexical_aid"
                selected.append(item)
                if len(selected) >= limit:
                    break
            return selected

    def import_claims(self, claims, owner_id="local"):
        """Idempotent initial adapter for the legacy personal-laboratory triples.

        The caller supplies a read-only snapshot; original chat tables/history
        stay intact. Later source corrections use invalidate_sources(M#).
        """
        if not isinstance(claims, list) or len(claims) > 10000:
            raise ValueError("Use bounded claim snapshots")
        imported = []
        with self.transaction():
            for claim in claims:
                if not isinstance(claim, dict) or not {"id", "subject", "predicate", "object"} <= claim.keys():
                    raise ValueError("Legacy claims require id, subject, predicate and object")
                status = {"deduced": "asserted", "asserted": "asserted", "hypothesis": "hypothesis",
                          "disputed": "disputed", "retracted": "retracted"}.get(claim.get("status"))
                if status is None:
                    raise ValueError("Unknown legacy claim status")
                reasoned = claim.get("origin") == "reasoner"
                deduced = claim.get("status") == "deduced" or (reasoned and claim.get("method") == "deduction")
                evidence = "deduction" if deduced else "generated" if reasoned else "user"
                source = "M" + str(claim["id"])
                args = {"predicate": claim["predicate"], "arguments": [claim["subject"], claim["object"]],
                        "polarity": claim.get("polarity", True), "quantifier": claim.get("scope", "instance"),
                        "legacy_id": claim["id"]}
                rid = self.record("legacy-import", "relation", args,
                                  list(dict.fromkeys([source] + ["M" + str(i) for i in claim.get("premises", [])])),
                                  scope="user", owner_id=owner_id, status=status, evidence=evidence,
                                  uncertainties={"derivation": "conditional" if evidence == "deduction" else "unchecked"},
                                  dedupe_key="legacy:" + source)
                imported.append(rid)
        return imported

    def _invalidate(self, roots, reason, include_roots=True):
        queue = list(roots)
        affected, visited = [], set()
        while queue:
            rid = queue.pop()
            if rid in visited:
                continue
            visited.add(rid)
            if include_roots or rid not in roots:
                row = self.db.execute("SELECT id,status FROM records WHERE id=?", (rid,)).fetchone()
                if row and row["status"] != "retracted":
                    self.db.execute("UPDATE records SET status='retracted',updated_at=? WHERE id=?", (utcnow(), rid))
                    affected.append(rid)
                    self._event("retracted", rid, {"reason": reason})
            queue.extend(r[0] for r in self.db.execute("SELECT conclusion_id FROM dependencies WHERE premise_id=?", (rid,)))
        for model in self.db.execute("SELECT id,training_ids,metrics FROM models WHERE invalidated=0").fetchall():
            provenance = set(json.loads(model["training_ids"])) | {json.loads(model["metrics"])["validation_id"]}
            if provenance & visited:
                self.db.execute("UPDATE models SET active=0,invalidated=1 WHERE id=?", (model["id"],))
        return affected

    def retract(self, record_id, reason="withdrawn", owner_id="local"):
        with self.transaction():
            record = self.get(record_id, owner_id)
            if record["owner_id"] != owner_id:
                raise ValueError("Only the owner may withdraw a shared record")
            return self._invalidate([record_id], text_id(reason, "reason", 2000))

    def invalidate_sources(self, source_ids, reason="upstream premise withdrawn"):
        with self.transaction():
            return self._invalidate(source_ids, reason, include_roots=False)

    def revise(self, record_id, payload, owner_id="local", **changes):
        with self.transaction():
            old = self.get(record_id, owner_id)
            if old["owner_id"] != owner_id:
                raise ValueError("Only the owner may revise knowledge")
            self._invalidate([record_id], "superseded by correction")
            args = {k: old[k] for k in ("conversation_id", "kind", "source_ids", "scope", "owner_id", "evidence", "uncertainties", "logical_key", "valid_time")}
            args.update(changes)
            args["status"] = changes.get("status", "asserted")
            new = self.record(payload=payload, **args)
            self.db.execute("UPDATE records SET parent_id=?,version=? WHERE id=?", (record_id, old["version"] + 1, new))
            self._event("revised", new, {"previous": record_id})
            return new

    def consolidate(self, conversation_id, policy, owner_id="local"):
        """Select validated experiences. This does not silently train any model."""
        if not isinstance(policy, dict) or set(policy) - {"kinds", "limit", "training_consent"}:
            raise ValueError("Unknown consolidation policy")
        kinds = policy.get("kinds", ["experiment", "test_result", "model", "procedure"])
        if not isinstance(kinds, list) or not all(k in KINDS for k in kinds):
            raise ValueError("Unknown consolidation kinds")
        items = self.retrieve(conversation_id, {}, policy.get("limit", 100), owner_id)
        eligible, rejected = [], []
        for item in items:
            allowed = (item["kind"] in kinds and item["status"] == "verified"
                       and item["evidence"] in {"experiment", "observation"}
                       and bool(item["source_ids"]) and policy.get("training_consent") is True)
            (eligible if allowed else rejected).append(item["id"])
        return {"schema_version": 1, "eligible_ids": eligible, "rejected_ids": rejected,
                "weights_updated": False, "policy": json.loads(encode(policy))}

    def register_model(self, name, artifact, training_ids, metrics, owner_id="local", activate=False):
        text_id(name, "model name")
        if not isinstance(training_ids, list) or not training_ids:
            raise ValueError("Training provenance is required")
        if not isinstance(metrics, dict) or not {"passed", "validation_id", "retention_passed"} <= metrics.keys():
            raise ValueError("Independent validation and retention results required")
        text_id(metrics["validation_id"], "validation_id")
        if any(type(metrics[k]) is not bool for k in ("passed", "retention_passed")):
            raise ValueError("Validation decisions must be booleans")
        encoded_artifact, encoded_metrics = encode(artifact), encode(metrics)
        if activate and not (metrics["passed"] is True and metrics["retention_passed"] is True):
            raise ValueError("Failed candidate cannot be activated")
        with self.transaction():
            validation = self.get(metrics["validation_id"], owner_id)
            if (validation["id"] in training_ids or validation["kind"] not in {"experiment", "test_result"}
                    or validation["status"] != "verified" or validation["evidence"] != "experiment"
                    or not validation["source_ids"]):
                raise ValueError("Validation must be a separate verified experiment")
            measured = validation["payload"].get("metrics", {})
            if not isinstance(measured, dict) or any(measured.get(k) is not metrics[k] for k in ("passed", "retention_passed")):
                raise ValueError("Metrics must agree with the recorded independent validation")
            validation_samples = validation["payload"].get("sample_ids", validation["source_ids"])
            if not isinstance(validation_samples, list) or not validation_samples or not all(isinstance(s, str) for s in validation_samples):
                raise ValueError("Validation requires sample provenance")
            training_samples = set()
            for rid in training_ids:
                record = self.get(rid, owner_id)
                if record["status"] != "verified" or record["evidence"] not in {"experiment", "observation"} or not record["source_ids"]:
                    raise ValueError("Training requires validated observations or experiments")
                samples = record["payload"].get("sample_ids", record["source_ids"])
                if not isinstance(samples, list) or not samples or not all(isinstance(s, str) for s in samples):
                    raise ValueError("Training requires sample provenance")
                training_samples.update(samples)
            if training_samples & set(validation_samples):
                raise ValueError("Training and validation samples overlap")
            mid = "V-" + uuid.uuid4().hex
            if activate:
                self.db.execute("UPDATE models SET active=0 WHERE name=? AND owner_id=?", (name, owner_id))
            self.db.execute("INSERT INTO models VALUES(?,?,?,?,?,?,?,?,?)", (mid, name, owner_id,
                            encoded_artifact, encode(list(dict.fromkeys(training_ids))),
                            encoded_metrics, int(activate), 0, utcnow()))
            return mid

    def model(self, name, owner_id="local"):
        with self.lock:
            row = self.db.execute("SELECT * FROM models WHERE name=? AND owner_id=? AND active=1 AND invalidated=0",
                                  (name, owner_id)).fetchone()
            if not row:
                return None
            result = dict(row)
            for key in ("artifact", "training_ids", "metrics"):
                result[key] = json.loads(result[key])
            return result

    def rollback_model(self, version_id, owner_id="local"):
        with self.transaction():
            row = self.db.execute("SELECT * FROM models WHERE id=? AND owner_id=?", (version_id, owner_id)).fetchone()
            if row is None or row["invalidated"]:
                raise ValueError("Model unavailable or training provenance withdrawn; retrain first")
            metrics = json.loads(row["metrics"])
            if not (metrics["passed"] is True and metrics["retention_passed"] is True):
                raise ValueError("Version did not pass its validation")
            self.db.execute("UPDATE models SET active=0 WHERE name=? AND owner_id=?", (row["name"], owner_id))
            self.db.execute("UPDATE models SET active=1 WHERE id=?", (version_id,))

    def backup(self, target):
        target = Path(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb"):
            pass
        try:
            with self.lock:
                destination = sqlite3.connect(str(target))
                try:
                    self.db.backup(destination)
                    if destination.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                        raise RuntimeError("Backup integrity check failed")
                finally:
                    destination.close()
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return {"path": str(target), "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    @classmethod
    def restore(cls, backup, destination):
        destination = Path(destination)
        if destination.exists():
            raise ValueError("Restore requires a new destination; existing data is preserved")
        source = sqlite3.connect("file:" + quote(str(Path(backup).resolve())) + "?mode=ro", uri=True)
        try:
            if source.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise ValueError("Invalid backup")
            version = source.execute("SELECT value FROM store_meta WHERE key='schema_version'").fetchone()
            if version is None or int(version[0]) not in (1, SCHEMA_VERSION):
                raise ValueError("Unsupported backup schema")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb"):
                pass
            target = sqlite3.connect(str(destination))
            try:
                source.backup(target)
            finally:
                target.close()
        finally:
            source.close()
        return cls(destination)

    def export(self, owner_id="local"):
        with self.lock:
            return {"schema_version": SCHEMA_VERSION, "exported_at": utcnow(), "owner_id": owner_id,
                    "records": [self._decode(r) for r in self.db.execute("SELECT * FROM records WHERE owner_id=? ORDER BY created_at,id", (owner_id,))]}

    def forget(self, record_id, owner_id="local"):
        """Delete payload and dependant payloads, invalidate trained versions.

        Existing backup/export files are outside this deletion boundary and must
        be removed separately. Invalidated learned weights cannot be reactivated.
        """
        with self.transaction():
            record = self.get(record_id, owner_id)
            if record["owner_id"] != owner_id:
                raise ValueError("Only the owner may delete a record")
            pending, affected = [record_id], []
            while pending:
                rid = pending.pop()
                if rid not in affected:
                    affected.append(rid)
                    pending.extend(r[0] for r in self.db.execute("SELECT conclusion_id FROM dependencies WHERE premise_id=?", (rid,)))
            self._invalidate([record_id], "source erased")
            for model in self.db.execute("SELECT id,training_ids,metrics FROM models").fetchall():
                provenance = set(json.loads(model["training_ids"])) | {json.loads(model["metrics"])["validation_id"]}
                if provenance & set(affected):
                    self.db.execute("DELETE FROM models WHERE id=?", (model["id"],))
            for rid in affected:
                self.db.execute("DELETE FROM events WHERE record_id=?", (rid,))
                self.db.execute("DELETE FROM dependencies WHERE premise_id=?", (rid,))
                self.db.execute("DELETE FROM records WHERE id=?", (rid,))
            return {"deleted_ids": affected, "backup_deletion_required": True, "retraining_required": True}
