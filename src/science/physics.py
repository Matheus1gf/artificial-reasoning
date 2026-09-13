"""A declared one-dimensional Newtonian laboratory, not a universal simulator."""

import math

from .numerics import bounded, finite, integer, least_squares

UNITS = {"x": "m", "v": "m/s", "a": "m/s^2", "dt": "s", "mass": "kg"}
DIMENSIONS = {"1": (0, 0, 0), "m": (1, 0, 0), "s": (0, 1, 0),
              "kg": (0, 0, 1), "m/s": (1, -1, 0), "m/s^2": (1, -2, 0),
              "N": (1, -2, 1), "J": (2, -2, 1)}


def check_units(supplied, expected):
    if not isinstance(supplied, dict):
        raise ValueError("units must be an object")
    for key, unit in supplied.items():
        if key not in expected or unit != expected[key]:
            raise ValueError("unsupported or incompatible unit for " + key)
    return True


def dimension(expression, _depth=0):
    """Evaluate a dimension AST: unit string or {op,left,right}; never eval()."""
    if _depth > 16:
        raise ValueError("dimension expression exceeds depth limit")
    if isinstance(expression, str):
        if expression not in DIMENSIONS:
            raise ValueError("unknown physical unit")
        return DIMENSIONS[expression]
    if not isinstance(expression, dict):
        raise ValueError("dimension expression must be a unit or operation")
    left, right = dimension(expression["left"], _depth+1), dimension(expression["right"], _depth+1)
    op = expression["op"]
    if op in ("add", "subtract"):
        if left != right:
            raise ValueError("addition requires equal dimensions")
        return left
    if op not in ("multiply", "divide"):
        raise ValueError("unknown dimension operation")
    sign = 1 if op == "multiply" else -1
    return tuple(a+sign*b for a, b in zip(left, right))


def simulate(x, v, dt, a=0.0, steps=32, mass=1.0, units=None):
    """Midpoint integration under constant prescribed external acceleration."""
    check_units({} if units is None else units, UNITS)
    x = bounded(x, -10, 10, "initial x")
    v = bounded(v, -3, 3, "initial v")
    dt = bounded(dt, .1, 2, "dt")
    a = bounded(a, -2, 2, "a")
    mass = bounded(mass, 1e-6, 1e6, "mass")
    steps = integer(steps, 1, 10000, "steps")
    initial_x, initial_v, h = x, v, dt/steps
    for _ in range(steps):
        half_v = v+.5*a*h
        x += half_v*h
        v = half_v+.5*a*h
    # Independent closed-form oracle, not a second invocation of the integrator.
    reference_x = initial_x+initial_v*dt+.5*a*dt*dt
    reference_v = initial_v+a*dt
    error = max(abs(x-reference_x), abs(v-reference_v))
    energy_change = .5*mass*(v*v-initial_v*initial_v)
    external_work = mass*a*(x-initial_x)
    return {"x": x, "v": v, "dt": dt, "a": a,
            "kinetic_energy_change": energy_change, "external_work": external_work,
            "energy_balance_residual": energy_change-external_work,
            "reference_error": error, "verified": error < 1e-9,
            "steps": steps, "units": dict(UNITS, kinetic_energy_change="J", external_work="J"),
            "assumptions": ["point particle, one dimension", "constant prescribed acceleration",
                            "no collision or drag", "external work belongs to energy balance"],
            "domain": {"initial_x": [-10, 10], "initial_v": [-3, 3], "dt": [.1, 2], "a": [-2, 2]}}


def fit_motion(observations, degree=2, noise_sigma=0.0):
    """Infer x0,v0,(a) solely from position-time observations; v is unobserved."""
    integer(degree, 1, 2, "degree")
    noise_sigma = bounded(noise_sigma, 0, 10, "noise_sigma")
    if not isinstance(observations, list) or not degree+2 <= len(observations) <= 1000:
        raise ValueError("at least degree+2 and at most 1000 observations required")
    points = [(bounded(p["t"], 0, 2, "observation time"), finite(p["x"], "observed x")) for p in observations]
    design = [[t**power for power in range(degree+1)] for t, _ in points]
    fit = least_squares(design, [x for _, x in points])
    params = {"x0": fit["coefficients"][0], "v0": fit["coefficients"][1],
              "a": 2*fit["coefficients"][2] if degree == 2 else 0.0}
    fit.update({"parameters": params, "degree": degree, "noise_sigma": noise_sigma,
                "compatible": fit["rmse"] <= max(1e-9, 3*noise_sigma),
                "units": {"x0": "m", "v0": "m/s", "a": "m/s^2", "rmse": "m"},
                "identifiability": "full column rank under selected polynomial model",
                "uncertainty": "residual scale is not a posterior probability; alternatives outside grammar remain possible",
                "observation_domain": [min(t for t, _ in points), max(t for t, _ in points)]})
    return fit


def predict_motion(model, t):
    t = bounded(t, 0, 2, "prediction time")
    p = model["parameters"]
    return finite(p["x0"])+finite(p["v0"])*t+.5*finite(p["a"])*t*t


def experiment(observations, observation, degree=1, noise_sigma=0.0):
    """Predict a new observation, retain a refutation, then fit a broader model."""
    prior = fit_motion(observations, degree, noise_sigma)
    predicted = predict_motion(prior, observation["t"])
    actual = finite(observation["x"])
    error = abs(predicted-actual)
    rejected = error > max(1e-8, 3*noise_sigma)
    revised = fit_motion(observations+[observation], 2 if rejected else degree, noise_sigma)
    return {"prior": prior, "prediction": predicted, "observed": actual, "absolute_error": error,
            "refuted": rejected, "revised": revised,
            "negative_result": {"model_degree": degree, "prediction": predicted, "actual": actual,
                                "cause": "residual exceeds declared observation tolerance"} if rejected else None}


