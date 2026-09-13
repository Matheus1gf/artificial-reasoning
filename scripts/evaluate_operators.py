#!/usr/bin/env python3
"""Registered, bounded own-network/operator/invention evaluation; no Qwen."""
import argparse
from collections import defaultdict
import hashlib
import json
import math
from pathlib import Path
import platform
import random
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.operators import TransitionNetwork, fit_operator, select_example, synthesize
from src.cognition.sandbox import execute_program
from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.chat.provider import Settings
from src.science.numerics import least_squares as qr_least_squares


PROTOCOL = {
    "id": "learned-operators-pilot-v2", "seeds": [17, 29, 47], "examples": [1, 2, 4, 8, 16], "noise_sigma": [0, 0.1, 0.5],
    "amendment": "After v1 results, add a same-polynomial-basis QR comparator so a supplied x^2 feature is not mistaken for a neural advantage. All v1/v2 outputs are preserved. This is expanded pilot analysis on already-observed cases, not a fresh blind test.",
    "functions": {"affine": [[2, 1], [-2, 3], [3, -2], [1, 4]], "quadratic": [[1, 0], [-1, 2]], "piecewise": [[2, 1], [-1, 2]]},
    "training_domain": "distinct integer x sampled without replacement from [-8,8]",
    "held_out_inputs": [-7.5, -6.5, -5.5, -4.5, -3.5, -2.5, -1.5, -0.5, 0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5, 7.5],
    "split": "Per-task adaptation on integer inputs; scoring at disjoint half integers. New function families are structural transfer tests, not F00 reserved families.",
    "network": {"initialization": "project seeded random, no pretrained weights or metatraining", "architecture": "one linear neuron over supplied degree 1 or 2 polynomial features", "loss": "MSE", "epochs": 300, "learning_rate": 0.15},
    "comparators": ["exact memory with abstention", "nearest neighbour", "least-squares affine", "least-squares quadratic on identical features with rank-check abstention", "finite affine hypothesis grammar with abstention", "degree-1 neuron", "degree-2 neuron"],
    "metrics": ["held-out MSE", "coverage for abstaining comparators", "training loss curve", "training seconds", "parameters", "candidate count", "query reduction", "goal success", "false approval", "program actions and instructions", "distinct canonical mechanisms"],
    "active_query": {"strategies": ["active", "random", "smallest"], "prior_examples": 1, "queries": 1, "families": "all a in [-3,3], b in [-5,5]; noiseless finite affine grammar", "metric": "candidate-count reduction per supplied query; equal one-query budget"},
    "invention": {"cases": [[0, 5], [1, 6], [-1, 5], [2, 9], [3, 7], [0, 7]], "max_steps": 6, "max_operations": 2048,
                  "operators": "increment x+1 and double 2*x fitted independently from two observations each", "success": "independent DSL execution matches goal and all intermediate operator inputs inside [-20,20]"},
    "ablations": {"memory": "Discard previously supplied adaptation examples: retain latest x=0 observation only; report lost evidence explicitly.",
                  "neural": "Same examples, grammar, search and verification; no proposal network.",
                  "search": "Evaluate only zero/one action instead of composing; count unachieved multi-action goals.",
                  "verifier": "For 6 intentionally corrupted program candidates, compare approval without replay versus independent execution against target. Fault injection is not a measured natural error rate."},
    "decision_rules": {"network": "Keep as optional experiment unless median MSE beats least squares or verified success improves; negative results retained.",
                       "representations": "Report degree-1 transfer failure and effect of supplied degree-2 basis; do not call supplied basis a learned abstraction.",
                       "active": "Keep acquisition rule only as optional policy if it does not outperform same-budget alternatives.",
                       "memory_search_verifier": "Retain operational components if removing evidence, composition or checks reduces success or permits known-invalid artifacts."},
    "source_files": ["src/cognition/operators.py", "src/cognition/operator_runtime.py", "src/cognition/engine.py", "src/cognition/processor.py", "src/cognition/neural.py", "src/cognition/contracts.py", "src/cognition/store.py", "src/cognition/telemetry.py", "src/cognition/sandbox.py", "src/cognition/sandbox_worker.py", "src/chat/engine.py", "src/chat/discourse.py", "src/chat/domain.py", "src/chat/extraction.py", "src/chat/memory.py", "src/chat/reasoner.py", "src/chat/provider.py", "src/science/numerics.py", "experiments/cognition/intent-model.v1.json", "scripts/evaluate_operators.py"],
    "reproduction_note": "The v5 artifact directory reruns known pilot cases after conversational parsing/reasoning fixes; registration now also covers transitive chat dependencies, contracts, telemetry and the intent checkpoint. Old v1-v4 artifacts remain unchanged.",
    "limitations": ["Synthetic scalar tasks, not scientific discovery or general intelligence", "Affine grammar and polynomial bases supplied by programmer", "Three seeds per function and condition are repeated computational trials, not independent real-world populations", "No task-specific meta-training, no general model, no user data", "Novelty means new canonical function in local procedure memory only"]
}


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=False, allow_nan=False)
        stream.write("\n")


