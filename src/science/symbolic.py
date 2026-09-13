"""Enumerative dimension-aware polynomial discovery without law-name lookup."""

import itertools
import math

from .numerics import finite, integer, least_squares


def monomial_value(powers, names, variables):
    result = 1.0
    for name, power in zip(names, powers):
        result *= finite(variables[name], name)**power
    return result


def discover(samples, dimensions=None, target_dimension=None, max_degree=3,
             max_terms=3, max_candidates=2000, tolerance=1e-8, symmetries=None,
             max_work=500000):
    """Search sums of products with fitted dimensionless coefficients.

    Input only anonymous measurement rows, never simulator laws or target metadata.
    dimensions/target_dimension are exponent triples (L,T,M); omitted => untyped.
    """
    integer(max_degree, 1, 3, "max_degree")
    integer(max_terms, 1, 3, "max_terms")
    integer(max_candidates, 1, 10000, "max_candidates")
    integer(max_work, 1, 2000000, "max_work")
    tolerance = finite(tolerance, "tolerance")
    if tolerance <= 0:
        raise ValueError("positive tolerance required")
    if not isinstance(samples, list) or not 4 <= len(samples) <= 1000:
        raise ValueError("4 to 1000 samples required")
    names = sorted(samples[0]["variables"])
    if not 1 <= len(names) <= 4 or any(set(s["variables"]) != set(names) for s in samples):
        raise ValueError("consistent 1 to 4 variable names required")
    if any(not isinstance(name, str) or len(name) > 50 or not name.isidentifier() for name in names):
        raise ValueError("variable names must be short identifiers")
    if (dimensions is None) != (target_dimension is None):
        raise ValueError("dimensions and target_dimension must be supplied together")
    if dimensions is not None:
        if set(dimensions) != set(names):
            raise ValueError("dimension required for every variable")
        for dim in list(dimensions.values())+[target_dimension]:
            if not isinstance(dim, (tuple, list)) or len(dim) != 3 or any(type(v) is not int or abs(v) > 8 for v in dim):
                raise ValueError("dimensions must contain 3 bounded integer exponents")
    symmetries = [] if symmetries is None else symmetries
    if not isinstance(symmetries, list) or len(symmetries) > 8:
        raise ValueError("up to 8 declared sign symmetries supported")
    for symmetry in symmetries:
        if not isinstance(symmetry, dict) or set(symmetry) != {"variables", "parity"}:
            raise ValueError("symmetry requires variables and parity")
        if symmetry["parity"] not in ("even", "odd") or not isinstance(symmetry["variables"], list) or not symmetry["variables"]:
            raise ValueError("symmetry must declare even/odd parity and flipped variables")
        if len(set(symmetry["variables"])) != len(symmetry["variables"]) or not set(symmetry["variables"]) <= set(names):
            raise ValueError("symmetry variables must be unique known identifiers")
    terms = []
    for powers in itertools.product(range(max_degree+1), repeat=len(names)):
        if sum(powers) > max_degree:
            continue
        if any(sum(powers[names.index(name)] for name in symmetry["variables"]) % 2 != (1 if symmetry["parity"] == "odd" else 0)
               for symmetry in symmetries):
            continue
        if dimensions is not None:
            term_dim = tuple(sum(powers[j]*dimensions[names[j]][k] for j in range(len(names))) for k in range(3))
            if term_dim != tuple(target_dimension):
                continue
        terms.append(powers)
    terms.sort(key=lambda p: (sum(p), p))
    y = [finite(s["target"], "target") for s in samples]
    features = [[monomial_value(p, names, sample["variables"]) for p in terms] for sample in samples]
    best, tried, alternatives, exhausted, work = None, 0, [], False, 0
    for count in range(1, min(max_terms, len(terms))+1):
        for indices in itertools.combinations(range(len(terms)), count):
            required_work = len(samples)*count*count
            if tried >= max_candidates or work+required_work > max_work:
                exhausted = True
                break
            tried += 1
            work += required_work
            try:
                fit = least_squares([[row[j] for j in indices] for row in features], y)
            except ValueError:
                continue
            complexity = count+sum(sum(terms[j]) for j in indices)
            score = fit["rmse"]+tolerance*complexity
            record = {"powers": [list(terms[j]) for j in indices], "coefficients": fit["coefficients"],
                      "rmse": fit["rmse"], "complexity": complexity, "score": score}
            if best is None or score < best["score"]:
                best = record
            if fit["rmse"] <= tolerance:
                alternatives.append(record)
        if exhausted:
            break
    if best is None:
        return {"status": "unknown", "candidates_evaluated": tried, "budget_exhausted": exhausted,
                "work_units": work, "max_work": max_work}
    parts = []
    for coeff, powers in zip(best["coefficients"], best["powers"]):
        factors = [name+("^"+str(power) if power > 1 else "") for name, power in zip(names, powers) if power]
        parts.append("{:.10g}*{}".format(coeff, "*".join(factors) or "1"))
    best.update({"status": "identified" if best["rmse"] <= tolerance else "approximate",
                 "expression": " + ".join(parts), "variables": names,
                 "candidates_evaluated": tried, "compatible_candidates": len(alternatives),
                 "budget_exhausted": exhausted, "typed": dimensions is not None,
                 "work_units": work, "max_work": max_work,
                 "target_dimension": target_dimension,
                 "supplied_symmetries": symmetries,
                 "limits": "Polynomial sums degree<=3, <=3 terms, dimensionless coefficients when typed; selection is relative to this grammar."})
    return best


def predict(model, variables):
    return math.fsum(c*monomial_value(p, model["variables"], variables)
                     for c, p in zip(model["coefficients"], model["powers"]))


def compile_artifact(model):
    """Compile the selected expression into the restricted arithmetic DSL."""
    program = [{"op": "const", "value": 0}]
    for coefficient, powers in zip(model["coefficients"], model["powers"]):
        program.append({"op": "const", "value": coefficient})
        for name, power in zip(model["variables"], powers):
            if power:
                program.extend([{"op": "load", "name": name}, {"op": "const", "value": power},
                                {"op": "pow"}, {"op": "mul"}])
        program.append({"op": "add"})
    return program


def verify_artifact(model, samples):
    from src.cognition.sandbox import execute_program
    program = compile_artifact(model)
    checks = []
    for sample in samples:
        output = execute_program(program, sample["variables"], timeout=1, max_steps=1000)
        expected = predict(model, sample["variables"])
        passed = output["status"] == "completed" and len(output["stack"]) == 1 and abs(output["stack"][0]-expected) < 1e-9
        checks.append({"passed": passed, "execution_status": output["status"], "expected": expected,
                       "actual": output["stack"][0] if output["stack"] else None})
    return {"passed": bool(checks) and all(c["passed"] for c in checks), "checks": checks,
            "program": program, "scope": "independent restricted execution agrees with expression; not new physical evidence"}
