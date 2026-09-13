"""Conversation-scoped learned operators, counterexamples and executable invention.

User transitions are conditional premises. A fitted model version is never a
verified observation, a globally activated network, or independent real evidence.
"""
import hashlib
import math

from .contracts import AnswerPackage, canonical
from .operators import fit_operator, observations, predict_operator, synthesize, VERSION
from .reasoning import _symbol as symbol, number


def _model(store, cid, name):
    rows = store.retrieve(cid, {"kind": "model", "where": {"type": "learned_transition", "name": name}}, limit=1000)
    # This workflow is deliberately conversation-scoped even if another local
    # workflow has laboratory records with the same name.
    rows = [r for r in rows if r["conversation_id"] == cid and r["scope"] == "conversation"]
    if len(rows) > 1:
        raise ValueError("Mais de uma versão ativa; revise o operador antes de usar.")
    return rows[0] if rows else None


def _fit_summary(fit):
    return {k: v for k, v in fit.items() if k not in {"neural_artifact", "examples"}}


def package_is_current(package, store, cid, legacy_memory=None):
    """A durable response may become obsolete after an intervening correction."""
    legacy_ids = set()
    for source in package.sources:
        sid = source.get("id", "")
        if sid.startswith("M") and sid[1:].isdigit():
            legacy_ids.add(int(sid[1:]))
        if sid.startswith("E-"):
            try:
                if store.get(sid, conversation_id=cid)["status"] in {"retracted", "disputed"}:
                    return False
            except ValueError:
                return False
    def collect(value):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == "claim_id" and type(child) is int:
                    legacy_ids.add(child)
                elif key == "premise_ids" and isinstance(child, list):
                    legacy_ids.update(i for i in child if type(i) is int)
                else:
                    collect(child)
        elif isinstance(value, list):
            for child in value:
                collect(child)
    if package.domain == "memory":
        for value in (package.conclusions, package.premises, package.hypotheses, package.verification):
            collect(value)
    if legacy_ids:
        if legacy_memory is None:
            return False
        with legacy_memory.lock:
            for identity in legacy_ids:
                try:
                    if legacy_memory.claim(identity)["status"] in {"retracted", "disputed"}:
                        return False
                except ValueError:
                    return False
    return True


def obsolete_package(problem):
    return AnswerPackage.build(problem, "unknown", ["As premissas do resultado anterior foram retiradas ou corrigidas. Envie uma nova tarefa para reavaliar os modelos atuais."],
        verification=[{"check": "sources_still_active", "passed": False}], limitations=["O pacote anterior foi preservado para auditoria e não autoriza uma nova conclusão."], domain="learned_operator")


def _cached(store, problem, source):
    # Read inactive rows too: an invalidated command remains processed and must
    # not silently re-execute its mutations under a new world state.
    with store.lock:
        row = store.db.execute("SELECT id FROM records WHERE conversation_id=? AND owner_id='local' AND dedupe_key=?",
                               (problem.conversation_id, "operator-answer:" + source)).fetchone()
        if row is None:
            return None
        record = store.get(row["id"], conversation_id=problem.conversation_id)
    if record["payload"]["problem_id"] != problem.digest:
        raise ValueError("A origem do comando já pertence a outro problema.")
    package = AnswerPackage.from_dict(record["payload"]["package"])
    return package if record["status"] not in {"retracted", "disputed"} and package_is_current(package, store, problem.conversation_id) else obsolete_package(problem)


def _cache(store, problem, source, package):
    store.record(problem.conversation_id, "episode", {"type": "operator_answer", "problem_id": problem.digest, "package": package.to_dict()},
        list(dict.fromkeys([source] + [s["id"] for s in package.sources if s.get("id", "").startswith("E-")])),
        status="asserted", evidence="deduction", dedupe_key="operator-answer:" + source)
    return package


def _merge(old, new):
    # Exact repeated evidence is replay, never an independent confirmation.
    rows, seen = [], set()
    for row in old + new:
        key = (row["x"], row["y"])
        if key in seen:
            continue
        seen.add(key)
        rows.append(dict(row, id="sample-" + hashlib.sha256(canonical(list(key)).encode()).hexdigest()[:20]))
    return observations(rows)