def target(family, parameters, x):
    a, b = parameters
    return a * (x if family == "affine" else x*x if family == "quadratic" else abs(x)) + b


def mse(expected, predicted):
    return sum((a-b)**2 for a, b in zip(expected, predicted)) / len(expected)


def least_squares(rows):
    xs, ys = [r["x"] for r in rows], [r["y"] for r in rows]
    mx, my = statistics.mean(xs), statistics.mean(ys)
    denominator = sum((x-mx)**2 for x in xs)
    a = sum((x-mx)*(y-my) for x, y in zip(xs, ys)) / denominator if denominator else 0
    return a, my-a*mx


def adaptation():
    runs = []
    for family, functions in PROTOCOL["functions"].items():
        for function_index, parameters in enumerate(functions):
            for seed in PROTOCOL["seeds"]:
                rng = random.Random(seed + 97 * function_index)
                pool = rng.sample(list(range(-8, 9)), 16)
                noise = [rng.gauss(0, 1) for _ in pool]
                for count in PROTOCOL["examples"]:
                    for sigma in PROTOCOL["noise_sigma"]:
                        rows = [{"x": x, "y": target(family, parameters, x) + sigma*noise[i], "id": "adapt-"+str(i)} for i, x in enumerate(pool[:count])]
                        xs = PROTOCOL["held_out_inputs"]
                        ys = [target(family, parameters, x) for x in xs]
                        a, b = least_squares(rows)
                        values = {"least_squares_affine": {"mse": mse(ys, [a*x+b for x in xs]), "coverage": 1.0},
                                  "nearest_neighbour": {"mse": mse(ys, [min(rows, key=lambda r: abs(r["x"]-x))["y"] for x in xs]), "coverage": 1.0},
                                  "exact_memory": {"mse": None, "coverage": 0.0}}
                        try:
                            coefficients = qr_least_squares([[1, row["x"], row["x"]**2] for row in rows], [row["y"] for row in rows])["coefficients"]
                            values["least_squares_quadratic"] = {"mse": mse(ys, [sum(c*x**i for i, c in enumerate(coefficients)) for x in xs]), "coverage": 1.0}
                        except ValueError:
                            values["least_squares_quadratic"] = {"mse": None, "coverage": 0.0, "reason": "unidentifiable coefficients with supplied observations"}
                        grammar = fit_operator(rows, use_neural=False, tolerance=min(1.0, sigma * 3))
                        predictions = []
                        covered = []
                        for x, y in zip(xs, ys):
                            possibilities = {c["a"]*x+c["b"] for c in grammar["candidates"]}
                            if len(possibilities) == 1:
                                predictions.append(possibilities.pop()); covered.append(y)
                        values["finite_affine"] = {"mse": mse(covered, predictions) if covered else None,
                                                  "coverage": len(covered)/len(xs), "candidate_count": len(grammar["candidates"])}
                        for degree in (1, 2):
                            model = TransitionNetwork(seed, degree)
                            before = mse(ys, [model.predict(x) for x in xs])
                            started = time.perf_counter()
                            artifact = model.fit(rows)
                            values["neuron_degree_" + str(degree)] = {"before_mse": before, "mse": mse(ys, [model.predict(x) for x in xs]),
                                "coverage": 1.0, "seconds": time.perf_counter()-started, "artifact": artifact,
                                "training_samples": len(rows), "prior_training_samples": 0, "parameter_count": len(model.weights)}
                        runs.append({"family": family, "function": parameters, "seed": seed, "examples": count, "noise_sigma": sigma,
                                     "training": rows, "held_out": {"x": xs, "y": ys}, "comparators": values})
    return runs


