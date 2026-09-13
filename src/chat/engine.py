"""Own reasoning before language arrangement; durable, resumable chat turns."""
import json
import threading
import time
import uuid
from dataclasses import asdict
from pathlib import Path

from .domain import Assertion
from .extraction import is_correction
from .provider import LanguageModel, Settings
from .reasoner import Reasoner, refers_to_previous, retrieve, verify_hypothesis
from src.cognition.contracts import AnswerPackage, ProblemSpec, render_with_arranger
from src.cognition.engine import CognitiveCore
from src.cognition.processor import process_message
from src.cognition.store import ExperienceStore
from src.cognition.telemetry import start_measurement, finish_measurement


class ChatEngine:
    def __init__(self, memory, settings=None, language_model=None, experience_store=None, core=None):
        self.memory, self.settings = memory, settings or Settings()
        self.language_model = language_model or LanguageModel(self.settings)
        self.reasoner, self.core = Reasoner(), core or CognitiveCore()
        self._turn_lock = threading.RLock()
        self._owns_store = experience_store is None
        if experience_store is None:
            path = memory.db.execute("PRAGMA database_list").fetchone()[2]
            experience_store = ExperienceStore(Path(path).with_name(Path(path).stem + ".cognition.sqlite3") if path else ":memory:")
        self.experience_store = experience_store

    def close(self):
        if self._owns_store:
            self.experience_store.close()

    def _prepare(self, conversation_id, text, request_id, problem, pending):
        """Called within a short memory transaction; no model/simulator calls."""
        user_id = pending["id"] if pending else self.memory.add_message(conversation_id, "user", text,
                    {"request_id": request_id, "processing": True, "problem_id": problem.digest, "problem": problem.to_dict()})
        learned, invalidated, conflicts, seen = [], [], [], set()
        if pending:
            learned = [row[0] for row in self.memory.db.execute("SELECT claim_id FROM sources WHERE message_id=?", (user_id,))
                       if self.memory.claim(row[0])["status"] in {"asserted", "deduced", "hypothesis"}]
        for raw in ([] if pending else problem.facts):
            assertion = Assertion(**raw).clean()
            key = (assertion.subject, assertion.predicate, assertion.object, assertion.polarity, assertion.scope)
            if key in seen:
                continue
            seen.add(key)
            claim_id, removed, disputed = self.memory.learn(assertion, user_id, is_correction(text))
            learned.append(claim_id); invalidated.extend(removed); conflicts.extend(disputed)
        new_deductions = []
        for _ in range(4):
            progress = False
            for proposal in self.reasoner.deduce(self.memory.claims()):
                claim, created = self.memory.propose(proposal)
                if claim["status"] == "disputed":
                    conflicts.extend(c["id"] for c in self.memory.claims() if c["status"] == "disputed" and
                                     (c["subject"], c["predicate"], c["object"]) == (claim["subject"], claim["predicate"], claim["object"]))
                if created:
                    new_deductions.append(claim["id"]); progress = True
            if not progress:
                break
        previous_subject = problem.context.get("subject", "")
        all_claims = self.memory.claims()
        by_id = {c["id"]: c for c in all_claims}
        for claim in all_claims:
            if claim["origin"] == "reasoner" and claim["status"] == "hypothesis" and not verify_hypothesis(claim, by_id):
                invalidated.extend(self.memory.invalidate_generated(claim["id"], "A transformação perdeu apoio após reavaliar as relações atuais."))
        all_claims = self.memory.claims()
        frame = problem.payload.get("discourse", {})
        relevant = retrieve(text, all_claims, previous_subject, conversation_id=conversation_id, frame=frame)
        inferred = []
        temporary = []
        candidates = self.reasoner.explore(text, all_claims, relevant, previous_subject, frame=frame)
        for proposal in candidates:
            candidate = asdict(proposal)
            wrong_target = (frame.get("mode") == "assume_relation" and frame.get("target")
                            and proposal.subject != frame["target"])
            if wrong_target or not verify_hypothesis(candidate, {c["id"]: c for c in all_claims}, frame.get("temporary_assumptions", [])):
                self.reasoner.trace.append({"operation": "reject_proposal", "method": proposal.method,
                                            "reason": "transformation_replay_failed", "accepted": False})
                continue
            if frame.get("mode") == "assume_relation":
                temporary.append(candidate)
                continue
            claim, _ = self.memory.propose(proposal)
            if claim["origin"] == "reasoner" and claim["status"] in {"hypothesis", "deduced"}:
                inferred.append(claim)
        for claim in relevant:
            if claim["status"] == "deduced" and claim["id"] not in {c["id"] for c in inferred}:
                inferred.append(claim)
        for cid in new_deductions:
            claim = self.memory.claim(cid)
            if claim["status"] == "deduced" and cid not in {c["id"] for c in inferred} and any(p in learned for p in claim["premises"]):
                inferred.append(claim)
        conflict_claims = [c for c in self.memory.claims() if c["status"] == "disputed" and
                           (c["id"] in conflicts or c["id"] in {r["id"] for r in relevant})]
        return user_id, {"learned": [self.memory.claim(cid) for cid in dict.fromkeys(learned)],
                         "relevant": relevant, "inferences": inferred, "conflicts": conflict_claims,
                         "invalidated": invalidated, "claims": self.memory.claims(),
                         "temporary_inferences": temporary, "reasoning_trace": list(self.reasoner.trace),
                         "memory_operations": self.reasoner.operations + len(new_deductions)}

    def _record_experience(self, conversation_id, text, request_id, user_id, problem, context):
        withdrawn = set(context["invalidated"]) | {c["id"] for c in context["conflicts"]}
        if withdrawn:
            self.experience_store.invalidate_sources(["M" + str(cid) for cid in withdrawn], reason="Premissa do chat revisada ou em conflito.")
        kind = problem.intent if problem.intent in {"question", "correction", "hypothesis", "preference"} else "episode"
        episode = self.experience_store.record(conversation_id, kind,
            {"message": text, "intent": problem.intent, "problem_id": problem.digest, "entities": problem.entities,
             "quantities": problem.payload.get("quantities", [])}, ["message:" + str(user_id)], evidence="user",
            status="hypothesis" if kind == "hypothesis" else "asserted", dedupe_key="turn:" + request_id)
        ids = [episode]
        for claim in context["learned"]:
            rid = self.experience_store.record(conversation_id, "relation",
                {"predicate": claim["predicate"], "arguments": [claim["subject"], claim["object"]],
                 "polarity": claim["polarity"], "scope": claim["scope"]}, ["M" + str(claim["id"]), episode],
                scope="user", status=claim["status"] if claim["status"] in {"hypothesis", "disputed"} else "asserted", evidence="user",
                dedupe_key="claim:" + request_id + ":" + str(claim["id"]))
            ids.append(rid)
        return ids

    def reply(self, conversation_id, text, request_id=None, on_token=None, on_progress=None, cancel_event=None):
        if not isinstance(text, str) or not text.strip() or len(text) > 8000:
            raise ValueError("Escreva uma mensagem de até 8.000 caracteres.")
        text, request_id = text.strip(), request_id or uuid.uuid4().hex
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
            raise ValueError("Identificador de envio inválido.")
        with self._turn_lock:
            measurement = start_measurement()
            started = time.perf_counter()
            def cancelled():
                if cancel_event is not None and cancel_event.is_set():
                    raise ValueError("Processamento cancelado; reenvie a mesma mensagem para retomar.")
            cancelled()
            settings, language_model = self.settings, self.language_model
            with self.memory.lock:
                self.memory.conversation(conversation_id)
                cached = self.memory.cached_turn(request_id, conversation_id, text)
                if cached:
                    return cached
                history = self.memory.messages(conversation_id)
                pending = next((m for m in history if m["role"] == "user" and m["metadata"].get("request_id") == request_id), None)
                if pending and pending["content"] != text:
                    raise ValueError("Identificador de envio já utilizado para outra mensagem.")
            problem = (ProblemSpec.from_dict(pending["metadata"]["problem"]) if pending and pending["metadata"].get("problem") else
                       process_message(text, [m for m in history if pending is None or m["id"] != pending["id"]], conversation_id=conversation_id))
            processed_at = time.perf_counter()
            if on_progress:
                on_progress("processing")
            with self.memory.transaction():
                user_id, context = self._prepare(conversation_id, text, request_id, problem, pending)
            warnings = []
            experience_ids = self._record_experience(conversation_id, text, request_id, user_id, problem, context)
            context["experience_store"] = self.experience_store
            context["current_experience_id"] = experience_ids[0]
            context["experiences"] = self.experience_store.retrieve(conversation_id, {}, limit=20)
            context["cancel_event"] = cancel_event
            remembered_at = time.perf_counter()
            cancelled()
            # Neither solving nor rendering holds the chat DB transaction/lock.
            saved_package = pending["metadata"].get("approved_package") if pending else None
            package = AnswerPackage.from_dict(saved_package) if saved_package else self.core.solve(problem, context)
            if not isinstance(package, AnswerPackage):
                raise RuntimeError("O núcleo não devolveu um pacote validado.")
            if package.problem_id != problem.digest:
                raise RuntimeError("O pacote persistido não corresponde ao problema desta mensagem.")
            if saved_package:
                from src.cognition.operator_runtime import package_is_current, obsolete_package
                if not package_is_current(package, self.experience_store, conversation_id, self.memory):
                    package = obsolete_package(problem)
            # Persist the completed semantic step before checking cancellation or
            # invoking an arranger. Retrying the same turn must not learn a new
            # operator version or duplicate an invention already completed.
            with self.memory.transaction():
                self.memory.db.execute("UPDATE messages SET metadata=? WHERE id=?", (
                    json.dumps({"request_id": request_id, "processing": True, "problem_id": problem.digest,
                                "problem": problem.to_dict(), "approved_package": package.to_dict()}), user_id))
            package_ready = time.perf_counter()
            cancelled()
            if on_progress:
                on_progress("verified")
            response, rendering = render_with_arranger(package, language_model, settings.research_mode)
            rendered_at = time.perf_counter()
            cancelled()
            if rendering["mode"] == "deterministic_fallback":
                warnings.append("O organizador não preservou o contrato ou ficou indisponível; usei o pacote aprovado.")
            learned, relevant = context["learned"], context["relevant"]
            focus = (problem.question.get("subject") or (learned[0]["subject"] if learned else "") or
                     (relevant[0]["subject"] if relevant else problem.context.get("subject", "") if refers_to_previous(text) else ""))
            provider = settings.provider if rendering["mode"] == "approved_sentence_order" else "symbolic"
            result = {"conversation_id": conversation_id, "content": response, "learned": learned, "retrieved": relevant,
                      "inferences": context["inferences"], "conflicts": context["conflicts"], "invalidated": sorted(set(context["invalidated"])),
                      "focus": focus, "provider": provider, "model": settings.model if provider != "symbolic" else "",
                      "warnings": warnings, "request_id": request_id, "problem": problem.to_dict(), "answer_package": package.to_dict(),
                      "rendering": rendering, "experience_ids": experience_ids,
                      "reasoning": {"status": package.status, "domain": package.domain, "operations": package.operations,
                                    "package_sha256": package.digest, "package_ready_before_model": True,
                                    "core_seconds": package_ready - started, "total_seconds": time.perf_counter() - started,
                                    "timings": {"comprehension": processed_at - started, "memory": remembered_at - processed_at,
                                                "reasoning_verification": package_ready - remembered_at, "rendering": rendered_at - package_ready},
                                    "research_mode": settings.research_mode, "model_calls": rendering["model_calls"]}}
            result["reasoning"]["resources"] = finish_measurement(measurement, package)
            with self.memory.transaction():
                result["message_id"] = self.memory.add_message(conversation_id, "assistant", response, result)
                self.memory.db.execute("UPDATE messages SET metadata=? WHERE id=?", (
                    json.dumps({"request_id": request_id, "processing": False, "problem_id": problem.digest}), user_id))
                result["stats"] = self.memory.stats()
                self.memory.save_turn(request_id, conversation_id, text, result)
            if on_token:
                on_token(response)  # Only approved, persisted text reaches the stream.
            return result
