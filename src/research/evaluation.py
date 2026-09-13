"""F00 measurement harness: offline, bounded, auditable, no reserved scoring."""
import copy
import hashlib
import json
import math
import platform
import random
import statistics
import sys
import time
from pathlib import Path

from .baselines import BASELINES
from .worlds import (FAMILIES, GENERATOR_VERSION, TASK_KINDS,
                     generate_case, hidden_success, integer, observed_success)


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PROTOCOL = ROOT / "experiments" / "f00" / "protocol.v1.json"
PROTOCOL_KEYS = {
    "protocol_id", "registered_date", "generator_version", "status", "splits",
    "cases_per_seed", "evidence_budget", "max_plan_steps", "max_operations_per_case",
    "max_seconds_per_case", "bootstrap_repetitions", "bootstrap_seed", "comparators",
    "primary_metric", "decision_rule", "reserved_policy",
}


def load_protocol(path=DEFAULT_PROTOCOL):
    protocol = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(protocol, dict) or set(protocol) != PROTOCOL_KEYS:
        raise ValueError("protocol must contain exactly the documented v1 fields")
    if protocol["generator_version"] != GENERATOR_VERSION:
        raise ValueError("generator version mismatch")
    for name in ("protocol_id", "registered_date", "status", "decision_rule", "reserved_policy"):
        if not isinstance(protocol[name], str) or not protocol[name].strip():
            raise ValueError(name + " must be a nonempty string")
    if protocol["primary_metric"] != "supported_task_success_rate":
        raise ValueError("unsupported primary metric")
    count = integer("cases_per_seed", protocol["cases_per_seed"], 3, 99)
    if count % 3:
        raise ValueError("cases_per_seed must be divisible by three for balanced strata")
    integer("evidence_budget", protocol["evidence_budget"], 4, 16)
    integer("max_plan_steps", protocol["max_plan_steps"], 2, 2)
    integer("max_operations_per_case", protocol["max_operations_per_case"], 1, 10000)
    integer("bootstrap_repetitions", protocol["bootstrap_repetitions"], 100, 10000)
    integer("bootstrap_seed", protocol["bootstrap_seed"], 0, 2 ** 32 - 1)
    seconds = protocol["max_seconds_per_case"]
    if type(seconds) not in (int, float) or not math.isfinite(seconds) or not 0 < seconds <= 10:
        raise ValueError("max_seconds_per_case must be finite, positive and at most ten")
    splits = protocol["splits"]
    if not isinstance(splits, dict) or set(splits) != set(FAMILIES):
        raise ValueError("protocol needs all three distinct splits")
    all_seeds = []
    for split, config in splits.items():
        if not isinstance(config, dict) or set(config) != {"family", "seeds"} or config["family"] != FAMILIES[split]:
            raise ValueError("split family does not match the frozen structural assignment")
        seeds = config["seeds"]
        if not isinstance(seeds, list) or not 2 <= len(seeds) <= 20:
            raise ValueError("each split requires between two and twenty seeds")
        for seed in seeds:
            integer("seed", seed, 0, 2 ** 32 - 1)
        all_seeds.extend(seeds)
    if len(set(all_seeds)) != len(all_seeds):
        raise ValueError("seeds must be distinct within and across splits")
    if max(len(c["seeds"]) for c in splits.values()) * count > 1000:
        raise ValueError("at most 1000 cases per split are allowed")
    names = protocol["comparators"]
    if (not isinstance(names, list) or not names or any(not isinstance(n, str) or n not in BASELINES for n in names)
            or len(set(names)) != len(names)):
        raise ValueError("comparators must be a nonempty, unique list of registered names")
    return protocol


def bootstrap_interval(values, repetitions=1000, seed=20260908):
    """Percentile interval over independent seed means, never individual cases."""
    if not values or any(type(v) not in (int, float) or not math.isfinite(v) for v in values):
        raise ValueError("bootstrap requires finite numeric values")
    integer("repetitions", repetitions, 100, 10000)
    integer("seed", seed, 0, 2 ** 32 - 1)
    rng = random.Random(seed)
    samples = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(repetitions))
    return [samples[int((repetitions - 1) * 0.025)], samples[int((repetitions - 1) * 0.975)]]


def score_result(case, result):
    valid = (isinstance(result, dict) and set(result) == {"status", "plan", "operations"}
             and isinstance(result["status"], str)
             and result["status"] in {"answered", "insufficient", "budget_exhausted"}
             and isinstance(result["plan"], list) and all(isinstance(a, str) for a in result["plan"])
             and type(result["operations"]) is int and result["operations"] >= 0
             and (result["status"] == "answered" or not result["plan"]))
    if not valid:
        return {"correct": False, "answered": False, "unsupported_answer": False,
                "hidden_plan_success": False, "invalid_output": True,
                "correct_abstention": False, "missed_answer": False}
    answered = result["status"] == "answered"
    supported = answered and observed_success(case.public, result["plan"])
    physical = answered and hidden_success(case, result["plan"])
    expected = case.oracle["expected_status"]
    abstained = result["status"] == "insufficient"
    return {"correct": (supported and physical and expected == "answered") or (abstained and expected == "insufficient"),
            "answered": answered, "unsupported_answer": answered and not supported,
            "hidden_plan_success": physical, "invalid_output": False,
            "correct_abstention": abstained and expected == "insufficient",
            "missed_answer": abstained and expected == "answered"}


