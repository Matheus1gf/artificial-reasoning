"""Bounded executable reasoning, with explicit hypotheses and independent checks.

The operator vocabulary, finite candidate classes and causal semantics below
are declared priors. Learned parameters are not claims of general intelligence.
"""
import ast
import copy
import heapq
import itertools
import math
import time
from dataclasses import dataclass

from .contracts import canonical


class Exhausted(Exception):
    pass


@dataclass
class Budget:
    maximum: int = 2048
    seconds: float = 1.0
    operations: int = 0

    def __post_init__(self):
        integer(self.maximum, "max_operations", 1, 10000)
        number(self.seconds, "max_seconds", 0.001, 5.0)
        self.deadline = time.perf_counter() + self.seconds

    def tick(self):
        if self.operations >= self.maximum or time.perf_counter() > self.deadline:
            raise Exhausted()
        self.operations += 1


def integer(value, name, minimum=0, maximum=10000):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("%s deve ser inteiro entre %s e %s." % (name, minimum, maximum))
    return value


def number(value, name="value", minimum=-1e12, maximum=1e12):
    if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
        raise ValueError("%s deve ser número finito entre %s e %s." % (name, minimum, maximum))
    return float(value)


def _symbol(value):
    if not isinstance(value, str) or not value or len(value) > 120:
        raise ValueError("Símbolo inválido.")
    return value


def _fact(raw, default_id, allow_variables=False):
    if not isinstance(raw, dict) or set(raw) - {"id", "predicate", "arguments", "polarity"}:
        raise ValueError("Fato deve conter id, predicate, arguments e polarity opcionais.")
    _symbol(raw.get("predicate"))
    args = raw.get("arguments")
    if not isinstance(args, list) or not 1 <= len(args) <= 4:
        raise ValueError("Fato exige de um a quatro argumentos.")
    for arg in args:
        _symbol(arg)
        if arg.startswith("?") and not allow_variables:
            raise ValueError("Fatos precisam ser concretos, sem variáveis livres.")
    polarity = raw.get("polarity", True)
    if type(polarity) is not bool:
        raise ValueError("Polaridade deve ser booleana.")
    return {"id": _symbol(raw.get("id", default_id)), "predicate": raw["predicate"],
            "arguments": list(args), "polarity": polarity}


def _rule(raw, index):
    if not isinstance(raw, dict) or set(raw) - {"id", "if", "then", "types"}:
        raise ValueError("Regra exige id, if, then e types opcionais.")
    if not isinstance(raw.get("if"), list) or not 1 <= len(raw["if"]) <= 4:
        raise ValueError("Regra exige de uma a quatro condições.")
    antecedents = [_fact(f, "condition", True) for f in raw["if"]]
    consequent = _fact(raw.get("then"), "consequent", True)
    bound = {a for f in antecedents for a in f["arguments"] if a.startswith("?")}
    if any(a.startswith("?") and a not in bound for a in consequent["arguments"]):
        raise ValueError("Consequência contém variável não ligada às condições.")
    types = raw.get("types", {})
    if not isinstance(types, dict) or any(v not in bound or not isinstance(t, str) or not t for v, t in types.items()):
        raise ValueError("Restrição de tipo inválida.")
    return {"id": _symbol(raw.get("id", "R" + str(index))), "if": antecedents,
            "then": consequent, "types": dict(types)}


def fact_key(fact):
    return (fact["predicate"], tuple(fact["arguments"]), fact.get("polarity", True))


def _match(pattern, fact, bindings):
    if pattern["predicate"] != fact["predicate"] or pattern["polarity"] != fact["polarity"] or len(pattern["arguments"]) != len(fact["arguments"]):
        return None
    matched = dict(bindings)
    for expected, actual in zip(pattern["arguments"], fact["arguments"]):
        if expected.startswith("?"):
            if expected in matched and matched[expected] != actual:
                return None
            matched[expected] = actual
        elif expected != actual:
            return None
    return matched


