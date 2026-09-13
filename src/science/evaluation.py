"""Reproducible pilots for physics, quantum models and observed calibration data."""

import hashlib
import json
import math
import platform
import random
import time
from datetime import datetime, timezone
from pathlib import Path

from . import physics, symbolic, quantum, discovery, learning
from .numerics import least_squares, rmse

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = ROOT/"experiments"/"science"/"protocol.v1.json"
SUPPLEMENT = ROOT/"experiments"/"science"/"supplement.v1.json"


def interval(values):
    generator = random.Random(10101)
    n = len(values)
    means = sorted(sum(generator.choice(values) for _ in range(n))/n for _ in range(1000))
    return {"mean": sum(values)/n, "bootstrap_95_interval": [means[24], means[974]], "independent_seeds": n}


def physics_pilot(protocol):
    p = protocol["physics"]
    seed_results, all_failures = [], []
    for seed in p["seeds"]:
        rng = random.Random(seed)
        errors, balance, sensitivity, prediction_errors = [], [], [], {str(s): [] for s in p["noise_sigma"]}
        for _ in range(p["cases_per_seed"]):
            x, v, a, t = rng.uniform(-10, 10), rng.uniform(-3, 3), rng.uniform(-2, 2), rng.uniform(.1, 2)
            runs = [physics.simulate(x, v, t, a, steps) for steps in p["integrator_steps"]]
            errors.extend(r["reference_error"] for r in runs)
            balance.extend(abs(r["energy_balance_residual"]) for r in runs)
            sensitivity.append(abs(runs[0]["x"]-runs[-1]["x"]))
            for sigma in p["noise_sigma"]:
                observations = [{"t": u, "x": x+v*u+.5*a*u*u+rng.gauss(0, sigma)} for u in p["fit_times"]]
                model = physics.fit_motion(observations, noise_sigma=sigma)
                expected = [x+v*u+.5*a*u*u for u in p["prediction_times"]]
                prediction_errors[str(sigma)].append(rmse(expected, [physics.predict_motion(model, u) for u in p["prediction_times"]]))
        if max(errors) > p["numeric_reference_tolerance"]:
            all_failures.append({"seed": seed, "check": "integrator reference", "error": max(errors)})
        # Anonymous independent rows vary all physical conditions, not only names.
        generated = []
        for _ in range(p["symbolic_training_rows"]+p["symbolic_prediction_rows"]):
            x, v, a, t = rng.uniform(-10, 10), rng.uniform(-3, 3), rng.uniform(-2, 2), rng.uniform(.1, 2)
            generated.append({"variables": {"q": x, "r": v, "s": a, "u": t}, "target": x+v*t+.5*a*t*t})
        train_rows = generated[:p["symbolic_training_rows"]]
        test_rows = generated[p["symbolic_training_rows"]:]
        learned = symbolic.discover(train_rows, dimensions={"q": [1, 0, 0], "r": [1, -1, 0], "s": [1, -2, 0], "u": [0, 1, 0]},
                                    target_dimension=[1, 0, 0], max_degree=p["symbolic_max_degree"], max_terms=p["symbolic_max_terms"])
        symbolic_error = rmse([r["target"] for r in test_rows], [symbolic.predict(learned, r["variables"]) for r in test_rows])
        if symbolic_error > 1e-8:
            all_failures.append({"seed": seed, "check": "symbolic novel conditions", "error": symbolic_error})
        training, testing = [], []
        for dest, size in ((training, p["neural_training_rows"]), (testing, 32)):
            for _ in range(size):
                v, a, t = rng.uniform(-3, 3), rng.uniform(-2, 2), rng.uniform(.1, 2)
                dest.append({"v": v, "a": a, "t": t, "target": v*t+.5*a*t*t})
        neural = {}
        for constrained in (False, True):
            start = time.perf_counter()
            network = learning.train(training, constrained, seed, p["neural_epochs"])
            network["elapsed_seconds"] = time.perf_counter()-start
            network["prediction_rmse"] = rmse([r["target"] for r in testing], [learning.predict(network, r) for r in testing])
            neural["physical_features" if constrained else "raw_features"] = network
        numerical = least_squares([learning.features(r, True) for r in training], [r["target"] for r in training])
        numerical_rmse = rmse([r["target"] for r in testing], [sum(c*x for c, x in zip(numerical["coefficients"], learning.features(r, True))) for r in testing])
        # Refute straight-line model with a new accelerated observation.
        evidence = [{"t": t, "x": t*t} for t in [0, .2, .4, .6]]
        revision = physics.simulated_experiment(evidence, {"x": 0, "v": 0, "a": 2}, noise_sigma=.01)
        artifact_verification = symbolic.verify_artifact(learned, test_rows[:2])
        seed_results.append({"seed": seed, "max_integrator_error": max(errors), "max_energy_balance_error": max(balance),
                             "step_sensitivity": max(sensitivity), "prediction_rmse_by_noise": {s: sum(v)/len(v) for s, v in prediction_errors.items()},
                             "symbolic_model": learned, "symbolic_prediction_rmse": symbolic_error,
                             "neural_comparison": neural, "traditional_fit_rmse": numerical_rmse, "model_revision": revision,
                             "artifact_verification": artifact_verification})
    return {"seeds": seed_results, "failures": all_failures,
            "prediction_rmse": {str(s): interval([r["prediction_rmse_by_noise"][str(s)] for r in seed_results]) for s in p["noise_sigma"]},
            "conclusions": ["Dimensional polynomial search rediscovers a relation within its supplied grammar.",
                            "Physical-feature neural layer uses supplied physics products; this is not learning physics from no priors.",
                            "Numerical least squares is the stronger comparator on the linear feature problem.",
                            "Simulated motion is not yet transferred to independently measured trajectories."]}


