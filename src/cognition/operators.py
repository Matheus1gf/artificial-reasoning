"""Learn bounded numeric transitions and synthesize executable compositions.

The affine hypothesis grammar is supplied; coefficients are learned from data.
Neural proposals are optional and never substitute for consistency checking.
User observations remain conditional premises, not verified physical laws.
"""
import hashlib
import json
import math
import random
from collections import deque

from .reasoning import Budget, Exhausted, integer, number, _symbol as symbol
from .sandbox import execute_program


PRIOR = "y=a*x+b; a integer [-3,3], b integer [-5,5]; x in [-20,20]"
VERSION = "affine-operator-1"


def observations(examples):
    if not isinstance(examples, list) or not 1 <= len(examples) <= 32:
        raise ValueError("Use de 1 a 32 transições {x,y,id opcional}.")
    rows = []
    for index, row in enumerate(examples):
        if not isinstance(row, dict) or set(row) - {"x", "y", "id"} or not {"x", "y"} <= set(row):
            raise ValueError("Transição exige x e y numéricos.")
        x, y = number(row["x"]), number(row["y"])
        if abs(x) > 20 or abs(y) > 100:
            raise ValueError("Domínio das transições: |x| ≤ 20 e |y| ≤ 100.")
        rid = symbol(row.get("id", "observation-" + str(index)))
        rows.append({"x": x, "y": y, "id": rid})
    if len({r["id"] for r in rows}) != len(rows):
        raise ValueError("IDs de observação repetidos.")
    return rows


class TransitionNetwork:
    """One own linear output neuron over a declared polynomial feature basis.

    No pretraining. Batch gradient descent on MSE, with normalized inputs.
    degree=2 changes the supplied representation, not a discovered abstraction.
    """
    def __init__(self, seed=17, degree=1):
        integer(seed, "seed", 0, 2 ** 32 - 1)
        integer(degree, "degree", 1, 2)
        self.seed, self.degree, self.scale = seed, degree, 1.0
        rng = random.Random(seed)
        self.weights = [rng.uniform(-0.1, 0.1) for _ in range(degree + 1)]
        self.loss_curve, self.training_ids = [], []

    def predict(self, x):
        z = number(x) / self.scale
        return sum(w * z ** i for i, w in enumerate(self.weights))

    def fit(self, examples, epochs=300, learning_rate=0.15):
        rows = observations(examples)
        integer(epochs, "epochs", 1, 1000)
        rate = number(learning_rate)
        if not 0 < rate <= 0.25:
            raise ValueError("Taxa de aprendizado fora de (0,0.25].")
        self.scale = max(1.0, max(abs(r["x"]) for r in rows))
        self.loss_curve = []
        for _ in range(epochs):
            gradient = [0.0] * len(self.weights)
            loss = 0.0
            for row in rows:
                z = row["x"] / self.scale
                error = self.predict(row["x"]) - row["y"]
                loss += error * error
                for i in range(len(gradient)):
                    gradient[i] += 2 * error * z ** i / len(rows)
            self.weights = [w - rate * g for w, g in zip(self.weights, gradient)]
            self.loss_curve.append(loss / len(rows))
        self.training_ids = [r["id"] for r in rows]
        return self.artifact()

    def artifact(self):
        return {"version": "transition-neuron-1", "seed": self.seed, "degree": self.degree,
                "scale": self.scale, "weights": list(self.weights), "training_ids": list(self.training_ids),
                "loss_curve": list(self.loss_curve), "prior": "polynomial features supplied; random initialized weights fitted by MSE"}