def _apply(pattern, bindings, identity):
    return {"id": identity, "predicate": pattern["predicate"], "polarity": pattern["polarity"],
            "arguments": [bindings.get(arg, arg) for arg in pattern["arguments"]]}


def _logical_inputs(facts, rules, entity_types=None):
    if not isinstance(facts, list) or len(facts) > 128 or not isinstance(rules, list) or len(rules) > 32:
        raise ValueError("Use até 128 fatos e 32 regras.")
    facts = [_fact(f, "F" + str(i)) for i, f in enumerate(facts)]
    rules = [_rule(r, i) for i, r in enumerate(rules)]
    ids = [f["id"] for f in facts] + [r["id"] for r in rules]
    if len(set(ids)) != len(ids):
        raise ValueError("IDs de fatos e regras devem ser únicos.")
    types = {} if entity_types is None else entity_types
    if not isinstance(types, dict) or any(not isinstance(v, str) or not isinstance(t, list) or any(not isinstance(k, str) for k in t) for v, t in types.items()):
        raise ValueError("entity_types deve mapear entidades a listas de tipos.")
    return facts, rules, types


def deduce(facts, rules, entity_types=None, max_operations=2048, max_facts=256, max_seconds=1.0):
    facts, rules, entity_types = _logical_inputs(facts, rules, entity_types)
    integer(max_facts, "max_facts", 128, 512)
    budget = Budget(max_operations, max_seconds)
    available = {fact_key(f): f for f in facts}
    derivation = []
    for predicate, args, polarity in available:
        if (predicate, args, not polarity) in available:
            return {"status": "contradictory", "facts": facts, "derivation": [], "operations": 0,
                    "reason": "Premissas incluem uma afirmação e sua negação."}
    try:
        while True:
            before = len(available)
            for rule in rules:
                matches = [({}, [])]
                for condition in rule["if"]:
                    next_matches = []
                    for binding, premises in matches:
                        for fact in list(available.values()):
                            budget.tick()
                            matched = _match(condition, fact, binding)
                            if matched is not None:
                                next_matches.append((matched, premises + [fact["id"]]))
                    matches = next_matches
                for binding, premises in matches:
                    if any(t not in entity_types.get(binding[v], []) for v, t in rule["types"].items()):
                        continue
                    conclusion = _apply(rule["then"], binding, "D" + str(len(derivation)))
                    while conclusion["id"] in {f["id"] for f in available.values()} or conclusion["id"] in {r["id"] for r in rules}:
                        conclusion["id"] = "_" + conclusion["id"]
                    key = fact_key(conclusion)
                    if key in available:
                        continue
                    if (key[0], key[1], not key[2]) in available:
                        return {"status": "contradictory", "facts": list(available.values()), "derivation": derivation,
                                "operations": budget.operations, "reason": "Regras produzem conclusões incompatíveis."}
                    if len(available) >= max_facts:
                        raise Exhausted()
                    available[key] = conclusion
                    derivation.append({"rule_id": rule["id"], "premise_ids": premises,
                                       "bindings": binding, "conclusion": conclusion})
            if len(available) == before:
                break
    except Exhausted:
        return {"status": "budget_exhausted", "facts": list(available.values()), "derivation": derivation,
                "operations": budget.operations}
    return {"status": "answered", "facts": list(available.values()), "derivation": derivation,
            "operations": budget.operations}