def active_selection():
    runs = []
    for seed in PROTOCOL["seeds"]:
        for a in range(-3, 4):
            for b in range(-5, 6):
                initial_x = random.Random(seed+a*17+b).choice(list(range(-3, 4)))
                row = {"x": initial_x, "y": a*initial_x+b, "id": "initial"}
                fit = fit_operator([row], use_neural=False)
                for strategy in PROTOCOL["active_query"]["strategies"]:
                    x = select_example(fit["candidates"], [row], strategy, seed)
                    updated = fit_operator([row, {"x": x, "y": a*x+b, "id": "query"}], use_neural=False) if x is not None else fit
                    runs.append({"seed": seed, "a": a, "b": b, "strategy": strategy, "query": x,
                                 "before": len(fit["candidates"]), "after": len(updated["candidates"]),
                                 "reduction": len(fit["candidates"])-len(updated["candidates"])})
    return runs


def invention():
    examples = {"increment": [{"x": 1, "y": 2}, {"x": 0, "y": 1}], "double": [{"x": 1, "y": 2}, {"x": 0, "y": 0}]}
    runs = []
    for initial, goal in PROTOCOL["invention"]["cases"]:
        for condition in ("full", "without_memory", "without_neural", "without_search"):
            started = time.perf_counter()
            fitted = {name: fit_operator(rows[-1:] if condition == "without_memory" else rows, use_neural=condition != "without_neural") for name, rows in examples.items()}
            result = synthesize(initial, goal, fitted, max_steps=1 if condition == "without_search" else 6)
            runs.append({"initial": initial, "goal": goal, "condition": condition, "seconds": time.perf_counter()-started,
                         "status": result["status"], "success": result.get("verification", {}).get("passed", False), "result": result})
    fault_trials = []
    for initial, goal in PROTOCOL["invention"]["cases"]:
        # A generated candidate claiming the correct target while its executable
        # constant is off by one. This tests verification, not the model's natural error frequency.
        program = [{"op": "const", "value": goal+1}, {"op": "store", "name": "x"}, {"op": "load", "name": "x"}]
        result = execute_program(program, {"x": initial})
        approved = result.get("status") == "completed" and math.isclose(result["values"]["x"], goal, abs_tol=1e-9, rel_tol=0)
        fault_trials.append({"initial": initial, "goal": goal, "program": program, "without_verifier_approved": True,
                             "with_verifier_approved": approved, "observed": result["values"]["x"]})
    return {"runs": runs, "verifier_fault_injection": fault_trials}


