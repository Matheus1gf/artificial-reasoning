#!/usr/bin/env python3
"""Reproduce measured retention, replay, versioning and withdrawal in a temp DB."""
import argparse
import hashlib
import json
import platform
import random
import resource
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.learning import consolidate_model
from src.cognition.store import ExperienceStore


def dump(path, value):
    with path.open("x", encoding="utf-8") as output:
        json.dump(value, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def predict(model, inputs):
    return model["coefficients"].get(str(int(inputs[0])), 0.0) * inputs[1]


def fit(rows, prior=None):
    # Explicit modular inductive bias. The coefficients are fitted from samples.
    coefficients = dict((prior or {}).get("coefficients", {}))
    for task in sorted({int(row["inputs"][0]) for row in rows}):
        selected = [row for row in rows if int(row["inputs"][0]) == task]
        coefficients[str(task)] = (sum(row["inputs"][1] * row["target"] for row in selected)
                                  / sum(row["inputs"][1] ** 2 for row in selected))
    return {"coefficients": coefficients, "hypothesis_class": "y=w_task*x"}


def samples(seed, task, xs, coefficient, partition):
    return [{"id": "seed{}:{}:task{}:x{}".format(seed, partition, task, x),
             "inputs": [task, x], "target": coefficient * x} for x in xs]


def observe(store, rows):
    return [store.record("pilot", "experiment", dict(row, sample_ids=[row["id"]]),
                         [row["id"]], status="verified", evidence="experiment") for row in rows]


def score(model, rows):
    return sum((predict(model, row["inputs"]) - row["target"]) ** 2 for row in rows) / len(rows)


def run_case(directory, seed, condition, protocol):
    rng = random.Random(seed)
    coefficients = [rng.choice([-3, -2, 2, 3]), rng.choice([-4, -2, 2, 4])]
    database = directory / (str(seed) + "-" + condition + ".sqlite3")
    store = ExperienceStore(database)
    try:
        training = [samples(seed, task, protocol["training_x"], coefficients[task], "train") for task in (0, 1)]
        validation = [samples(seed, task, protocol["validation_x"], coefficients[task], "validation") for task in (0, 1)]
        retention = samples(seed, 0, protocol["retention_x"], coefficients[0], "retention")
        old_ids = observe(store, training[0])
        empty = {"coefficients": {}}
        first = consolidate_model(store, "pilot", "pilot-model", fit, predict,
                                  validation[0], retention, policy=protocol["policy"], initial_artifact=empty)
        previous = store.model("pilot-model")["artifact"]
        new_ids = observe(store, training[1])
        if condition == "new-task-only":
            trainer = lambda rows: fit([row for row in rows if row["inputs"][0] == 1])
        elif condition == "preserve-old-module":
            trainer = lambda rows: fit([row for row in rows if row["inputs"][0] == 1], previous)
        else:
            trainer = fit
        second = consolidate_model(store, "pilot", "pilot-model", trainer, predict,
                                   validation[1], retention, policy=protocol["policy"])
        active = store.model("pilot-model")
        before_rollback = active["id"]
        store.rollback_model(first["model_version"])
        rollback_exact = store.model("pilot-model")["artifact"] == previous
        store.rollback_model(before_rollback)
        backup = store.backup(directory / (database.stem + ".backup"))
        restored = ExperienceStore.restore(backup["path"], directory / (database.stem + "-restored.sqlite3"))
        try:
            # Each export has its own wall-clock timestamp; compare stored data.
            restoration_equal = (restored.export()["records"] == store.export()["records"]
                                 and restored.model("pilot-model") == store.model("pilot-model"))
        finally:
            restored.close()
        store.retract(old_ids[0], "simulated withdrawal")
        disabled = store.model("pilot-model") is None
        forget = store.forget(old_ids[0])
        surviving = store.db.execute("SELECT COUNT(*) FROM models").fetchone()[0]
        return {"seed": seed, "condition": condition, "coefficients_hidden_from_trainer": coefficients,
                "datasets": {"training": training, "validation": validation, "retention": retention},
                "first_task": first, "second_task": second,
                "adopted_old_task_mse": score(active["artifact"], retention),
                "adopted_new_task_mse": score(active["artifact"], validation[1]),
                "rollback_exact": rollback_exact, "backup_restore_equal": restoration_equal,
                "withdrawal_disabled_active": disabled, "dependent_weight_versions_remaining": surviving,
                "forget": forget, "recorded_experiences": len(old_ids) + len(new_ids)}
    finally:
        store.close()


def run_drift(directory, protocol):
    store = ExperienceStore(directory / "drift.sqlite3")
    try:
        old = samples(71, 0, protocol["training_x"], 2, "old-observed")
        old_ids = observe(store, old)
        first = consolidate_model(store, "pilot", "drift", fit, predict,
            samples(71, 0, protocol["validation_x"], 2, "old-validation"),
            samples(71, 0, protocol["retention_x"], 2, "old-retention"),
            policy=protocol["policy"], initial_artifact={"coefficients": {}})
        previous = store.model("drift")["artifact"]
        for rid in old_ids:
            store.retract(rid, "domain changed: old observations no longer apply")
        disabled = store.model("drift") is None
        observe(store, samples(71, 0, protocol["training_x"], -3, "new-observed"))
        changed = consolidate_model(store, "pilot", "drift", fit, predict,
            samples(71, 0, protocol["validation_x"], -3, "new-validation"),
            samples(71, 0, protocol["retention_x"], -3, "new-retention"),
            policy=protocol["policy"], initial_artifact=previous)
        return {"old_coefficient": 2, "new_coefficient": -3, "change_supplied_by_observer": True,
                "obsolete_model_disabled": disabled, "old_version": first["model_version"],
                "adaptation": changed,
                "limit": "Relevance/domain change supplied explicitly; automatic drift detection not claimed"}
    finally:
        store.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="New directory; existing results are never overwritten")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source_paths = [ROOT / path for path in ("experiments/learning/protocol.v1.json", "scripts/evaluate_learning.py",
                                           "src/cognition/learning.py", "src/cognition/store.py")]
    fingerprints = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest() for path in source_paths}
    protocol = json.loads(source_paths[0].read_text())
    registration = {"protocol": protocol, "sha256": fingerprints, "python": sys.version,
                    "platform": platform.platform(), "registered_before_training": True}
    dump(args.output / "registration.json", registration)
    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="ar-learning-pilot-") as temporary:
        directory = Path(temporary)
        results = [run_case(directory, seed, condition, protocol)
                   for seed in protocol["seeds"] for condition in protocol["conditions"]]
        drift = run_drift(directory, protocol)
    decisions = {
        "initial_learning_adopted_all": all(row["first_task"]["status"] == "adopted" for row in results),
        "unacceptable_forgetting_rejected_all": all(row["second_task"]["status"] == "rejected"
             and not row["second_task"]["metrics"]["retention_passed"] for row in results if row["condition"] == "new-task-only"),
        "replay_and_modular_adopted_all": all(row["second_task"]["status"] == "adopted"
             and row["adopted_old_task_mse"] <= 1e-10 and row["adopted_new_task_mse"] <= 1e-10
             for row in results if row["condition"] != "new-task-only"),
        "backup_rollback_withdrawal_all": all(row["rollback_exact"] and row["backup_restore_equal"]
             and row["withdrawal_disabled_active"] and row["dependent_weight_versions_remaining"] == 0 for row in results),
        "explicit_drift_adapted": drift["obsolete_model_disabled"] and drift["adaptation"]["status"] == "adopted"}
    report = {"schema_version": 1, "kind": "synthetic_learning_control_pilot", "official_reserved_test_used": False,
              "results": results, "drift": drift, "decisions": decisions,
              "seconds": time.monotonic() - started, "peak_rss_native": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
              "rss_unit": "bytes" if sys.platform == "darwin" else "KiB", "limitations": protocol["limits"]}
    dump(args.output / "report.json", report)
    print(json.dumps({"output": str(args.output.resolve()), "decisions": decisions, "seconds": report["seconds"]}, indent=2))
    return 0 if all(decisions.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