def verify_derivation(facts, rules, derivation, entity_types=None):
    """Replay a supplied proof; does not call the forward search algorithm."""
    try:
        facts, rules, types = _logical_inputs(facts, rules, entity_types)
        if not isinstance(derivation, list) or len(derivation) > 512:
            return False
        known, by_rule = {f["id"]: f for f in facts}, {r["id"]: r for r in rules}
        keys = {fact_key(f) for f in facts}
        if any((p, a, not polarity) in keys for p, a, polarity in keys):
            return False
        for step in derivation:
            if not isinstance(step, dict) or set(step) != {"rule_id", "premise_ids", "bindings", "conclusion"}:
                return False
            rule = by_rule[step["rule_id"]]
            if not isinstance(step["premise_ids"], list) or len(step["premise_ids"]) != len(rule["if"]):
                return False
            bindings = {}
            for condition, source in zip(rule["if"], step["premise_ids"]):
                bindings = _match(condition, known[source], bindings)
                if bindings is None:
                    return False
            if bindings != step["bindings"] or any(t not in types.get(bindings[v], []) for v, t in rule["types"].items()):
                return False
            conclusion = _fact(step["conclusion"], "invalid")
            if conclusion["id"] in known or fact_key(conclusion) != fact_key(_apply(rule["then"], bindings, conclusion["id"])):
                return False
            p, a, polarity = fact_key(conclusion)
            if (p, a, not polarity) in keys:
                return False
            known[conclusion["id"]] = conclusion
            keys.add(fact_key(conclusion))
        return True
    except (KeyError, ValueError, TypeError):
        return False


def _state(value):
    if not isinstance(value, dict) or not 1 <= len(value) <= 16:
        raise ValueError("Estado deve conter entre uma e 16 variáveis.")
    for name, scalar in value.items():
        _symbol(name)
        if isinstance(scalar, str):
            _symbol(scalar)
        elif type(scalar) in (int, float):
            number(scalar)
        elif type(scalar) is not bool:
            raise ValueError("Valores de estado devem ser escalares finitos.")
    return dict(value)


def _actions(actions, variables):
    if not isinstance(actions, list) or not 1 <= len(actions) <= 32:
        raise ValueError("Use entre uma e 32 ações.")
    result = []
    for action in actions:
        if not isinstance(action, dict) or set(action) - {"name", "preconditions", "effects", "cost", "source_ids"}:
            raise ValueError("Ação fora do esquema declarado.")
        name = _symbol(action.get("name"))
        preconditions = action.get("preconditions", {})
        effects = action.get("effects")
        if preconditions:
            _state(preconditions)
        if not isinstance(preconditions, dict):
            raise ValueError("Pré-condições inválidas.")
        _state(effects)
        if set(preconditions) - variables or set(effects) - variables:
            raise ValueError("Ação usa variável ausente no estado inicial.")
        cost = number(action.get("cost", 1), "cost", 0, 1e6)
        sources = action.get("source_ids", [])
        if not isinstance(sources, list) or len(sources) > 32 or any(not isinstance(s, str) for s in sources):
            raise ValueError("source_ids deve ser uma lista de IDs.")
        result.append({"name": name, "preconditions": dict(preconditions), "effects": dict(effects), "cost": cost,
                       "source_ids": list(sources)})
    if len({a["name"] for a in result}) != len(result):
        raise ValueError("Os nomes das ações devem ser únicos.")
    return result


def _goal(state, goal):
    return all(k in state and state[k] == v and (type(state[k]) is type(v) or
               (type(state[k]) in (int, float) and type(v) in (int, float))) for k, v in goal.items())