def solve_operator_request(problem, task, request, context):
    store = context.get("experience_store")
    source = context.get("current_experience_id")
    if store is None or not source:
        raise ValueError("O aprendizado de operadores exige memória de experiência com origem da mensagem.")
    cid = problem.conversation_id
    cached = _cached(store, problem, source)
    if cached:
        return cached
    allowed = {
        "learn_operator": {"name", "examples", "use_neural", "tolerance", "seed", "max_operations"},
        "test_operator": {"name", "examples", "max_operations"},
        "apply_operator": {"name", "x"},
        "invent": {"initial", "target", "operators", "max_steps", "max_operations", "alternative_initials"},
    }
    if set(request) - allowed[task]:
        raise ValueError("Campos desconhecidos na tarefa de operador.")
    if task == "invent":
        names = request.get("operators")
        if not isinstance(names, list) or not 1 <= len(names) <= 8 or any(not isinstance(n, str) for n in names) or len(set(names)) != len(names):
            raise ValueError("Use entre 1 e 8 nomes distintos de operadores aprendidos.")
        records = [_model(store, cid, symbol(n)) for n in names]
        if any(r is None for r in records):
            raise ValueError("Aprenda todos os operadores nesta conversa antes de inventar.")
        models = {name: row["payload"]["fit"] for name, row in zip(names, records)}
        procedures = store.retrieve(cid, {"kind": "procedure", "where": {"type": "learned_program"}}, limit=1000)
        known = [r["payload"]["result"]["signature"] for r in procedures if r["payload"]["result"].get("signature")]
        templates = [r["payload"]["result"]["plan"] for r in procedures if r["payload"]["result"].get("status") == "answered"
                     and all(name in models for name in r["payload"]["result"].get("plan", []))][:8]
        result = synthesize(request["initial"], request["target"], models,
                            max_steps=request.get("max_steps", 6), max_operations=request.get("max_operations", 2048),
                            known_signatures=known, cancel_event=context.get("cancel_event"), templates=templates,
                            alternative_initials=request.get("alternative_initials"))
        dependencies = [source] + [r["id"] for r in records]
        with store.transaction():
            cached = _cached(store, problem, source)
            if cached:
                return cached
            persisted = store.record(cid, "procedure", {"type": "learned_program", "result": result,
                                     "operators": [{"name": n, "record_id": r["id"], "version": r["version"]} for n, r in zip(names, records)],
                                     "goal": {"initial": request["initial"], "target": request["target"], "success": "absolute error <= 1e-9"}},
                                     dependencies, status="asserted", evidence="deduction", uncertainties={"derivation": "conditional"})
            passed = result.get("verification", {}).get("passed") is True
            sentence = ("Programa construído com operadores aprendidos e executado no verificador: %s. Partindo de %s, alcança %s em %s ações, sob os modelos condicionais da conversa." %
                        (" → ".join(result["plan"]) or "identidade", request["initial"], request["target"], len(result["plan"])) if passed else
                        result.get("reason", "Não há um programa aprovado com os modelos e orçamento fornecidos."))
            package = AnswerPackage.build(problem, result["status"], [sentence], conclusions=[{"procedure_id": persisted, "program": result["program"], "target": result["target"]}] if passed else [],
                calculations=[result], premises=[{"operator_id": r["id"], "version": r["version"], "prior": r["payload"]["fit"]["prior"]} for r in records],
                sources=[{"id": s} for s in dependencies + [persisted]], verification=[{"check": "independent_program_execution", "passed": passed}],
                limitations=result.get("limitations", []) + ["Novidade apenas em relação à memória acessível; nenhuma novidade científica foi afirmada."],
                operations=result.get("operations", 0), domain="learned_invention")
            return _cache(store, problem, source, package)

    name = symbol(request.get("name"))
    old = _model(store, cid, name)
    if task == "apply_operator":
        if old is None:
            raise ValueError("Não há operador ativo com esse nome nesta conversa.")
        result = predict_operator(old["payload"]["fit"], request["x"])
        sentence = ("Segundo o operador aprendido %s (versão %s), x=%s produz %s, condicionalmente às observações e à família afim declarada." %
                    (name, old["version"], result["x"], canonical(result["predictions"])))
        if not result["predictions"]:
            sentence = "A família de modelos do operador %s foi refutada pelas observações; não há previsão aprovada. Revise as premissas ou a família de modelos." % name
        return AnswerPackage.build(problem, result["status"], [sentence], conclusions=[result] if result["status"] == "answered" else [],
            calculations=[result], premises=[{"operator_id": old["id"], "version": old["version"]}], sources=[{"id": old["id"]}],
            uncertainty={"candidate_count": result["candidate_count"]}, limitations=[old["payload"]["fit"]["prior"]], domain="learned_operator")

    if task == "test_operator" and old is None:
        raise ValueError("Aprenda o operador antes de enviar uma contraprova.")
    new_rows = observations(request.get("examples"))
    failures, tests = [], []
    if old:
        tolerance = old["payload"]["fit"]["tolerance"]
        for row in new_rows:
            predictions = predict_operator(old["payload"]["fit"], row["x"])
            supported = any(math.isclose(row["y"], y, abs_tol=tolerance + 1e-12, rel_tol=0) for y in predictions["predictions"])
            test = {"x": row["x"], "observed": row["y"], "predictions": predictions["predictions"], "supported": supported}
            tests.append(test)
            if predictions["predictions"] and not supported:
                failures.append(test)
    # Negative evidence remains available after the old model is withdrawn.
    # It depends on the test message, not on the model that failed its test.
    memory_failures = store.retrieve(cid, {"kind": "experiment", "where": {"type": "operator_counterexample", "name": name}}, limit=32)
    replay = [{"x": row["payload"]["test"]["x"], "y": row["payload"]["test"]["observed"], "id": row["id"]} for row in memory_failures]
    rows = _merge((old["payload"]["fit"]["examples"] if old else []) + replay, new_rows)
    options = {k: request[k] for k in ("use_neural", "tolerance", "seed", "max_operations") if k in request}
    # The registered pilot found no verified-goal gain over the finite grammar.
    # Keep the learned neuron available explicitly for research, without paying
    # for a redundant training step on every ordinary conversation update.
    options.setdefault("use_neural", False)
    if old:
        options.setdefault("tolerance", old["payload"]["fit"]["tolerance"])
    fit = fit_operator(rows, **options)
    with store.transaction():
        cached = _cached(store, problem, source)
        if cached:
            return cached
        failure_ids = []
        for failure in failures:
            failure_ids.append(store.record(cid, "experiment", {"type": "operator_counterexample", "name": name,
                "failed_model_id": old["id"], "failed_version": old["version"], "test": failure,
                "meaning": "user-supplied transition contradicts a conditional prediction"}, [source], evidence="user", status="asserted"))
        if fit["status"] == "budget_exhausted":
            if old and failures:
                store.retract(old["id"], "Contraprova recebida; orçamento insuficiente para reavaliar o modelo.")
            package = AnswerPackage.build(problem, "budget_exhausted", [fit["reason"]], calculations=[fit],
                sources=[{"id": source}], operations=fit["operations"], domain="learned_operator")
            return _cache(store, problem, source, package)
        payload = {"type": "learned_transition", "name": name, "fit": fit,
                   "conditions": {"input_interval": [-20, 20], "stationary_affine_family": True},
                   "epistemic_status": "conditional_model_fitted_to_user_observations", "replayed_failure_count": len(replay)}
        dependencies = list(dict.fromkeys((old["source_ids"] if old else []) + [source] + [r["id"] for r in memory_failures] + failure_ids))
        rid = (store.revise(old["id"], payload, source_ids=dependencies, status="asserted", evidence="deduction", uncertainties={"derivation": "conditional"}) if old else
               store.record(cid, "model", payload, dependencies, status="asserted", evidence="deduction", uncertainties={"derivation": "conditional"}))
        version = store.get(rid)["version"]
        sentence = "Aprendi %s como modelo condicional, versão %s: %s candidato(s) compatível(is) com %s observações distintas." % (name, version, len(fit["candidates"]), len(rows))
        if failures:
            sentence += " A contraprova retirou a versão anterior e seus procedimentos dependentes."
        if fit["next_query"] is not None:
            sentence += " Para distinguir as alternativas, observe x=%s." % fit["next_query"]
        if not fit["candidates"]:
            sentence += " A família afim declarada foi refutada por estas premissas; não há previsão aprovada."
        package = AnswerPackage.build(problem, fit["status"], [sentence], hypotheses=fit["candidates"], calculations=[dict(_fit_summary(fit), tests=tests, failed_tests=failures,
            record_id=rid, model_version=version, replayed_failure_count=len(replay))], premises=[{"examples": rows}], sources=[{"id": s} for s in dependencies + [rid]],
            verification=[{"check": "candidate_observation_consistency", "passed": fit["verification"]["passed"]}],
            uncertainty={"candidate_count": len(fit["candidates"]), "weights_globally_activated": False},
            limitations=[fit["prior"], "Verifica compatibilidade com premissas; não confirma leis físicas nem a confiabilidade da fonte."], operations=fit["operations"], domain="learned_operator")
        return _cache(store, problem, source, package)