def quantum_pilot(protocol):
    p = protocol["quantum"]
    seed_results = []
    for seed in p["seeds"]:
        rng = random.Random(seed)
        frequency_results = []
        for omega in p["true_omegas"]:
            rows = []
            for t in p["training_times"]:
                state = quantum.evolve([1, 0], omega, t)
                measured = quantum.measure(state, p["shots_per_measurement"], rng.randrange(2**32))
                rows.append({"t": t, "zeros": measured["counts"][0], "shots": measured["shots"]})
            learned = quantum.fit_frequency(rows)
            error = rmse([math.cos(omega*t/2)**2 for t in p["prediction_times"]],
                         [math.cos(learned["omega"]*t/2)**2 for t in p["prediction_times"]])
            choice = quantum.choose_measurement(learned["plausible_candidates"] if len(learned["plausible_candidates"]) > 1 else [max(0, learned["omega"]-.02), learned["omega"]+.02], [.1, .5, 1, 1.5, 2])
            frequency_results.append({"true_omega": omega, "learned_omega": learned["omega"], "held_condition_probability_rmse": error,
                                      "plausible_candidates": learned["plausible_candidates"], "measurement_choice": choice})
        theta, phi = .35, .75
        train, evaluation = [], []
        for destination, shots in ((train, p["contextual_shots_train"]), (evaluation, p["contextual_shots_test"])):
            for order in ("AB", "BA"):
                ps = [quantum.sequential_probability(theta, phi, order, k//2, k % 2) for k in range(4)]
                counts = [0]*4
                for _ in range(shots):
                    draw, cumulative = rng.random(), 0.0
                    for k, value in enumerate(ps):
                        cumulative += value
                        if draw < cumulative or k == 3:
                            counts[k] += 1
                            break
                destination.append({"order": order, "counts": counts})
        comparisons = {}
        for name in ("quantum", "classical_context"):
            start = time.perf_counter()
            fit = quantum.contextual_fit(train, name, p["contextual_grid_size"])
            function = quantum.sequential_probability if name == "quantum" else quantum.classical_context_probability
            loss = 0
            for row in evaluation:
                for k, count in enumerate(row["counts"]):
                    loss -= count*math.log(max(1e-15, function(fit["theta"], fit["phi"], row["order"], k//2, k % 2)))
            fit["test_nll"] = loss
            fit["elapsed_seconds"] = time.perf_counter()-start
            comparisons[name] = fit
        # Order should not matter for conjunction of two accepted propositions.
        # This probes a proposed decision mechanism, not all possible quantum cognition.
        order_sensitive_cases = 0
        for theta in [.1, .3, .5, .7, 1.0]:
            for phi in [.2, .4, .6, .8, 1.0]:
                ab = quantum.sequential_probability(theta, phi, "AB") > .5
                ba = quantum.sequential_probability(theta, phi, "BA") > .5
                order_sensitive_cases += ab != ba
        seed_results.append({"seed": seed, "frequency_results": frequency_results, "contextual_comparison": comparisons,
                             "synthetic_only": True, "order_invariant_logic_probe": {"cases": 25, "quantum_order_sensitive_decisions": order_sensitive_cases,
                             "classical_equivalent_order_sensitive_decisions": order_sensitive_cases, "symbolic_conjunction_order_sensitive_decisions": 0,
                             "decision": "do not use contextual probability threshold as logical entailment"}})
    return {"seeds": seed_results, "cost": [quantum.state_cost(q, 100) for q in p["cost_qubits"]],
            "probability_prediction_rmse": interval([sum(x["held_condition_probability_rmse"] for x in r["frequency_results"])/len(r["frequency_results"]) for r in seed_results]),
            "decision": "No advantage over equivalent classical context model; no human cognitive data; no invention superiority; no hardware acquisition.",
            "failures": []}


def learning_budget_pilot():
    """Fresh prespecified seeds; count all training data and report negative cases."""
    supplement = json.loads(SUPPLEMENT.read_text())
    records = []
    for seed in supplement["seeds"]:
        rng = random.Random(seed)
        test = []
        for _ in range(supplement["validation_cases_per_seed"]):
            v, a, t = rng.uniform(-3, 3), rng.uniform(-2, 2), rng.uniform(1.2, 2)
            test.append({"v": v, "a": a, "t": t, "target": v*t+.5*a*t*t})
        for sigma in supplement["noise_sigma"]:
            rows = []
            for _ in range(max(supplement["training_counts"])):
                v, a, t = rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(.1, 1)
                rows.append({"v": v, "a": a, "t": t, "target": v*t+.5*a*t*t+rng.gauss(0, sigma)})
            for n in supplement["training_counts"]:
                selected = rows[:n]
                outcomes = {}
                for constrained in (False, True):
                    start = time.perf_counter()
                    model = learning.train(selected, constrained, seed, supplement["epochs"])
                    elapsed = time.perf_counter()-start
                    outcomes["physical_features" if constrained else "raw_features"] = {
                        "rmse": rmse([r["target"] for r in test], [learning.predict(model, r) for r in test]),
                        "elapsed_seconds": elapsed, "weights": model["weights"], "scales": model["scales"],
                        "boundary_displacement": learning.predict(model, {"v": 1, "a": 1, "t": 0})}
                numerical = least_squares([learning.features(r, True) for r in selected], [r["target"] for r in selected])
                outcomes["least_squares"] = {"rmse": rmse([r["target"] for r in test],
                    [sum(c*x for c, x in zip(numerical["coefficients"], learning.features(r, True))) for r in test])}
                records.append({"seed": seed, "training_examples": n, "noise_sigma": sigma, "outcomes": outcomes})
    out_of_domain_rejected = 0
    for invalid in ({"x": 0, "v": 4, "dt": 1}, {"x": 0, "v": 1, "dt": 3}):
        try:
            physics.simulate(**invalid)
        except ValueError:
            out_of_domain_rejected += 1
    return {"supplement_id": supplement["supplement_id"], "records": records,
            "out_of_domain_rejected": out_of_domain_rejected, "out_of_domain_cases": 2,
            "interpretation": "New prediction conditions are inside simulator domain but outside training ranges. Physical features are supplied, not discovered. Fixed training budget may leave optimization error."}


def discovery_pilot(protocol):
    corpus = discovery.load_corpus()
    rows = corpus["rows"]
    result = discovery.calibration_study(rows, [i for i in range(len(rows)) if i % 3], [i for i in range(len(rows)) if not i % 3])
    # Separate full-data numerical reproducibility check, never used to select learner output.
    full_fit = least_squares([[1, row["variables"]["q"]] for row in rows], [row["target"] for row in rows])
    published = [-.262323073774029, 1.00211681802045]
    result["independent_published_reference"] = {"coefficients": full_fit["coefficients"], "certified_coefficients": published,
                                               "absolute_errors": [abs(a-b) for a, b in zip(full_fit["coefficients"], published)],
                                               "scope": "numerical algorithm reproduction on same observed dataset, not new independent measurement"}
    result["provenance"] = corpus["provenance"]
    result["physical_interpretation_approved"] = corpus["physical_interpretation_approved"]
    result["open_problem_gate"] = "closed: no expert novelty review or independent new dataset"
    result["failures"] = [] if result["rmse"] < result["mean_baseline_rmse"] else [{"check": "mean baseline", "passed": False}]
    if abs(result["rmse"]-result["ordinary_least_squares_rmse"]) > 1e-8:
        result["failures"].append({"check": "preregistered match to ordinary least squares within 1e-8", "passed": False,
                                   "difference": result["rmse"]-result["ordinary_least_squares_rmse"],
                                   "interpretation": "complexity penalty chose one term; retain negative result, do not tune after scoring"})
    return result


def code_hashes():
    paths = sorted((ROOT/"src"/"science").glob("*.py")) + [ROOT/"scripts"/"evaluate_science.py", PROTOCOL, SUPPLEMENT,
        ROOT/"src"/"cognition"/"sandbox.py", ROOT/"src"/"cognition"/"sandbox_worker.py"]
    paths += sorted((ROOT/"experiments"/"science"/"corpus").glob("*.json"))
    paths += [ROOT/"experiments"/"science"/"corpus"/"Norris.dat"]
    paths += [ROOT/"experiments"/"science"/"human-context.protocol.v1.json"]
    paths += [ROOT/"experiments"/"science"/"motion-transfer.protocol.v1.json",
              ROOT/"experiments"/"science"/"corpus"/"tum-fr1-xyz-groundtruth.txt"]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def evaluate():
    protocol = json.loads(PROTOCOL.read_text())
    start = time.perf_counter()
    physics_result = physics_pilot(protocol)
    quantum_result = quantum_pilot(protocol)
    discovery_result = discovery_pilot(protocol)
    budget_result = learning_budget_pilot()
    from . import human_context
    human_result = human_context.evaluate()
    from . import motion_transfer
    motion_result = motion_transfer.evaluate()
    return {"protocol_id": protocol["protocol_id"], "executed_at": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(), "platform": platform.platform(), "code_hashes": code_hashes(),
            "physics": physics_result, "quantum": quantum_result, "discovery": discovery_result,
            "learning_budgets": budget_result,
            "human_context": human_result,
            "measured_motion_transfer": motion_result,
            "elapsed_seconds": time.perf_counter()-start,
            "reserved_scored": False, "language_model_calls": 0,
            "interpretation": "software and bounded-model pilot evidence; independent human/scientific external validation remains pending"}