def plan(initial, goal, actions, max_steps=8, max_operations=2048, max_states=512, max_seconds=1.0):
    initial, goal = _state(initial), _state(goal)
    if set(goal) - set(initial):
        raise ValueError("Meta usa variável ausente no estado.")
    actions = _actions(actions, set(initial))
    integer(max_steps, "max_steps", 0, 12)
    integer(max_states, "max_states", 1, 2048)
    budget = Budget(max_operations, max_seconds)
    queue, counter = [(0.0, 0, initial, [])], 0
    best = {(canonical(initial), 0): 0.0}
    try:
        while queue:
            cost, _, state, sequence = heapq.heappop(queue)
            if _goal(state, goal):
                return {"status": "answered", "plan": sequence, "final": state, "cost": cost,
                        "operations": budget.operations, "visited_states": len(best)}
            if len(sequence) == max_steps:
                continue
            for action in actions:
                budget.tick()
                if not _goal(state, action["preconditions"]):
                    continue
                after = dict(state, **action["effects"])
                if canonical(after) == canonical(state):
                    continue
                next_cost = cost + action["cost"]
                key = (canonical(after), len(sequence) + 1)
                if any(best.get((key[0], depth), float("inf")) <= next_cost for depth in range(key[1] + 1)):
                    continue  # A shallower no-more-expensive visit dominates a cycle.
                if key in best and best[key] <= next_cost:
                    continue
                if len(best) >= max_states:
                    raise Exhausted()
                best[key] = next_cost
                counter += 1
                heapq.heappush(queue, (next_cost, counter, after, sequence + [action["name"]]))
    except Exhausted:
        return {"status": "budget_exhausted", "plan": [], "operations": budget.operations, "visited_states": len(best)}
    return {"status": "unknown", "plan": [], "operations": budget.operations, "visited_states": len(best),
            "reason": "Nenhum plano encontrado com estas ações e neste horizonte; não é prova de impossibilidade geral."}


def verify_plan(initial, goal, actions, sequence, max_steps=8):
    """Replay preconditions/effects; never trusts a planner's reported final state."""
    try:
        state, goal = _state(initial), _state(goal)
        by_name = {a["name"]: a for a in _actions(actions, set(state))}
        if not isinstance(sequence, list) or len(sequence) > max_steps:
            return False
        for name in sequence:
            action = by_name[name]
            if not _goal(state, action["preconditions"]):
                return False
            state.update(action["effects"])
        return _goal(state, goal)
    except (ValueError, KeyError, TypeError):
        return False


def calculate(expression, variables=None):
    """Evaluate a tiny arithmetic AST with SI dimension vectors; never Python eval."""
    if not isinstance(expression, str) or not expression.strip() or len(expression) > 500:
        raise ValueError("Expressão aritmética inválida.")
    variables = {} if variables is None else variables
    if not isinstance(variables, dict) or len(variables) > 32:
        raise ValueError("Variáveis inválidas.")
    checked = {}
    for name, item in variables.items():
        _symbol(name)
        if not isinstance(item, dict) or set(item) != {"value", "dimensions"}:
            raise ValueError("Variável exige value e dimensions.")
        dims = item["dimensions"]
        if not isinstance(dims, list) or len(dims) != 3 or any(type(x) is not int or abs(x) > 8 for x in dims):
            raise ValueError("Dimensões devem ser expoentes inteiros [comprimento, tempo, massa].")
        checked[name] = (number(item["value"]), tuple(dims))
    try:
        tree = ast.parse(expression, mode="eval")
    except (SyntaxError, RecursionError):
        raise ValueError("Expressão fora da gramática aritmética.")
    nodes = list(ast.walk(tree))
    if len(nodes) > 100:
        raise ValueError("Expressão excedeu o limite de operações.")

    def evaluate(node):
        if isinstance(node, ast.Constant):
            return number(node.value), (0, 0, 0)
        if isinstance(node, ast.Name) and node.id in checked:
            return checked[node.id]
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value, dims = evaluate(node.operand)
            return (-value if isinstance(node.op, ast.USub) else value), dims
        if isinstance(node, ast.BinOp):
            left, ld = evaluate(node.left)
            right, rd = evaluate(node.right)
            if isinstance(node.op, (ast.Add, ast.Sub)):
                if ld != rd:
                    raise ValueError("Não é possível somar ou subtrair unidades de dimensões diferentes.")
                value, dims = (left + right if isinstance(node.op, ast.Add) else left - right), ld
            elif isinstance(node.op, ast.Mult):
                value, dims = left * right, tuple(a + b for a, b in zip(ld, rd))
            elif isinstance(node.op, ast.Div):
                if right == 0:
                    raise ValueError("Divisão por zero.")
                value, dims = left / right, tuple(a - b for a, b in zip(ld, rd))
            elif isinstance(node.op, ast.Pow) and rd == (0, 0, 0) and right.is_integer() and abs(right) <= 8:
                if left == 0 and right < 0:
                    raise ValueError("Potência indefinida.")
                value, dims = left ** int(right), tuple(a * int(right) for a in ld)
            else:
                raise ValueError("Operador não suportado ou expoente fora do limite.")
            return number(value), dims
        raise ValueError("Use números, variáveis fornecidas e operadores aritméticos; chamadas de código não são permitidas.")
    value, dimensions = evaluate(tree.body)
    return {"status": "answered", "value": value, "dimensions": list(dimensions), "expression": expression,
            "operations": len(nodes), "verification": {"finite": True, "dimension_check": True}}


