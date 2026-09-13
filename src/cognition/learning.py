"""Measured promotion of a numeric learner; conversation text cannot authorize it.

The trainer and predictor are trusted application functions. Held-out targets
are never supplied to the trainer. This controller does not claim to erase
information from existing weights; withdrawal disables the dependent version.
"""
import copy
import hashlib
import math
import time

from .store import encode


def _samples(rows):
    if not isinstance(rows, list) or not rows or len(rows) > 1000:
        raise ValueError("Use between 1 and 1000 samples per set")
    cleaned = []
    for row in rows:
        if not isinstance(row, dict) or not {"inputs", "target", "id"} <= row.keys():
            raise ValueError("Each sample requires inputs, target and id")
        if not isinstance(row["id"], str) or not row["id"]:
            raise ValueError("A sample needs provenance")
        if not isinstance(row["inputs"], list) or not 1 <= len(row["inputs"]) <= 64:
            raise ValueError("Numeric features required")
        if any(type(v) not in (int, float) or not math.isfinite(v) or abs(v) > 1e50
               for v in row["inputs"] + [row["target"]]):
            raise ValueError("Finite bounded features and target required")
        item = copy.deepcopy(row)
        item["inputs"] = [0.0 if value == 0 else float(value) for value in item["inputs"]]
        item["target"] = 0.0 if item["target"] == 0 else float(item["target"])
        cleaned.append(item)
    if len({r["id"] for r in cleaned}) != len(cleaned):
        raise ValueError("Duplicate sample IDs")
    return cleaned


def _loss(artifact, rows, predict):
    errors = []
    for row in rows:
        value = predict(copy.deepcopy(artifact), copy.deepcopy(row["inputs"]))
        if type(value) not in (int, float) or not math.isfinite(value) or abs(value) > 1e50:
            raise ValueError("Predictor produced invalid output")
        errors.append((value - row["target"]) ** 2)
    return sum(errors) / len(errors)


def consolidate_model(store, conversation_id, name, trainer, predictor, validation, retention,
                      *, policy, owner_id="local", initial_artifact=None):
    """Fit selected, verified samples and evaluate before version activation.

    Trainer receives [{'inputs': [...], 'target': x, 'id': ...}], never a store
    handle, held-out data or their scores. Replays include all selected eligible
    experiences; retention is measured on a separate prior-domain set.
    """
    required = {"training_consent", "min_gain", "max_validation_error", "max_forgetting", "protocol_id"}
    if not isinstance(policy, dict) or not required <= policy.keys() or set(policy) - required - {"limit"}:
        raise ValueError("Explicit training and evaluation policy required")
    if not isinstance(policy["protocol_id"], str) or not policy["protocol_id"]:
        raise ValueError("A versioned protocol ID is required")
    for key in ("min_gain", "max_validation_error", "max_forgetting"):
        if type(policy[key]) not in (int, float) or not math.isfinite(policy[key]) or policy[key] < 0:
            raise ValueError("Evaluation thresholds must be nonnegative finite numbers")
    selected = store.consolidate(conversation_id, {"training_consent": policy["training_consent"],
                    "kinds": ["experiment", "test_result", "state"], "limit": policy.get("limit", 100)}, owner_id)
    if not selected["eligible_ids"]:
        return {"status": "no_eligible_experiences", "weights_updated": False, "selected": selected}
    training = []
    for rid in selected["eligible_ids"]:
        record = store.get(rid, owner_id)
        payload = record["payload"]
        if {"inputs", "target"} <= payload.keys():
            samples = payload.get("sample_ids", record["source_ids"])
            if not isinstance(samples, list) or not samples or any(not isinstance(s, str) or not s for s in samples):
                raise ValueError("Training samples require nonempty sample provenance")
            training.append({"id": samples[0],
                             "inputs": payload["inputs"], "target": payload["target"], "record_id": rid})
    if not training:
        return {"status": "no_numeric_training_samples", "weights_updated": False, "selected": selected}
    training, validation, retention = _samples(training), _samples(validation), _samples(retention)
    groups = [{r["id"] for r in rows} for rows in (training, validation, retention)]
    if any(groups[i] & groups[j] for i in range(3) for j in range(i)):
        raise ValueError("Training, validation and retention sample IDs must be disjoint")
    # Also reject identical content renamed to a different sample ID.
    signatures = [{encode({"inputs": r["inputs"], "target": r["target"]}) for r in rows}
                  for rows in (training, validation, retention)]
    if any(signatures[i] & signatures[j] for i in range(3) for j in range(i)):
        raise ValueError("Identical examples cannot cross evaluation partitions")
    before = store.model(name, owner_id)
    previous = initial_artifact if before is None else before["artifact"]
    baseline_loss = _loss(previous, validation, predictor)
    baseline_retention = _loss(previous, retention, predictor)
    started = time.monotonic()
    candidate = trainer(copy.deepcopy(training))
    encode(candidate)
    loss = _loss(candidate, validation, predictor)
    retained = _loss(candidate, retention, predictor)
    passed = loss <= policy["max_validation_error"] and baseline_loss - loss >= policy["min_gain"]
    retention_passed = retained <= baseline_retention + policy["max_forgetting"]
    metrics = {"passed": passed, "retention_passed": retention_passed,
               "validation_mse": loss, "previous_validation_mse": baseline_loss,
               "retention_mse": retained, "previous_retention_mse": baseline_retention,
               "train_examples": len(training), "validation_examples": len(validation),
               "retention_examples": len(retention), "seconds": time.monotonic() - started,
               "policy_sha256": hashlib.sha256(encode(policy).encode()).hexdigest(),
               "protocol_id": policy["protocol_id"]}
    validation_id = store.record(conversation_id, "test_result", {
        "metrics": metrics, "sample_ids": sorted(groups[1] | groups[2]),
        "validation": validation, "retention": retention, "policy": policy,
        "candidate_sha256": hashlib.sha256(encode(candidate).encode()).hexdigest()},
        sorted(groups[1] | groups[2]), owner_id=owner_id, status="verified", evidence="experiment")
    metrics["validation_id"] = validation_id
    version = store.register_model(name, candidate, [r["record_id"] for r in training], metrics,
                                   owner_id=owner_id, activate=passed and retention_passed)
    return {"status": "adopted" if passed and retention_passed else "rejected",
            "weights_updated": passed and retention_passed, "model_version": version,
            "previous_version": before["id"] if before else None, "metrics": metrics,
            "selected_ids": [r["record_id"] for r in training]}