def summarize(rows, protocol):
    summary = {}
    for name in protocol["comparators"]:
        selected = [r for r in rows if r["comparator"] == name]
        total = len(selected)
        answered = sum(r["score"]["answered"] for r in selected)
        insufficient = sum(r["expected_status"] == "insufficient" for r in selected)
        seed_means = [statistics.mean(r["score"]["correct"] for r in selected if r["seed"] == seed)
                      for seed in sorted({r["seed"] for r in selected})]
        summary[name] = {
            "cases": total, "correct": sum(r["score"]["correct"] for r in selected),
            "supported_task_success_rate": statistics.mean(seed_means),
            "seed_bootstrap_95_interval": bootstrap_interval(seed_means, protocol["bootstrap_repetitions"], protocol["bootstrap_seed"]),
            "answered": answered,
            "answer_coverage": answered / total,
            "unsupported_answers": sum(r["score"]["unsupported_answer"] for r in selected),
            "unsupported_answer_rate": sum(r["score"]["unsupported_answer"] for r in selected) / answered if answered else None,
            "correct_abstention_rate": sum(r["score"]["correct_abstention"] for r in selected) / insufficient if insufficient else None,
            "invalid_outputs": sum(r["score"]["invalid_output"] for r in selected),
            "budget_exhaustions": sum(r["budget_exhausted"] for r in selected),
            "seconds_total": sum(r["seconds"] for r in selected),
            "operations_total": sum(r["measured_operations"] for r in selected),
            "by_kind": {kind: {"cases": sum(r["kind"] == kind for r in selected),
                               "correct": sum(r["score"]["correct"] for r in selected if r["kind"] == kind)} for kind in TASK_KINDS},
            "seed_success_rates": seed_means,
        }
    return summary


def source_fingerprints():
    paths = ["src/research/worlds.py", "src/research/baselines.py", "src/research/evaluation.py", "scripts/evaluate_f00.py"]
    return {path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest() for path in paths}


def run_evaluation(protocol_path=DEFAULT_PROTOCOL, split="validation"):
    # No CLI flag silently unlocks a benchmark held for a future scientific claim.
    if not isinstance(split, str) or split not in {"development", "validation"}:
        raise ValueError("F00 scores only development or validation; reserved remains unopened")
    protocol = load_protocol(protocol_path)
    rows = []
    for seed in protocol["splits"][split]["seeds"]:
        for index in range(protocol["cases_per_seed"]):
            case = generate_case(split, seed, index, protocol["evidence_budget"])
            for name in protocol["comparators"]:
                public = case.public_input()
                started = time.perf_counter()
                try:
                    result = BASELINES[name](public, protocol["max_operations_per_case"])
                except Exception as exc:
                    # One failed comparator is a failed case, not missing data.
                    # Do not include arbitrary exception messages in artifacts.
                    result = {"comparator_error_type": type(exc).__name__}
                seconds = time.perf_counter() - started
                # Built-ins have deterministic operation limits. This wall-time
                # criterion detects overruns after return, not process preemption.
                over = seconds > protocol["max_seconds_per_case"]
                if public != case.public:
                    raise RuntimeError("comparator mutated its input: " + name)
                score = score_result(case, result)
                operation_count = result.get("operations", 0) if isinstance(result, dict) else 0
                if type(operation_count) is not int or operation_count < 0:
                    operation_count = 0
                status = result.get("status") if isinstance(result, dict) else None
                if over or operation_count > protocol["max_operations_per_case"]:
                    score["correct"] = False
                    over = True
                if not isinstance(result, dict):
                    result = {"invalid_output_type": type(result).__name__}
                try:
                    json.dumps(result, allow_nan=False)
                except (TypeError, ValueError, OverflowError):
                    result = {"invalid_output_type": type(result).__name__, "serialization_error": True}
                rows.append(dict(case.metadata, comparator=name, result=copy.deepcopy(result), score=score,
                                 expected_status=case.oracle["expected_status"], seconds=seconds,
                                 measured_operations=operation_count,
                                 budget_exhausted=over or status == "budget_exhausted"))
    summary = summarize(rows, protocol)
    paired = {}
    if "symbolic_search" in summary and "memory_only" in summary:
        differences = [a - b for a, b in zip(summary["symbolic_search"]["seed_success_rates"], summary["memory_only"]["seed_success_rates"])]
        paired["symbolic_search_minus_memory_only"] = {
            "mean": statistics.mean(differences),
            "seed_bootstrap_95_interval": bootstrap_interval(differences, protocol["bootstrap_repetitions"], protocol["bootstrap_seed"]),
            "interpretation": "expected effect of programmed chaining; not evidence of learning new rules",
        }
    return {
        "report_version": "f00-report-1", "protocol_id": protocol["protocol_id"],
        "protocol_sha256": hashlib.sha256(Path(protocol_path).read_bytes()).hexdigest(),
        "generator_version": GENERATOR_VERSION, "source_sha256": source_fingerprints(),
        "split": split, "family": FAMILIES[split], "reserved_evaluated": False,
        "qwen_calls": 0, "network_calls": 0, "training_scope": "per-episode evidence only; no persistent training",
        "environment": {"python": sys.version.split()[0], "platform": platform.platform(), "machine": platform.machine()},
        "summary": summary, "paired_comparisons": paired, "rows": rows,
        "pending_comparators": {
            "current_chat_rules": "not_comparable: current universal-triple engine has no state/action plan adapter",
            "qwen_only": "not_executed: pretraining and structured output protocol must be controlled first",
            "own_core_without_qwen": "not_implemented: F01 and subsequent phases",
            "own_core_with_qwen": "not_implemented: F01 and subsequent phases",
        },
        "limitations": ["one structural family per split", "finite fully observed deterministic states",
                        "only two-step observed-edge composition", "synthetic exact evidence, no language understanding",
                        "ten seed clusters are a pilot, not a power guarantee",
                        "bootstrap intervals describe these seeds; do not establish general intelligence",
                        "oracle isolation is a trusted-code interface, not an adversarial sandbox"],
    }