def induce_affine(examples, query=None, counterexamples=None, max_operations=2048):
    """Learn coefficients from observations within a declared finite affine prior."""
    if not isinstance(examples, list) or not 1 <= len(examples) <= 32:
        raise ValueError("Forneça de um a 32 exemplos {x,y}.")
    checked = []
    for example in examples:
        if not isinstance(example, dict) or set(example) - {"x", "y", "id"} or not {"x", "y"} <= set(example):
            raise ValueError("Exemplo deve conter x e y.")
        checked.append((number(example["x"]), number(example["y"])))
    negatives = [] if counterexamples is None else counterexamples
    if not isinstance(negatives, list) or len(negatives) > 32:
        raise ValueError("Contraexemplos inválidos.")
    for example in negatives:
        if not isinstance(example, dict) or set(example) != {"x", "not_y"}:
            raise ValueError("Contraexemplo deve conter x e not_y.")
        number(example["x"]); number(example["not_y"])
    if query is not None:
        query = number(query)
    budget, candidates = Budget(max_operations), []
    try:
        for a in range(-3, 4):
            for b in range(-5, 6):
                compatible = True
                for x, y in checked:
                    budget.tick()
                    if not math.isclose(a * x + b, y, rel_tol=0, abs_tol=1e-9):
                        compatible = False
                        break
                if compatible:
                    for example in negatives:
                        budget.tick()
                        if math.isclose(a * example["x"] + b, example["not_y"], rel_tol=0, abs_tol=1e-9):
                            compatible = False
                            break
                if compatible:
                    candidates.append({"a": a, "b": b, "complexity": int(a != 0) + int(b != 0),
                                       "expression": "%s*x%+d" % (a, b)})
    except Exhausted:
        return {"status": "budget_exhausted", "candidates": candidates, "operations": budget.operations,
                "reason": "A busca incompleta não permite descartar candidatos ainda não examinados."}
    candidates.sort(key=lambda m: (m["complexity"], abs(m["a"]) + abs(m["b"]), m["a"], m["b"]))
    predictions = sorted({m["a"] * query + m["b"] for m in candidates}) if query is not None else []
    possible_queries = [x for x in range(-5, 6) if x not in {e[0] for e in checked}]
    ranked = sorted(possible_queries, key=lambda x: (-len({m["a"] * x + m["b"] for m in candidates}), abs(x), x))
    next_query = ranked[0] if len(candidates) > 1 and ranked else None
    return {"status": "unknown" if not candidates else "answered" if len(candidates) == 1 or len(predictions) == 1 else "ambiguous",
            "candidates": candidates, "predictions": predictions, "next_query": next_query,
            "operations": budget.operations, "prior": "y=a*x+b; a inteiro em[-3,3], b inteiro em[-5,5]; observações exatas",
            "reason": "Nenhum modelo da família é compatível; ampliar a família ou revisar os dados." if not candidates else "Validade condicional à família declarada; simplicidade não prova unicidade física."}