def chat_workflow():
    memory = Memory(":memory:")
    engine = ChatEngine(memory, Settings(research_mode=True))
    cid = memory.create_conversation()["id"]
    requests = [
        {"task": "learn_operator", "name": "increment", "examples": [{"x": 0, "y": 1}]},
        {"task": "learn_operator", "name": "increment", "examples": [{"x": 1, "y": 2}]},
        {"task": "learn_operator", "name": "double", "examples": [{"x": 0, "y": 0}, {"x": 1, "y": 2}]},
        {"task": "invent", "initial": 1, "target": 6, "operators": ["increment", "double"], "alternative_initials": [0, 2]},
        {"task": "invent", "initial": 2, "target": 10, "operators": ["increment", "double"]},
        {"task": "invent", "initial": 1, "target": 6, "operators": ["increment", "double"]},
        {"task": "test_operator", "name": "increment", "examples": [{"x": 2, "y": 4}]},
        {"task": "learn_operator", "name": "increment", "examples": [{"x": 0, "y": 1}, {"x": 1, "y": 2}]},
        {"task": "invent", "initial": 1, "target": 6, "operators": ["increment", "double"]},
    ]
    runs = []
    try:
        for index, request in enumerate(requests):
            result = engine.reply(cid, json.dumps(request), request_id="registered-pilot-"+str(index))
            runs.append({"request": request, "answer": result["answer_package"], "model_calls": result["reasoning"]["model_calls"],
                         "resources": result["reasoning"]["resources"]})
        records = engine.experience_store.export()["records"]
        return {"runs": runs, "records": records,
                "checks": {"initially_ambiguous": runs[0]["answer"]["status"] == "ambiguous",
                           "learned_after_second_example": runs[1]["answer"]["status"] == "answered",
                           "invention_verified": runs[3]["answer"]["status"] == "answered",
                           "composed_unseen_goal": runs[4]["answer"]["status"] == "answered",
                           "repeat_not_novel": runs[5]["answer"]["calculations"][0]["metrics"]["novel_to_memory"] is False,
                           "counterexample_refutes_family": runs[6]["answer"]["status"] == "unknown",
                           "old_examples_do_not_erase_failure": runs[7]["answer"]["status"] == "unknown",
                           "failed_operator_blocks_new_invention": runs[8]["answer"]["status"] != "answered",
                           "no_general_model_calls": all(r["model_calls"] == 0 for r in runs)}}
    finally:
        engine.close(); memory.close()


def summarize(runs):
    groups = defaultdict(list)
    for run in runs:
        for name, result in run["comparators"].items():
            groups[(run["family"], run["examples"], run["noise_sigma"], name)].append(result)
    summaries = []
    for (family, count, noise, name), values in groups.items():
        errors = [v["mse"] for v in values if v["mse"] is not None]
        summaries.append({"family": family, "examples": count, "noise_sigma": noise, "comparator": name, "runs": len(values),
                          "mean_mse": statistics.mean(errors) if errors else None, "median_mse": statistics.median(errors) if errors else None,
                          "min_mse": min(errors) if errors else None, "max_mse": max(errors) if errors else None,
                          "mean_coverage": statistics.mean(v["coverage"] for v in values)})
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error("Escolha um diretório novo; protocolo e resultados anteriores são preservados.")
    args.output_dir.mkdir(parents=True)
    write_new(args.output_dir / "protocol.json", PROTOCOL)
    write_new(args.output_dir / "registration.json", {"created_unix": time.time(), "protocol_sha256": hashlib.sha256((args.output_dir / "protocol.json").read_bytes()).hexdigest(),
              "source_sha256": {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in PROTOCOL["source_files"]},
              "python": platform.python_version(), "platform": platform.platform(), "started_scoring": False})
    started = time.perf_counter()
    runs = adaptation()
    active = active_selection()
    invented = invention()
    workflow = chat_workflow()
    report = {"protocol": PROTOCOL["id"], "adaptation": runs, "summary": summarize(runs), "active_selection": active,
              "invention": invented, "chat_workflow": workflow, "seconds": time.perf_counter()-started, "qwen_calls": 0, "network_calls": 0}
    write_new(args.output_dir / "results.json", report)
    print(json.dumps({"output": str(args.output_dir.resolve()), "adaptation_cases": len(runs), "active_trials": len(active),
                      "invention_trials": len(invented["runs"]), "workflow": workflow["checks"], "seconds": report["seconds"]}, indent=2))


if __name__ == "__main__":
    main()