def fit_operator(examples, use_neural=True, max_operations=4096, tolerance=1e-9, seed=17):
    rows = observations(examples)
    if type(use_neural) is not bool:
        raise ValueError("use_neural deve ser booleano.")
    tolerance = number(tolerance)
    if not 0 <= tolerance <= 1:
        raise ValueError("Tolerância observacional deve estar entre 0 e 1.")
    integer(seed, "seed", 0, 2 ** 32 - 1)
    budget = Budget(max_operations)
    proposal, artifact = None, None
    if use_neural:
        network = TransitionNetwork(seed)
        artifact = network.fit(rows)
        proposal = {"a": round(network.weights[1] / network.scale), "b": round(network.weights[0])}
    grammar = [(a, b) for a in range(-3, 4) for b in range(-5, 6)]
    if proposal and (proposal["a"], proposal["b"]) in grammar:
        grammar.remove((proposal["a"], proposal["b"]))
        grammar.insert(0, (proposal["a"], proposal["b"]))
    candidates = []
    try:
        for a, b in grammar:
            error = 0.0
            for row in rows:
                budget.tick()
                residual = abs(a * row["x"] + b - row["y"])
                error = max(error, residual)
                if residual > tolerance + 1e-12:
                    break
            else:
                candidates.append({"a": a, "b": b, "max_residual": error, "complexity": int(a != 0) + int(b != 0)})
    except Exhausted:
        return {"status": "budget_exhausted", "candidates": [], "operations": budget.operations,
                "reason": "Busca incompleta; alternativas não examinadas impedem aprovação.", "prior": PRIOR}
    candidates.sort(key=lambda c: (c["complexity"], abs(c["a"]) + abs(c["b"]), c["a"], c["b"]))
    return {"version": VERSION, "status": "answered" if len(candidates) == 1 else "ambiguous" if candidates else "unknown",
            "candidates": candidates, "examples": rows, "tolerance": tolerance, "prior": PRIOR,
            "domain": [-20, 20], "neural_proposal": proposal, "neural_artifact": artifact,
            "neural_proposal_verified": bool(proposal and any(all(c[k] == proposal[k] for k in ("a", "b")) for c in candidates)),
            "operations": budget.operations, "next_query": select_example(candidates, rows),
            "verification": {"passed": True, "meaning": "all retained coefficients satisfy supplied observations within tolerance"}}


def select_example(candidates, examples, strategy="active", seed=17):
    if strategy not in {"active", "random", "smallest"}:
        raise ValueError("Estratégia de consulta inválida.")
    integer(seed, "seed", 0, 2 ** 32 - 1)
    if not candidates or len(candidates) == 1:
        return None
    used = {row["x"] for row in observations(examples)}
    available = [x for x in range(-5, 6) if x not in used]
    if not available:
        return None
    if strategy == "random":
        return random.Random(seed).choice(available)
    if strategy == "smallest":
        return min(available, key=lambda x: (abs(x), x))
    # Minimize expected posterior candidate count under a uniform version-space
    # prior. This is a declared acquisition criterion, not learned certainty.
    def score(x):
        groups = {}
        for model in candidates:
            prediction = model["a"] * x + model["b"]
            groups[prediction] = groups.get(prediction, 0) + 1
        return sum(n * n for n in groups.values()) / len(candidates), abs(x), x
    return min(available, key=score)


def predict_operator(model, x):
    x = number(x)
    if not -20 <= x <= 20:
        raise ValueError("Operador só pode ser aplicado em [-20,20].")
    validate_model(model)
    predictions = sorted({number(c["a"]) * x + number(c["b"]) for c in model["candidates"]})
    return {"status": "answered" if len(predictions) == 1 else "ambiguous" if predictions else "unknown", "x": x,
            "predictions": predictions, "candidate_count": len(model["candidates"]), "conditional": True}


def validate_model(model):
    """Check coefficients and their evidence independently of a neural score."""
    if not isinstance(model, dict) or model.get("version") != VERSION or not isinstance(model.get("candidates"), list) or len(model["candidates"]) > 77:
        raise ValueError("Modelo de transição inválido.")
    rows = observations(model.get("examples"))
    tolerance = number(model.get("tolerance"), "tolerance", 0, 1)
    seen = set()
    for candidate in model["candidates"]:
        if not isinstance(candidate, dict):
            raise ValueError("Candidato inválido.")
        a, b = number(candidate.get("a"), "a", -3, 3), number(candidate.get("b"), "b", -5, 5)
        if a != int(a) or b != int(b) or (a, b) in seen:
            raise ValueError("Coeficientes inteiros distintos exigidos pela família declarada.")
        seen.add((a, b))
        if any(abs(a * row["x"] + b - row["y"]) > tolerance + 1e-12 for row in rows):
            raise ValueError("Os coeficientes não passaram na conferência independente das observações.")
    return True


def program_for(sequence, models):
    program = []
    for name in sequence:
        validate_model(models[name])
        candidates = models[name]["candidates"]
        if len(candidates) != 1:
            raise ValueError("Um programa exige operadores identificados na família declarada.")
        model = candidates[0]
        program.extend([{"op": "load", "name": "x"}, {"op": "const", "value": model["a"]}, {"op": "mul"},
                        {"op": "const", "value": model["b"]}, {"op": "add"}, {"op": "store", "name": "x"}])
    program.append({"op": "load", "name": "x"})
    return program