def abduce(facts, rules, query, entity_types=None, max_operations=2048):
    """Grounded backward explanations: unmet antecedents remain hypotheses."""
    facts, rules, types = _logical_inputs(facts, rules, entity_types)
    query = _fact(query, "query")
    known = {fact_key(f) for f in facts}
    budget, candidates = Budget(max_operations), []
    constants = sorted({a for f in facts + [query] for a in f["arguments"]})[:12]
    try:
        for rule in rules:
            initial = _match(rule["then"], query, {})
            if initial is None:
                continue
            variables = sorted({a for f in rule["if"] for a in f["arguments"] if a.startswith("?")} - set(initial))
            if len(variables) > 3:
                continue
            for combination in itertools.product(constants, repeat=len(variables)):
                budget.tick()
                binding = dict(initial, **dict(zip(variables, combination)))
                if any(t not in types.get(binding[v], []) for v, t in rule["types"].items()):
                    continue
                assumptions = [_apply(f, binding, "H" + str(i)) for i, f in enumerate(rule["if"])]
                if any((f["predicate"], tuple(f["arguments"]), not f["polarity"]) in known for f in assumptions):
                    continue
                missing = [f for f in assumptions if fact_key(f) not in known]
                candidates.append({"rule_id": rule["id"], "bindings": binding, "missing": missing,
                                   "status": "hypothesis" if missing else "supported",
                                   "test": missing[0] if missing else None})
    except Exhausted:
        return {"status": "budget_exhausted", "explanations": candidates, "operations": budget.operations}
    candidates.sort(key=lambda c: (len(c["missing"]), c["rule_id"], canonical(c["bindings"])))
    return {"status": "answered" if any(not c["missing"] for c in candidates) else "ambiguous" if candidates else "unknown",
            "explanations": candidates[:32], "operations": budget.operations,
            "limitation": "Explicações são condicionais às regras fornecidas e não provam que os antecedentes ocorreram."}


def structural_analogy(source, target, source_entities, target_entities, mapping=None, max_operations=2048):
    """Transfer graph relations after matching at least two structural relations."""
    source, _, _ = _logical_inputs(source, [])
    target, _, _ = _logical_inputs(target, [])
    for entities in (source_entities, target_entities):
        if (not isinstance(entities, list) or not 1 <= len(entities) <= 6
                or any(not isinstance(e, str) for e in entities) or len(set(entities)) != len(entities)):
            raise ValueError("Informe de uma a seis entidades distintas por grafo.")
        for entity in entities:
            _symbol(entity)
    if len(source_entities) > len(target_entities):
        return {"status": "unknown", "proposals": [], "operations": 0, "reason": "Não há correspondência injetiva de papéis."}
    if mapping is not None:
        if (not isinstance(mapping, dict) or set(mapping) != set(source_entities)
                or any(not isinstance(v, str) or v not in target_entities for v in mapping.values())
                or len(set(mapping.values())) != len(mapping)):
            raise ValueError("Correspondência deve mapear cada entidade fonte para um alvo distinto.")
        mappings = [dict(mapping)]
    else:
        mappings = (dict(zip(source_entities, values)) for values in itertools.permutations(target_entities, len(source_entities)))
    budget, proposals = Budget(max_operations), []
    target_keys = {fact_key(f) for f in target}
    try:
        for candidate in mappings:
            translated = []
            for fact in source:
                budget.tick()
                translated.append(dict(fact, arguments=[candidate.get(a, a) for a in fact["arguments"]]))
            shared = [f for f in translated if fact_key(f) in target_keys]
            if len({fact_key(f) for f in shared}) < 2:
                continue
            for fact in translated:
                key = fact_key(fact)
                if key not in target_keys and (key[0], key[1], not key[2]) not in target_keys:
                    proposals.append({"mapping": dict(candidate), "shared": shared, "conclusion": fact,
                                      "status": "hypothesis", "requires_test": True})
    except Exhausted:
        return {"status": "budget_exhausted", "proposals": proposals[:32], "operations": budget.operations}
    return {"status": "answered" if proposals else "unknown", "proposals": proposals[:32], "operations": budget.operations,
            "limitation": "Correspondência estrutural gera hipótese; não transfere automaticamente causalidade ou existência."}


