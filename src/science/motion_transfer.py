"""Registered falsification of local kinematics on an external measured trajectory.

The source contains observed poses, not force-controlled dynamics. Model failure
therefore rejects this local prediction model; it cannot establish a new law.
"""

import bisect
import hashlib
import json
import math
from pathlib import Path

from . import physics
from .numerics import least_squares, rmse

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT / "experiments/science/motion-transfer.protocol.v1.json"
METADATA = ROOT / "experiments/science/corpus/tum-fr1-xyz.metadata.v1.json"


def load_trajectory():
    """Validate the versioned primary-source bytes before producing observations."""
    metadata = json.loads(METADATA.read_text())
    raw = METADATA.parent / metadata["raw_filename"]
    data = raw.read_bytes()
    if hashlib.sha256(data).hexdigest() != metadata["sha256"]:
        raise ValueError("measured trajectory checksum mismatch")
    if metadata["units"] != {"timestamp": "s since Unix epoch", "x": "m", "y": "m", "z": "m", "quaternion": "dimensionless"}:
        raise ValueError("unsupported measured trajectory units")
    if metadata["dataset_kind"] != "measured":
        raise ValueError("trajectory is not identified as measured")
    rows = []
    for number, line in enumerate(data.decode("utf-8").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split()
        if len(fields) != 8:
            raise ValueError("trajectory row must contain eight numeric columns")
        values = [float(value) for value in fields]
        if not all(math.isfinite(value) for value in values):
            raise ValueError("nonfinite trajectory value")
        if rows and values[0] <= rows[-1]["timestamp"]:
            raise ValueError("trajectory timestamps must strictly increase")
        if abs(sum(value*value for value in values[4:])-1) > .002:
            raise ValueError("invalid recorded orientation norm")
        rows.append({"source_line": number, "timestamp": values[0],
                     "x": values[1], "y": values[2], "z": values[3]})
    if not 100 <= len(rows) <= 100000:
        raise ValueError("trajectory row count outside supported range")
    return rows, metadata


def sample_window(rows, start_s, protocol):
    """Decimate by timestamp alone; no selection based on measured coordinates."""
    timestamps = [row["timestamp"] for row in rows]
    anchor_index = bisect.bisect_left(timestamps, timestamps[0]+start_s)
    if anchor_index == len(rows):
        raise ValueError("window starts after trajectory")
    anchor = timestamps[anchor_index]
    selected = []
    for offset in protocol["sample_offsets_s"]:
        target = anchor+offset
        index = bisect.bisect_left(timestamps, target)
        candidates = [i for i in (index-1, index) if 0 <= i < len(rows)]
        chosen = min(candidates, key=lambda i: (abs(timestamps[i]-target), i))
        if abs(timestamps[chosen]-target) > protocol["max_association_error_s"]:
            raise ValueError("no observation within registered timestamp tolerance")
        if selected and chosen <= selected[-1]["index"]:
            raise ValueError("window reuses or reverses observations")
        selected.append(dict(rows[chosen], index=chosen, t=timestamps[chosen]-anchor,
                             requested_offset_s=offset,
                             association_error_s=abs(timestamps[chosen]-target)))
    return selected


def prediction_weights(training_times, prediction_time, degree):
    """OLS influence weights for a conditional deterministic error sensitivity."""
    design = [[t**power for power in range(degree+1)] for t in training_times]
    weights = []
    for index in range(len(design)):
        unit = [float(j == index) for j in range(len(design))]
        coefficients = least_squares(design, unit)["coefficients"]
        weights.append(sum(c*prediction_time**k for k, c in enumerate(coefficients)))
    return weights


def compare_segment(training, evaluation, protocol):
    """Fit on the training prefix; future measured values enter only scoring.

    Synthetic controls are analytic positions implied by that fit, used solely
    to separate integrator error from discrepancy against measured positions.
    """
    if len(training) != 10 or len(evaluation) != 10:
        raise ValueError("registered comparison requires 10 training and 10 future observations")
    times = [row["t"] for row in training+evaluation]
    if any(not math.isfinite(t) for t in times) or any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError("training and evaluation must be strictly chronological")
    if any(not math.isfinite(row["x"]) for row in training+evaluation):
        raise ValueError("observed coordinates must be finite")
    actual = [row["x"] for row in evaluation]
    outputs = {}
    for name, degree in (("constant_acceleration_midpoint", 2), ("constant_velocity_midpoint", 1)):
        model = physics.fit_motion(training, degree=degree)
        params = model["parameters"]
        predictions, controls, sensitivity = [], [], []
        try:
            for row in evaluation:
                result = physics.simulate(params["x0"], params["v0"], row["t"], params["a"],
                                          steps=protocol["integrator_steps"])
                predictions.append(result["x"])
                controls.append(abs(result["x"]-physics.predict_motion(model, row["t"])))
                weights = prediction_weights([p["t"] for p in training], row["t"], degree)
                sensitivity.append(protocol["source_reported_absolute_error_bound_m"]*(1+sum(abs(w) for w in weights)))
        except ValueError as exc:
            outputs[name] = {"status": "outside_simulator_domain", "parameters": params,
                             "reason": str(exc), "predictions": [], "training_rmse_m": model["rmse"]}
            continue
        errors = [abs(p-a) for p, a in zip(predictions, actual)]
        outputs[name] = {"status": "evaluated", "parameters": params,
                         "training_rmse_m": model["rmse"], "predictions": predictions,
                         "rmse_m": rmse(actual, predictions), "max_absolute_error_m": max(errors),
                         "synthetic_control_max_integrator_error_m": max(controls),
                         "conditional_position_error_budget_m": sensitivity,
                         "errors_exceeding_conditional_budget": sum(e > b for e, b in zip(errors, sensitivity))}
    persistence = [training[-1]["x"]]*len(evaluation)
    outputs["last_observation"] = {"status": "evaluated", "predictions": persistence,
                                   "rmse_m": rmse(actual, persistence),
                                   "max_absolute_error_m": max(abs(p-a) for p, a in zip(persistence, actual))}
    return {"training": training, "evaluation": evaluation, "models": outputs}


def evaluate():
    protocol = json.loads(PROTOCOL.read_text())
    rows, metadata = load_trajectory()
    segments, failures = [], []
    for start_s in protocol["window_starts_s"]:
        try:
            window = sample_window(rows, start_s, protocol)
        except ValueError as exc:
            failures.append({"window_start_s": start_s, "reason": str(exc)})
            continue
        for axis in protocol["axis_selection"]:
            observations = [{"t": row["t"], "x": row[axis], "source_line": row["source_line"]} for row in window]
            training = [observations[i] for i in protocol["training_indices"]]
            future = [observations[i] for i in protocol["evaluation_indices"]]
            comparison = compare_segment(training, future, protocol)
            comparison.update(axis=axis, window_start_s=start_s,
                              max_association_error_s=max(row["association_error_s"] for row in window))
            segments.append(comparison)
    summaries = {}
    for name in protocol["models"]:
        included = [s for s in segments if s["models"][name]["status"] == "evaluated"]
        observed = [p["x"] for s in included for p in s["evaluation"]]
        predicted = [p for s in included for p in s["models"][name]["predictions"]]
        # No exclusions are hidden: coverage is part of the promotion gate.
        summaries[name] = {"evaluated_segments": len(included), "excluded_segments": len(segments)-len(included),
                           "evaluated_future_positions": len(predicted),
                           "pooled_rmse_m": rmse(observed, predicted) if predicted else None,
                           "max_absolute_error_m": max((abs(a-b) for a, b in zip(observed, predicted)), default=None)}
    primary = summaries["constant_acceleration_midpoint"]
    baseline = summaries["last_observation"]
    criteria = protocol["promotion_gate"]
    expected = len(protocol["window_starts_s"])*len(protocol["axis_selection"])
    complete = not failures and primary["evaluated_segments"] == expected
    checks = {
        "all_segments_inside_simulator_domain": complete,
        "aggregate_rmse": primary["pooled_rmse_m"] is not None and primary["pooled_rmse_m"] <= criteria["aggregate_rmse_max_m"],
        "absolute_error": primary["max_absolute_error_m"] is not None and primary["max_absolute_error_m"] <= criteria["max_absolute_error_m"],
        "gain_vs_persistence": complete and primary["pooled_rmse_m"] <= baseline["pooled_rmse_m"]*(1-criteria["relative_rmse_gain_vs_last_observation_min"]),
    }
    promoted = all(checks.values())
    return {"protocol_id": protocol["protocol_id"], "dataset_kind": "measured", "provenance": metadata,
            "raw_rows": len(rows), "segments": segments, "sampling_failures": failures,
            "expected_segments": expected, "summary": summaries, "promotion_checks": checks,
            "transfer_promoted": promoted, "larger_problem_transfer_authorized": False,
            "decision": "bounded_local_compatibility_only" if promoted else "constant_acceleration_transfer_rejected",
            "negative_results": [{"axis": s["axis"], "window_start_s": s["window_start_s"],
                                  "model": s["models"]["constant_acceleration_midpoint"]}
                                 for s in segments if s["models"]["constant_acceleration_midpoint"].get("rmse_m", float("inf")) > criteria["aggregate_rmse_max_m"]],
            "new_physical_law": False, "language_model_calls": 0,
            "limitations": ["One public trajectory; axes and windows are correlated, not independent replications.",
                            "Forces and time-varying acceleration are unobserved; constant acceleration is a supplied local approximation.",
                            "Published error bounds are empirical setup summaries; per-pose covariance and timestamp uncertainty are unavailable.",
                            "Sensitivity budgets cover bounded position perturbations conditionally, not all model or timing errors.",
                            "A numerical control generated from the fit is not an independent physical observation.",
                            "Larger problems and open scientific novelty require additional independent evidence."]}