def synthesize(initial, target, models, max_steps=6, max_operations=2048, known_signatures=None, cancel_event=None,
               templates=None, alternative_initials=None):
    """BFS over learned functions, verified by a separate finite DSL interpreter."""
    initial, target = number(initial), number(target)
    if not -20 <= initial <= 20 or not -100 <= target <= 100:
        raise ValueError("Estado inicial ou alvo fora do domínio.")
    integer(max_steps, "max_steps", 0, 10)
    if not isinstance(models, dict) or not 1 <= len(models) <= 8:
        raise ValueError("Forneça entre 1 e 8 operadores aprendidos.")
    names = sorted(models)
    for name in names:
        symbol(name)
        validate_model(models[name])
        if not models[name]["candidates"]:
            return {"status": "unknown", "reason": "A família de modelos de um operador foi refutada pelas observações. Revise as premissas ou a família antes de inventar; uma observação adicional não restaura um modelo incompatível.", "operations": 0}
        if len(models[name].get("candidates", [])) != 1:
            return {"status": "ambiguous", "reason": "Um operador ainda possui alternativas; obtenha outra observação antes de inventar.", "operations": 0}
    if known_signatures is not None and (not isinstance(known_signatures, list) or any(not isinstance(s, str) for s in known_signatures)):
        raise ValueError("Assinaturas conhecidas inválidas.")
    templates = [] if templates is None else templates
    alternative_initials = [] if alternative_initials is None else alternative_initials
    if not isinstance(templates, list) or len(templates) > 8:
        raise ValueError("Use até 8 programas anteriores como analogias estruturais.")
    if not isinstance(alternative_initials, list) or len(alternative_initials) > 3:
        raise ValueError("Use até 3 variações explícitas da premissa inicial.")
    for value in alternative_initials:
        number(value, "alternative_initial", -20, 20)
    for template in templates:
        if not isinstance(template, list) or len(template) > 10 or any(name not in models for name in template):
            raise ValueError("Programa anterior usa ações desconhecidas ou excede o horizonte.")
    budget = Budget(max_operations)
    queue = deque([(initial, [], 1, 0)])
    seen_states, mechanisms, failed = {initial}, {(1, 0)}, []
    duplicate_mechanisms = 0
    solution, transfer_candidates = None, []
    try:
        # Reuse a previously learned procedure's roles and action order for a
        # new state/goal. Numeric transition models still have to verify it.
        for template in templates:
            value, a, b, admissible = initial, 1, 0, len(template) <= max_steps
            for name in template:
                budget.tick()
                if not -20 <= value <= 20:
                    admissible = False
                    break
                model = models[name]["candidates"][0]
                value = model["a"] * value + model["b"]
                a, b = model["a"] * a, model["a"] * b + model["b"]
            passed = admissible and math.isclose(value, target, abs_tol=1e-9, rel_tol=0)
            transfer_candidates.append({"transformation": "structural_analogy_of_stored_program", "plan": template,
                                        "predicted": value, "meets_original_goal": passed})
            if passed and solution is None:
                solution = (template, a, b)
        while queue:
            value, sequence, composed_a, composed_b = queue.popleft()
            if math.isclose(value, target, abs_tol=1e-9, rel_tol=0):
                if solution is None or len(sequence) < len(solution[0]):
                    solution = (sequence, composed_a, composed_b)
                break
            if len(sequence) >= max_steps or not -20 <= value <= 20:
                continue
            for name in names:
                if cancel_event is not None and cancel_event.is_set():
                    return {"status": "budget_exhausted", "operations": budget.operations, "reason": "Busca cancelada."}
                budget.tick()
                candidate = models[name]["candidates"][0]
                a, b = number(candidate["a"]), number(candidate["b"])
                result = a * value + b
                mechanism = (a * composed_a, a * composed_b + b)
                duplicate_mechanisms += int(mechanism in mechanisms)
                mechanisms.add(mechanism)
                if abs(result) > 100:
                    failed.append({"plan": sequence + [name], "reason": "state outside [-100,100]", "value": result})
                    continue
                if result in seen_states:
                    continue
                seen_states.add(result)
                queue.append((result, sequence + [name], mechanism[0], mechanism[1]))
        if solution is None:
            return {"status": "unknown", "reason": "Nenhum plano satisfaz a meta neste horizonte e nesta família.",
                    "operations": budget.operations, "failure_cases": failed[:16], "mechanism_count": len(mechanisms)}
    except Exhausted:
        return {"status": "budget_exhausted", "operations": budget.operations,
                "reason": "Orçamento de busca esgotado; ausência de solução não demonstrada.", "failure_cases": failed[:16]}
    sequence, a, b = solution
    program = program_for(sequence, models)
    executed = execute_program(program, {"x": initial}, max_steps=1000, cancel_event=cancel_event)
    verified = executed.get("status") == "completed" and math.isclose(executed["values"]["x"], target, abs_tol=1e-9, rel_tol=0)
    # Probe independent execution against the composed expression. These tests
    # verify code generation, not unobserved reality or the truth of a premise.
    probes, excluded_probes = [], []
    for x in (-20.0, -2.0, 0.0, 2.0, 20.0):
        current, admissible = x, True
        for name in sequence:
            if not -20 <= current <= 20:
                admissible = False; break
            m = models[name]["candidates"][0]
            current = m["a"] * current + m["b"]
        if admissible:
            result = execute_program(program, {"x": x}, max_steps=1000, cancel_event=cancel_event)
            passed = result.get("status") == "completed" and math.isclose(result["values"]["x"], a*x+b, abs_tol=1e-9, rel_tol=0)
            probes.append({"x": x, "expected": a*x+b, "passed": passed})
            verified = verified and passed
        else:
            excluded_probes.append({"x": x, "reason": "intermediate input outside learned operator domain"})
    normalized_coefficients = [0.0 if value == 0 else float(value) for value in (a, b)]
    signature = hashlib.sha256(json.dumps(normalized_coefficients, separators=(",", ":")).encode()).hexdigest()
    # The composed expression is an actual executable abstraction, not a second
    # prose rendering. It has the same conditional input domain as the full plan.
    abstract_program = [{"op": "load", "name": "x"}, {"op": "const", "value": a}, {"op": "mul"},
                        {"op": "const", "value": b}, {"op": "add"}, {"op": "store", "name": "x"}, {"op": "load", "name": "x"}]
    abstract_run = execute_program(abstract_program, {"x": initial}, max_steps=1000, cancel_event=cancel_event)
    abstract_verified = abstract_run.get("status") == "completed" and math.isclose(abstract_run["values"]["x"], target, abs_tol=1e-9, rel_tol=0)
    verified = verified and abstract_verified
    variations = []
    for alternative in alternative_initials:
        # Altering a supplied premise is an exploratory candidate only. Even if
        # it succeeds it cannot count as answering the original problem.
        value, admissible = alternative, True
        for name in sequence:
            if not -20 <= value <= 20:
                admissible = False
                break
            candidate = models[name]["candidates"][0]
            value = candidate["a"] * value + candidate["b"]
        run = execute_program(program, {"x": alternative}, max_steps=1000, cancel_event=cancel_event) if admissible else {}
        variations.append({"transformation": "explicit_initial_premise_variation", "initial": alternative, "predicted": value,
                           "original_initial": initial, "meets_original_goal": False,
                           "hypothesis_only": True, "execution_status": run.get("status", "outside_model_domain"),
                           "reaches_target_under_changed_premise": admissible and math.isclose(value, target, abs_tol=1e-9, rel_tol=0)})
    return {"status": "answered" if verified else "unknown", "initial": initial, "target": target,
            "plan": sequence, "program": program, "expression": {"a": a, "b": b}, "signature": signature,
            "transformation": "composition of learned affine transition models",
            "candidates": [{"transformation": "program_search_and_composition", "plan": sequence, "signature": signature},
                           {"transformation": "symbolic_abstraction", "program": abstract_program, "same_mechanism_signature": signature,
                            "verified": abstract_verified, "instruction_count": len(abstract_program)}] + transfer_candidates + variations,
            "operations": budget.operations, "execution": executed, "probes": probes, "failure_cases": failed[:16],
            "excluded_probes": excluded_probes,
            "verification_budget": {"probe_inputs": [-20, -2, 0, 2, 20], "max_dsl_steps_per_check": 1000,
                                    "scope": "independent code replay and boundary checks; additional real observations remain necessary"},
            "verification": {"passed": verified, "meaning": "independent DSL replay under supplied conditional models"},
            "metrics": {"utility": int(verified), "viability": verified, "novel_to_memory": signature not in (known_signatures or []),
                        "novelty_scope": "canonical affine function, relative to accessible procedure memory; not scientific novelty",
                        "cost_actions": len(sequence), "cost_search_operations": budget.operations,
                        "robustness_passed": sum(p["passed"] for p in probes), "robustness_tested": len(probes),
                        "distinct_mechanisms_examined": len(mechanisms), "duplicate_mechanisms_removed": duplicate_mechanisms,
                        "transfer_candidates_tested": len(transfer_candidates), "changed_premise_hypotheses": len(variations),
                        "abstraction_instruction_saving": len(program) - len(abstract_program)},
            "limitations": [PRIOR, "The artifact is conditional on observed transition models; probes test compilation only."]}