def simulated_experiment(observations, environment, times=None, noise_sigma=0.0):
    """Select an informative time, execute a separate simulator, revise candidates.

    Environment parameters are available to the executor only. Candidate fitting
    and time selection see observations, not the hidden environment parameters.
    """
    times = [1.6, 1.8, 2.0] if times is None else times
    if not isinstance(times, list) or not 1 <= len(times) <= 100:
        raise ValueError("1 to 100 experiment times required")
    times = [bounded(t, .1, 2, "experiment time") for t in times]
    candidates = [fit_motion(observations, degree, noise_sigma) for degree in (1, 2)]
    options = []
    for t in times:
        predictions = [predict_motion(model, t) for model in candidates]
        options.append({"t": t, "predictions": predictions, "disagreement": abs(predictions[0]-predictions[1])})
    selected = max(options, key=lambda item: item["disagreement"])
    simulation = simulate(dt=selected["t"], **environment)
    observed = {"t": selected["t"], "x": simulation["x"]}
    revision = experiment(observations, observed, degree=1, noise_sigma=noise_sigma)
    return {"selection": selected, "alternatives": options, "observation": observed,
            "executor_reference_error": simulation["reference_error"], "revision": revision,
            "data_kind": "simulated", "selection_policy": "maximal disagreement between supplied linear/quadratic model classes"}


def resolve(request):
    parameters = request.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    operation = request.get("operation")
    if operation == "simulate":
        result = simulate(**parameters)
        passed = result["verified"]
        sentences = ["No modelo de movimento 1D, a posição final é {:.8g} m e a velocidade final é {:.8g} m/s.".format(result["x"], result["v"])]
    elif operation == "fit":
        result = fit_motion(**parameters)
        passed = result["compatible"]
        sentences = ["O ajuste das observações retornou x0={x0:.8g} m, v0={v0:.8g} m/s e a={a:.8g} m/s².".format(**result["parameters"])]
    elif operation == "experiment":
        result = experiment(**parameters)
        passed = result["revised"]["compatible"]
        sentences = ["A nova observação {} a previsão do modelo anterior.".format("refutou" if result["refuted"] else "foi compatível com")]
    elif operation == "simulated_experiment":
        result = simulated_experiment(**parameters)
        passed = result["revision"]["revised"]["compatible"]
        sentences = ["O núcleo escolheu t={:.8g} s, executou o simulador e {} o modelo inicial.".format(result["selection"]["t"], "refutou" if result["revision"]["refuted"] else "manteve")]
    elif operation == "measured_transfer":
        if parameters:
            raise ValueError("measured_transfer uses the fixed registered protocol; parameters are not accepted")
        from .motion_transfer import evaluate
        result = evaluate()
        # A completed evaluation can validly reject its physical hypothesis.
        # Verify execution separately from the scientific promotion gate.
        passed = not result["sampling_failures"] and len(result["segments"]) == result["expected_segments"]
        sentences = ["A avaliação registrada da trajetória medida TUM {} a transferência do modelo de aceleração constante.".format("apoiou apenas localmente" if result["transfer_promoted"] else "rejeitou"),
                     "O resultado compara previsões com posições medidas e não estabelece uma nova lei física."]
        provenance = result["provenance"]
        return {"status": "answered" if passed else "unknown", "values": result,
                "sentences": sentences, "conclusions": sentences if passed else [],
                "units": {"position": "m", "time": "s", "rmse": "m", "velocity": "m/s", "acceleration": "m/s^2"},
                "premises": [{"source_url": provenance["source_url"], "kind": "measured_trajectory"},
                             {"source_url": provenance["paper_url"], "kind": "measurement_conditions"},
                             {"assumption": "Constant acceleration is a supplied local prediction hypothesis; applied forces are unobserved."}],
                "verification": {"passed": passed, "checks": ["source_checksum", "registered_temporal_split", "all_registered_segments_evaluated"],
                                 "physical_transfer_promoted": result["transfer_promoted"]},
                "limitations": result["limitations"]}
    elif operation == "symbolic":
        from .symbolic import discover
        result = discover(**parameters)
        passed = result["status"] == "identified"
        if passed:
            from .symbolic import verify_artifact
            result["artifact_verification"] = verify_artifact(result, parameters["samples"][:3])
            passed = result["artifact_verification"]["passed"]
        sentences = ["A busca na gramática polinomial encontrou: " + result.get("expression", "nenhum modelo identificável") + "."]
    elif operation == "dimensions":
        result = {"dimension": list(dimension(parameters["expression"]))}
        passed, sentences = True, ["A expressão é dimensionalmente compatível no sistema comprimento, tempo e massa."]
    else:
        raise ValueError("unknown physics operation")
    return {"status": "answered" if passed else "model_rejected", "values": result,
            "sentences": sentences, "conclusions": sentences,
            "units": result.get("units", {}),
            "premises": ["Laboratório Newtoniano 1D com domínio e unidades declarados."],
            "verification": {"passed": passed, "checks": [operation, "finite inputs", "declared model domain"]},
            "limitations": ["Modelo delimitado; validade numérica não prova a verdade física das premissas."] + result.get("limitations", [])}
