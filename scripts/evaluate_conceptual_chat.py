#!/usr/bin/env python3
"""Register and replay a known conversational regression corpus without Qwen."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.chat.provider import Settings
from src.chat.domain import normalize


def turn(text, **expected):
    return {"message": text, "expected": expected}


CORPUS = [
    {"id": "reported_user_dialogue", "turns": [
        turn("o que é um buraco negro?", status="unknown", no_hypotheses=True, no_user_learning=True),
        turn("buraco negro é um corpo celeste que absorve matéria e luz por causa da sua infinita gravidade.",
             user_triples=[["buraco negro", "é", "corpo celeste", True], ["buraco negro", "absorve", "materia", True], ["buraco negro", "absorve", "luz", True]], reported_cause=True),
        turn("considerando um buraco negro, o que seria um buraco branco?", target="buraco branco", no_hypotheses=True, no_user_learning=True),
        turn("considerando que buraco branco é o inverso de um buraco negro, o que seria um buraco branco?", target="buraco branco", reference="buraco negro", temporary=True,
             hypotheses=[["buraco branco", "expulsa", "materia"], ["buraco branco", "expulsa", "luz"]], no_user_learning=True, forbidden_hypothesis_terms=["gravidade", "infinita"]),
        turn("buraco branco é o inverso de um buraco negro?", no_user_learning=True),
        turn("O que é Taven?", target="taven", status="unknown", no_hypotheses=True, no_user_learning=True),
    ]},
    {"id": "invented_names_orientation_and_revision", "turns": [
        turn("Neral armazena energia. Vetra aquece água.", user_triples=[["neral", "armazena", "energia", True], ["vetra", "aquece", "agua", True]]),
        turn("Considerando que Neral é o inverso de Vetra, o que é Vetra?", target="vetra", reference="neral", temporary=True,
             hypotheses=[["vetra", "libera", "energia"]], forbidden_hypotheses=[["neral", "resfria", "agua"]], no_user_learning=True),
        turn("Vetra é o oposto de Neral.", user_triples=[["vetra", "oposto_de", "neral", True]]),
        turn("O que é Vetra?", target="vetra", hypotheses=[["vetra", "libera", "energia"]]),
        turn("Considerando que Vetra não é o inverso de Neral, o que é Vetra?", target="vetra", reference="neral", no_user_learning=True,
             forbidden_hypotheses=[["vetra", "libera", "energia"]]),
        turn("Corrigindo: Neral não armazena energia.", user_triples=[["neral", "armazena", "energia", False]]),
        turn("O que é Vetra?", target="vetra", forbidden_hypotheses=[["vetra", "libera", "energia"]]),
    ]},
    {"id": "analogy_and_counterexample", "turns": [
        turn("Mavon armazena energia. Mavon emite luz. Zedir armazena energia."),
        turn("Faça uma analogia para Zedir.", hypotheses=[["zedir", "emite", "luz"]], min_premises=3, method="analogy"),
        turn("Zedir não emite luz."),
        turn("Faça uma analogia para Zedir.", forbidden_hypotheses=[["zedir", "emite", "luz"]]),
    ]},
    {"id": "conversion_program_and_direction", "turns": [
        turn("Plorin converte luz em energia. Xaret converte energia em movimento."),
        turn("Crie uma solução para transformar luz em movimento.", hypotheses=[["sistema de plorin e xaret", "transforma", "luz em movimento"]],
             min_premises=2, method="conversion_composition", symbolic_artifact=True),
        turn("Crie uma solução para transformar movimento em luz.", no_hypotheses=True),
        turn("Corrigindo: Xaret não converte energia em movimento."),
        turn("Crie uma solução para transformar luz em movimento.", no_hypotheses=True),
    ]},
]
for index, connector in enumerate(("em razão de", "por conta de", "graças a"), 1):
    CORPUS.append({"id": "causal_qualification_" + str(index), "turns": [
        turn("Xalor absorve energia " + connector + " sua força.", user_triples=[["xalor", "absorve", "energia", True]], reported_cause=True),
        turn("Breno é o inverso de Xalor."),
        turn("O que Breno faria em oposição a Xalor?", target="breno", hypotheses=[["breno", "expulsa", "energia"]], forbidden_hypothesis_terms=["forca", "razao", "conta", "gracas"]),
    ]})

SOURCE_FILES = ["src/chat/discourse.py", "src/chat/domain.py", "src/chat/extraction.py", "src/chat/memory.py", "src/chat/reasoner.py", "src/chat/engine.py", "src/chat/provider.py",
                "src/cognition/processor.py", "src/cognition/engine.py", "src/cognition/contracts.py", "src/cognition/neural.py", "src/cognition/store.py", "src/cognition/telemetry.py",
                "experiments/cognition/intent-model.v1.json", "scripts/evaluate_conceptual_chat.py"]
PROTOCOL = {"id": "known-conceptual-chat-regression-v1", "corpus": CORPUS,
    "corpus_status": "Known regression cases selected from the user's reported dialogue and independently written QA scenarios; NOT blind or reserved evaluation.",
    "execution": {"entrypoint": "ChatEngine.reply", "provider": "symbolic", "research_mode": True, "general_models": "blocked by an adapter that raises on every model method", "storage": "fresh in-memory SQLite per dialogue", "repetitions": 1},
    "metrics": ["explicit expected facts and targets", "expected and prohibited hypotheses", "temporary assumption scope", "independent transformation verification recorded before rendering", "active premise IDs and cited source quotes", "novelty relative to supplied literal text only", "symbolic artifact versus unverified physical feasibility", "model calls"],
    "decision": "Report every turn and failed check; exit nonzero on any failure, without replacing expectations after observing output.",
    "source_files": SOURCE_FILES,
    "limitations": ["Finite controlled Portuguese grammar and programmed transformation operators", "Observed names and examples are known development regressions, not scientific evidence of generalization", "Functional hypotheses do not prove existence, causation or physical feasibility", "Surface novelty means a proposed triple was not literally supplied; it is not scientific novelty", "No Qwen, external corpus, personal chat database, or F00 reserved scoring"]}


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


class ForbiddenModel:
    def __init__(self):
        self.calls = 0

    def _blocked(self, *args, **kwargs):
        self.calls += 1
        raise AssertionError("General-model calls are prohibited in this regression.")

    complete = chat = arrange = test_connection = _blocked


def triple(record):
    return tuple(record.get(key, "") for key in ("subject", "predicate", "object"))


def user_state(memory):
    return sorted((row["id"], *triple(row), row["polarity"], row["status"]) for row in memory.claims(include_inactive=True) if row["origin"] == "user")


def evaluate_turn(item, result, memory, before_users, before_generated, supplied_texts, model):
    expected, package = item["expected"], result["answer_package"]
    hypotheses = package["hypotheses"]
    actual = {triple(h) for h in hypotheses}
    frame = result["problem"]["payload"].get("discourse", {})
    checks = {"no_general_model_calls": result["reasoning"]["model_calls"] == 0 and model.calls == 0,
              "semantic_package_precedes_rendering": result["reasoning"]["package_ready_before_model"] is True,
              "research_mode": result["reasoning"]["research_mode"] is True}
    for field, observed in (("target", result["focus"]), ("reference", frame.get("reference")), ("status", package["status"])):
        if field in expected:
            checks[field] = observed == expected[field]
    if expected.get("no_user_learning"):
        checks["no_user_learning"] = user_state(memory) == before_users and not result["learned"]
    if expected.get("no_hypotheses"):
        checks["no_hypotheses"] = not hypotheses
    for index, required in enumerate(expected.get("hypotheses", [])):
        checks["expected_hypothesis_"+str(index)] = tuple(required) in actual
    for index, prohibited in enumerate(expected.get("forbidden_hypotheses", [])):
        checks["prohibited_hypothesis_"+str(index)] = tuple(prohibited) not in actual
    for term in expected.get("forbidden_hypothesis_terms", []):
        checks["no_transferred_"+term] = all(normalize(term) not in normalize(h.get("object", "") + " " + h.get("text", "")) for h in hypotheses)
    user_triples = {(*triple(c), c["polarity"]) for c in memory.claims() if c["origin"] == "user" and c["status"] == "asserted"}
    for index, required in enumerate(expected.get("user_triples", [])):
        checks["supplied_fact_"+str(index)] = tuple(required) in user_triples
    if expected.get("reported_cause"):
        checks["cause_retained_without_transfer_authority"] = any(q.get("kind") == "reported_cause" and q.get("transferable_by_opposition") is False
            and q.get("causal_model_inferred") is False for q in result["problem"]["payload"].get("qualifications", []))
    if expected.get("temporary"):
        checks["temporary_scope"] = bool(frame.get("temporary_assumptions")) and all(h.get("scope") == "current_question" for h in hypotheses)
        checks["no_persistent_generated_claim"] = {c["id"] for c in memory.claims(include_inactive=True) if c["origin"] == "reasoner"} == before_generated
    if expected.get("symbolic_artifact"):
        checks["symbolic_artifact_only"] = any(c.get("operation") == "conversion_composition" and c.get("symbolic_goal_verified") is True
            and c.get("physical_feasibility_verified") is False and c.get("chain") for c in package["calculations"])
    evidence = []
    source_ids = {s["id"] for s in package["sources"]}
    for index, hypothesis in enumerate(hypotheses):
        parents = [memory.claim(identity) for identity in hypothesis.get("premise_ids", [])]
        checks["hypothesis_active_premises_"+str(index)] = bool(parents) and all(p["status"] in {"asserted", "deduced"} for p in parents)
        checks["hypothesis_cited_premises_"+str(index)] = all("M"+str(p["id"]) in source_ids for p in parents)
        checks["hypothesis_not_a_demonstrated_fact_"+str(index)] = hypothesis.get("status") == "hypothesis" and not any(
            c.get("status") == "deduced" and c.get("text") == hypothesis.get("text") for c in package["conclusions"])
        if "min_premises" in expected:
            checks["hypothesis_premise_count_"+str(index)] = len({p["id"] for p in parents}) >= expected["min_premises"]
        if "method" in expected:
            checks["hypothesis_method_"+str(index)] = hypothesis.get("method") == expected["method"]
        semantic_text = normalize(" ".join(triple(hypothesis)))
        novel = all(semantic_text not in normalize(text) for text in supplied_texts)
        checks["not_literally_supplied_"+str(index)] = novel
        if hypothesis.get("scope") == "current_question":
            verified = any(v.get("check") == "temporary_assumption_and_active_sources" and v.get("passed") is True for v in package["verification"])
        else:
            verified = any(v.get("claim_id") == hypothesis.get("claim_id") and v.get("passed") is True for v in package["verification"])
        checks["transformation_verified_"+str(index)] = verified
        evidence.append({"hypothesis": list(triple(hypothesis)), "method": hypothesis.get("method"), "new_relative_to_supplied_text": novel,
                         "premises": [{"id": p["id"], "triple": list(triple(p)), "status": p["status"], "sources": p["sources"]} for p in parents],
                         "temporary_assumptions": hypothesis.get("temporary_assumptions", []), "transformation_verified": verified})
    return {"checks": checks, "passed": all(checks.values()), "evidence": evidence,
            "semantic_snapshot": {"status": package["status"], "target": result["focus"], "hypotheses": sorted([list(h) for h in actual]),
                                  "user_triples": sorted([list(t) for t in user_triples]), "checks": checks}}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error("Escolha um diretório novo para preservar registros anteriores.")
    args.output_dir.mkdir(parents=True)
    write_new(args.output_dir / "protocol.json", PROTOCOL)
    initial_hashes = {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCE_FILES}
    write_new(args.output_dir / "registration.json", {"created_unix": time.time(), "source_sha256": initial_hashes,
        "protocol_sha256": hashlib.sha256((args.output_dir / "protocol.json").read_bytes()).hexdigest(), "started_scoring": False,
        "python": platform.python_version(), "platform": platform.platform(), "known_regression_corpus": True})
    started = time.perf_counter()
    dialogues = []
    for scenario in CORPUS:
        memory, model = Memory(":memory:"), ForbiddenModel()
        engine = ChatEngine(memory, Settings(provider="symbolic", research_mode=True), language_model=model)
        cid = memory.create_conversation()["id"]
        records, supplied = [], []
        try:
            for index, item in enumerate(scenario["turns"]):
                before_users = user_state(memory)
                before_generated = {c["id"] for c in memory.claims(include_inactive=True) if c["origin"] == "reasoner"}
                supplied.append(item["message"])
                result = engine.reply(cid, item["message"], request_id=scenario["id"]+":"+str(index))
                assessment = evaluate_turn(item, result, memory, before_users, before_generated, supplied, model)
                records.append({"message": item["message"], "expected": item["expected"], "result": result, **assessment})
            dialogues.append({"id": scenario["id"], "turns": records, "model_calls": model.calls})
        finally:
            engine.close(); memory.close()
    all_turns = [turn for d in dialogues for turn in d["turns"]]
    snapshots = [{"id": d["id"], "turns": [t["semantic_snapshot"] for t in d["turns"]]} for d in dialogues]
    final_hashes = {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in SOURCE_FILES}
    checks = [passed for row in all_turns for passed in row["checks"].values()]
    report = {"protocol": PROTOCOL["id"], "known_regression_corpus": True, "dialogues": dialogues,
              "summary": {"dialogues": len(dialogues), "turns": len(all_turns), "checks": len(checks), "passed_checks": sum(checks),
                          "passed_turns": sum(t["passed"] for t in all_turns), "hypotheses_assessed": sum(len(t["evidence"]) for t in all_turns),
                          "general_model_calls": sum(d["model_calls"] for d in dialogues), "source_hashes_unchanged_during_run": initial_hashes == final_hashes},
              "semantic_sha256": hashlib.sha256(json.dumps(snapshots, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest(),
              "seconds": time.perf_counter()-started, "limitations": PROTOCOL["limitations"]}
    write_new(args.output_dir / "results.json", report)
    print(json.dumps({"output": str(args.output_dir.resolve()), **report["summary"], "semantic_sha256": report["semantic_sha256"]}, ensure_ascii=False, indent=2))
    return 0 if all(checks) and initial_hashes == final_hashes else 1


if __name__ == "__main__":
    raise SystemExit(main())