def causal_evaluate(model, inputs, intervention=None, factual=None, max_operations=2048):
    """Deterministic binary acyclic structural causal model with fixed exogenous inputs.

    Counterfactual evaluation preserves supplied exogenous inputs; it does not
    identify latent noise from observational correlations or infer causation.
    """
    if not isinstance(model, dict) or not 1 <= len(model) <= 32:
        raise ValueError("Modelo causal deve conter de uma a 32 variáveis.")
    inputs = {} if inputs is None else inputs
    intervention = {} if intervention is None else intervention
    factual = {} if factual is None else factual
    for values in (inputs, intervention, factual):
        if not isinstance(values, dict) or set(values) - set(model):
            raise ValueError("Valores causais referem-se a variáveis inexistentes.")
        if any(type(v) not in (int, bool) or v not in (0, 1) for v in values.values()):
            raise ValueError("O domínio causal inicial aceita somente valores binários.")
    equations = {}
    arities = {"input": 0, "constant": 0, "copy": 1, "not": 1, "and": 2, "or": 2, "xor": 2}
    for variable, equation in model.items():
        _symbol(variable)
        if not isinstance(equation, dict) or set(equation) - {"op", "args", "value"}:
            raise ValueError("Equação causal inválida.")
        op, args = equation.get("op"), equation.get("args", [])
        if not isinstance(op, str) or op not in arities or not isinstance(args, list) or len(args) != arities[op]:
            raise ValueError("Operação/quantidade de pais inválida no modelo causal.")
        if any(not isinstance(p, str) or p not in model for p in args):
            raise ValueError("Pai causal inexistente.")
        if op == "constant" and (type(equation.get("value")) not in (int, bool) or equation.get("value") not in (0, 1)):
            raise ValueError("Constante causal deve ser binária.")
        equations[variable] = {"op": op, "args": args, "value": equation.get("value")}
    if any(equations[name]["op"] != "input" for name in inputs):
        raise ValueError("inputs deve fornecer apenas variáveis exógenas; use intervention para modificar mecanismos.")
    budget = Budget(max_operations)

    def evaluate(intervened):
        values, pending = {}, dict(equations)
        while pending:
            progress = False
            for variable, equation in list(pending.items()):
                budget.tick()
                if variable in intervened:
                    values[variable] = int(intervened[variable])
                elif equation["op"] == "input":
                    if variable not in inputs:
                        return None, "Entrada exógena não observada: " + variable
                    values[variable] = int(inputs[variable])
                elif equation["op"] == "constant":
                    values[variable] = int(equation["value"])
                elif all(p in values for p in equation["args"]):
                    args = [values[p] for p in equation["args"]]
                    op = equation["op"]
                    values[variable] = {"copy": lambda: args[0], "not": lambda: 1 - args[0],
                                        "and": lambda: args[0] & args[1], "or": lambda: args[0] | args[1],
                                        "xor": lambda: args[0] ^ args[1]}[op]()
                else:
                    continue
                del pending[variable]
                progress = True
            if not progress:
                raise ValueError("O modelo contém ciclo; somente grafos acíclicos são suportados.")
        return values, None

    try:
        baseline, missing = evaluate({})
        if missing:
            return {"status": "unknown", "reason": missing, "operations": budget.operations,
                    "identifiable": False}
        if any(baseline[name] != int(value) for name, value in factual.items()):
            return {"status": "contradictory", "reason": "O modelo e as entradas não reproduzem os fatos fornecidos.",
                    "operations": budget.operations}
        changed, missing = evaluate(intervention)
    except Exhausted:
        return {"status": "budget_exhausted", "operations": budget.operations}
    return {"status": "answered", "factual": baseline, "intervened": changed, "operations": budget.operations,
            "identifiable": True, "assumptions": ["modelo estrutural fornecido", "determinismo binário", "grafo acíclico",
                                                      "entradas exógenas mantidas no contrafactual"],
            "limitation": "Resultado condicional ao modelo; dados observacionais sem este modelo não identificam o efeito causal."}
