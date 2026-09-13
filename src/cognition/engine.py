"""Build and verify semantic answers before any language-model arrangement."""
from .contracts import AnswerPackage, ProblemSpec, canonical
from . import reasoning as logic
from src.chat.domain import claim_text


def _fact_text(fact):
    arguments = fact["arguments"]
    return "%s %s%s %s" % (arguments[0], "" if fact.get("polarity", True) else "não ",
                             fact["predicate"], ", ".join(arguments[1:]))


def _unknown(problem, message, status="unknown", **values):
    return AnswerPackage.build(problem, status, [message], limitations=[message], **values)


def _opposition_text(hypotheses, by_id):
    """Concise semantic rendering of verified proposal records, without an LLM."""
    from src.chat.reasoner import projected_claims
    groups = {}
    for h in hypotheses:
        key = (h["subject"], h["predicate"], h.get("scope", "memory"))
        groups.setdefault(key, []).append(h)
    sentences = []
    for (target, action, scope), rows in groups.items():
        objects = list(dict.fromkeys(h["object"] for h in rows))
        joined = " e ".join(objects) if len(objects) < 3 else ", ".join(objects[:-1]) + " e " + objects[-1]
        source_ids = list(dict.fromkeys(pid for h in rows for pid in h["premise_ids"]))
        projected = projected_claims([by_id[i] for i in source_ids if i in by_id])
        functions = [c for c in projected if c["subject"] != target and c["predicate"] not in {"é", "oposto_de"}
                     and c["object"] in objects]
        origin = functions[0]["subject"] if functions else "a entidade de referência"
        original_action = functions[0]["predicate"] if functions else "a função fornecida"
        prefix = "Sob a suposição desta pergunta, " if scope == "current_question" else "Pela oposição funcional com " + origin + ", "
        refs = " ".join("[M%s]" % h["claim_id"] for h in rows if "claim_id" in h)
        sentences.append(prefix + "a hipótese a testar é: " + target + " " + action + " " + joined + "." + (" " + refs if refs else ""))
        sentences.append("Usei a transformação de função “" + original_action + " → " + action +
                         "”. Essa interpretação não demonstra existência nem validade física; não inverti automaticamente causas ou outras propriedades.")
        sentences.append("Como testar: definir condições e verificar se " + target + " " + action + " " + joined +
                         ", comparando com a ausência dessa função. Ainda falta identificar um mecanismo e obter observações.")
    return sentences


def _verify_memory_claim(claim, by_id, path=None):
    """Independently check legacy universal-property proofs before verbalizing."""
    path = set() if path is None else set(path)
    if claim.get("id") in path or len(path) >= 64:
        return False
    if claim.get("status") == "asserted":
        return True  # A supplied premise, not a claim of external scientific truth.
    if claim.get("status") == "hypothesis":
        if claim.get("origin") == "user":
            return True  # Quoted as a user hypothesis, never an established fact.
        from src.chat.reasoner import verify_hypothesis
        path.add(claim.get("id"))
        return (all(pid in by_id and _verify_memory_claim(by_id[pid], by_id, path) for pid in claim.get("premises", []))
                and verify_hypothesis(claim, by_id))
    if claim.get("status") != "deduced" or len(claim.get("premises", [])) != 2:
        return False
    path.add(claim["id"])
    try:
        premises = [by_id[pid] for pid in claim["premises"]]
    except KeyError:
        return False
    for member, rule in (premises, list(reversed(premises))):
        if (member["predicate"] == "é" and member["polarity"] and member["scope"] == "instance"
                and rule["scope"] == "universal" and member["object"] == rule["subject"]
                and claim["subject"] == member["subject"] and claim["predicate"] == rule["predicate"]
                and claim["object"] == rule["object"] and claim["polarity"] == rule["polarity"]
                and _verify_memory_claim(member, by_id, path) and _verify_memory_claim(rule, by_id, path)):
            return True
    return False


class CognitiveCore:
    def __init__(self, domain_services=None):
        self.domain_services = domain_services

    def solve(self, problem, context=None):
        if not isinstance(problem, ProblemSpec):
            raise ValueError("O núcleo recebe exclusivamente um ProblemSpec validado.")
        context = {} if context is None else context
        if problem.ambiguities:
            questions = [a.get("question", "Confirme a interpretação da mensagem.") for a in problem.ambiguities]
            return AnswerPackage.build(problem, "ambiguous", questions, clarification=questions,
                                       uncertainty={"interpretations": problem.ambiguities})
        try:
            if problem.intent == "domain_request":
                return self._scientific(problem)
            if "structured" in problem.payload:
                return self._structured(problem, context)
            if problem.intent == "calculation":
                return self._calculation(problem, problem.payload["calculation"])
            if problem.intent == "summary":
                previous = problem.context.get("previous_approved")
                if not previous:
                    return _unknown(problem, "Não há conteúdo aprovado anterior para retomar nesta conversa.")
                old = AnswerPackage.from_dict(previous)
                # The core chooses retained semantic units; the arranger cannot.
                sentences = [s["text"] for s in old.sentences]
                limit = problem.constraints.get("words")
                if limit:
                    selected = [s for s in sentences if len(s.split()) <= limit["value"]]
                    if limit["exact"]:
                        selected = [s for s in selected if len(s.split()) == limit["value"]]
                    if not selected:
                        return _unknown(problem, "Não consigo cumprir essa contagem preservando as unidades de conteúdo aprovadas. Posso retomar a resposta completa.",
                                        status="ambiguous", clarification=["Posso preservar o conteúdo completo sem essa contagem exata?"])
                    sentences = selected[:1]
                return AnswerPackage.build(problem, old.status, sentences, conclusions=old.conclusions,
                                           premises=old.premises, sources=old.sources, hypotheses=old.hypotheses,
                                           verification=[{"check": "retained_approved_content", "passed": True}],
                                           limitations=old.limitations, domain=old.domain)
            return self._knowledge(problem, context)
        except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
            # Unsupported syntax/models are explicit, never delegated to Qwen.
            return _unknown(problem, "O núcleo não pôde validar esse pedido: " + str(exc), status="ambiguous",
                            clarification=["Revise os campos, unidades ou premissas indicados."],
                            verification=[{"check": "input_or_model_validation", "passed": False}])

    def _calculation(self, problem, request):
        result = logic.calculate(request["expression"], request.get("variables"))
        dims = result["dimensions"]
        unit = " · ".join(name + ("^" + str(power) if power != 1 else "")
                          for name, power in zip(("m", "s", "kg"), dims) if power) or "sem unidade"
        sentence = "O resultado é %s (%s), com as unidades convertidas ao SI quando fornecidas." % (format(result["value"], ".12g"), unit)
        return AnswerPackage.build(problem, "answered", [sentence], calculations=[result],
                                   conclusions=[{"value": result["value"], "dimensions": dims}],
                                   premises=[{"source": "user:current", "expression": request["expression"]}],
                                   verification=[{"check": "bounded_arithmetic_and_dimensions", "passed": True}],
                                   operations=result["operations"], domain="arithmetic")

    def _scientific(self, problem):
        if self.domain_services is None:
            from src.science import resolve
            resolver = resolve
        else:
            resolver = self.domain_services
        request = problem.payload["request"]
        result = resolver(request)
        if not isinstance(result, dict):
            raise ValueError("Serviço científico retornou formato inválido.")
        verification = result.get("verification", {})
        checked = isinstance(verification, dict) and verification.get("passed") is True
        status = result.get("status", "unknown")
        if status == "answered" and checked:
            sentences = result.get("sentences") or ["Resultado verificado no domínio declarado: " + canonical(result.get("values", {}))]
            final_status = "answered"
        else:
            sentences = (["Resultado sem conclusão confirmada: " + s for s in result.get("sentences", [])] if checked else [])
            sentences = sentences or ["A verificação científica não autorizou uma conclusão. Os dados e a falha ficaram registrados nas evidências do experimento."]
            final_status = "ambiguous" if status == "invalid" else "unknown"
        conclusions = [c if isinstance(c, dict) else {"text": str(c)} for c in result.get("conclusions", [])]
        premises = [{"request": request, "source": "user:current"}]
        sources = []
        for premise in result.get("premises", []):
            item = premise if isinstance(premise, dict) else {"source_url": premise} if isinstance(premise, str) and premise.startswith(("https://", "http://")) else {"assumption": str(premise)}
            premises.append(item)
            if item.get("source_url"):
                sources.append({"id": "science-source-" + str(len(sources) + 1), "url": item["source_url"], "kind": "declared_primary_source"})
        return AnswerPackage.build(problem, final_status, sentences,
                                   conclusions=conclusions if checked and status == "answered" else [], sources=sources,
                                   calculations=[{"result": result, "units": result.get("units", {})}], premises=premises,
                                   verification=[{"check": "scientific_service", "passed": checked, "details": verification}],
                                   limitations=result.get("limitations", []), domain=request["domain"])

    def _structured(self, problem, context=None):
        request = dict(problem.payload["structured"])
        task = request.pop("task")
        if task in {"learn_operator", "apply_operator", "test_operator"} or (task == "invent" and "operators" in request):
            from .operator_runtime import solve_operator_request
            return solve_operator_request(problem, task, request, context or {})
        if task == "classify":
            from .neural import local_intent
            if set(request) != {"text"}:
                raise ValueError("classify exige apenas text.")
            proposal = local_intent(request["text"])
            return AnswerPackage.build(problem, "ambiguous", ["A rede própria produziu uma classificação experimental; ela ainda não foi promovida a intérprete da mensagem."],
                hypotheses=[dict(proposal, adopted=False)] if proposal else [],
                limitations=["Cobertura de intenção insuficiente para compreensão aberta; nenhum fato foi extraído pela rede."], domain="intent_experiment")
        allowed = {
            "deduce": {"facts", "rules", "query", "entity_types", "max_operations"},
            "plan": {"initial", "goal", "actions", "max_steps", "max_operations", "max_states", "max_seconds"},
            "invent": {"initial", "goal", "actions", "max_steps", "max_operations", "max_states", "max_seconds"},
            "induce": {"examples", "query", "counterexamples", "max_operations"},
            "abduce": {"facts", "rules", "query", "entity_types", "max_operations"},
            "analogy": {"source", "target", "source_entities", "target_entities", "mapping", "max_operations"},
            "causal": {"model", "inputs", "intervention", "factual", "max_operations"},
            "counterfactual": {"model", "inputs", "intervention", "factual", "max_operations"},
            "calculate": {"expression", "variables"},
        }
        if set(request) - allowed[task]:
            raise ValueError("Campos desconhecidos para a tarefa " + task + ".")
        if task == "calculate":
            return self._calculation(problem, request)
        if task == "deduce":
            query = request.pop("query", None)
            result = logic.deduce(**request)
            if result["status"] == "contradictory":
                return AnswerPackage.build(problem, "contradictory", [result["reason"]],
                                           premises=[{"facts": request["facts"], "rules": request["rules"]}],
                                           verification=[{"check": "consistency", "passed": False}],
                                           operations=result["operations"], domain="logic")
            verified = logic.verify_derivation(request["facts"], request["rules"], result["derivation"], request.get("entity_types"))
            if not verified:
                return _unknown(problem, "A derivação não passou pela verificação independente.")
            selected = result["facts"]
            if query is not None:
                query = logic._fact(query, "query")
                selected = [f for f in selected if logic.fact_key(f) == logic.fact_key(query)]
            else:
                selected = [step["conclusion"] for step in result["derivation"]]
            status = result["status"] if result["status"] != "answered" or selected else "unknown"
            sentences = ["Dedução condicional às premissas fornecidas: " + _fact_text(f) + "." for f in selected[:16]] if status == "answered" else []
            sentences = sentences or [result.get("reason", "A consulta não foi demonstrada com estas premissas e este orçamento.")]
            return AnswerPackage.build(problem, status, sentences, conclusions=selected[:32],
                                       premises=[{"facts": request["facts"], "rules": request["rules"]}],
                                       calculations=[{"derivation": result["derivation"]}],
                                       verification=[{"check": "independent_derivation_replay", "passed": verified}],
                                       operations=result["operations"], domain="logic")
        if task in {"plan", "invent"}:
            result = logic.plan(**request)
            verified = result["status"] == "answered" and logic.verify_plan(request["initial"], request["goal"], request["actions"], result["plan"], request.get("max_steps", 8))
            if verified:
                sentence = "Plano verificado: %s. Custo total: %s. A meta é satisfeita sob as ações fornecidas." % (
                    " → ".join(result["plan"]) or "nenhuma ação necessária", format(result["cost"], ".12g"))
            else:
                sentence = result.get("reason", "A busca esgotou o orçamento sem um plano aprovado.")
            return AnswerPackage.build(problem, result["status"] if not result["status"] == "answered" or verified else "unknown", [sentence],
                                       conclusions=[result] if verified else [], calculations=[result],
                                       premises=[{"actions": request["actions"], "initial": request["initial"], "goal": request["goal"]}],
                                       verification=[{"check": "independent_plan_replay", "passed": verified}],
                                       limitations=["Planejamento em estados finitos e ações fornecidas; novidade científica não avaliada."],
                                       operations=result["operations"], domain="planning")
        if task == "induce":
            result = logic.induce_affine(**request)
            if result["status"] == "answered":
                sentence = "Os exemplos sustentam %s dentro da família afim declarada." % (
                    "a previsão " + canonical(result["predictions"]) if result["predictions"] else result["candidates"][0]["expression"])
            else:
                sentence = "Há %s modelos afins compatíveis; a conclusão permanece %s." % (len(result.get("candidates", [])), result["status"])
            if result.get("next_query") is not None:
                sentence += " Uma próxima observação discriminante usa x=%s." % result["next_query"]
            return AnswerPackage.build(problem, result["status"], [sentence], calculations=[result],
                                       hypotheses=result.get("candidates", []), premises=[{"examples": request["examples"]}],
                                       verification=[{"check": "candidate_consistency", "passed": result["status"] != "budget_exhausted"}],
                                       uncertainty={"candidate_count": len(result.get("candidates", []))},
                                       limitations=[result.get("prior", "Busca incompleta."), result.get("reason", "")],
                                       operations=result["operations"], domain="induction")
        if task == "abduce":
            result = logic.abduce(**request)
            sentences = ["Explicação candidata pela regra %s: verificar %s. Ela não prova que essas condições ocorreram." % (
                e["rule_id"], "; ".join(_fact_text(f) for f in e["missing"]) or "condições já fornecidas") for e in result["explanations"][:4]]
            return AnswerPackage.build(problem, result["status"], sentences or ["Não encontrei explicação nas regras fornecidas."],
                                       hypotheses=result["explanations"], calculations=[result],
                                       premises=[{"facts": request["facts"], "rules": request["rules"]}],
                                       operations=result["operations"], domain="abduction")
        if task == "analogy":
            result = logic.structural_analogy(**request)
            sentences = ["Hipótese por correspondência estrutural: " + _fact_text(p["conclusion"]) + ". A transferência precisa de teste no alvo."
                         for p in result["proposals"][:4]]
            return AnswerPackage.build(problem, result["status"], sentences or ["Não há correspondência suficiente para transferir uma hipótese."],
                                       hypotheses=result["proposals"], calculations=[result],
                                       operations=result["operations"], domain="analogy")
        result = logic.causal_evaluate(**request)
        sentence = ("Sob o modelo causal fornecido e suas entradas exógenas, a intervenção produz " + canonical(result["intervened"]) + "."
                    if result["status"] == "answered" else result.get("reason", "O cálculo causal não terminou no orçamento."))
        return AnswerPackage.build(problem, result["status"], [sentence], calculations=[result],
                                   premises=[{"model": request["model"], "inputs": request["inputs"]}],
                                   verification=[{"check": "structural_causal_model", "passed": result["status"] == "answered"}],
                                   limitations=[result.get("limitation", "Resultado não identificado neste modelo.")],
                                   operations=result["operations"], domain="causal")

    def _knowledge(self, problem, context):
        from src.chat.reasoner import projected_claims
        learned = context.get("learned", [])
        relevant = context.get("relevant", [])
        inferred = context.get("inferences", [])
        temporary = context.get("temporary_inferences", [])
        conflicts = context.get("conflicts", [])
        invalidated = context.get("invalidated", [])
        frame = problem.payload.get("discourse", {})
        target = frame.get("target") or problem.question.get("subject", "")
        reference = frame.get("reference", "")
        mode = frame.get("mode", "")
        if mode == "ask_relation" and not frame.get("target"):
            target = ""  # Asking for an unnamed counterpart, not source=target.
        by_id = {c["id"]: c for c in context.get("claims", learned + relevant + inferred)}
        if problem.intent == "creation" and not learned:
            # Shared words such as 'light' are insufficient grounds to include
            # a past topic in a design. Report the proposal's actual support.
            support = {pid for c in inferred for pid in c.get("premises", [])}
            relevant = [by_id[pid] for pid in sorted(support) if pid in by_id]
        if conflicts:
            sentences = ["Há premissas em conflito: " + "; ".join(claim_text(c) for c in conflicts[:4]) + ". Suspendi conclusões dependentes; indique a correção."]
            return AnswerPackage.build(problem, "contradictory", sentences,
                                       premises=[{"claim_id": c["id"], "text": claim_text(c)} for c in conflicts[:16]])
        sentences, conclusions, hypotheses = [], [], []
        checked_claims = list({c["id"]: c for c in learned + relevant + inferred}.values())
        # All transitive sources are part of the answer, not hidden in another
        # result row. They also allow pending responses to reject withdrawn data.
        evidence_ids = {c["id"] for c in checked_claims}
        for claim in checked_claims + temporary:
            evidence_ids.update(claim.get("premises", []))
        pending = list(evidence_ids)
        while pending and len(evidence_ids) < 128:
            identity = pending.pop()
            for parent in by_id.get(identity, {}).get("premises", []):
                if parent not in evidence_ids:
                    evidence_ids.add(parent); pending.append(parent)
        verification = [{"check": "memory_premise_or_derivation", "claim_id": cid,
                         "passed": _verify_memory_claim(by_id[cid], by_id)} for cid in sorted(evidence_ids) if cid in by_id]
        invalid = {v["claim_id"] for v in verification if not v["passed"]}
        selected = [c for c in (learned if learned else relevant) if c["id"] not in invalid]
        inferred = [c for c in inferred if c["id"] not in invalid]
        if mode == "assume_relation":
            # Global conclusions about the relation cannot override the local
            # assumption, especially when the question explicitly negates it.
            inferred = [c for c in inferred if c.get("method") != "opposition"]
            selected = [c for c in selected if c.get("method") != "opposition" and c["predicate"] != "oposto_de"
                        and not (c["predicate"] == "é" and "inverso de" in c["object"])]
        if target and not learned and mode in {"describe", "ask_relation", "assume_relation", "explore"}:
            selected = [c for c in selected if c["subject"] == target]
            inferred = [c for c in inferred if c["subject"] == target]
        # A generated hypothesis recalled from memory remains a hypothesis, not
        # a user-supplied fact or a conclusion. Repetition cannot promote it.
        inferred_ids = {c["id"] for c in inferred}
        for claim in selected:
            if claim["status"] == "hypothesis" and claim["id"] not in inferred_ids:
                inferred.append(claim); inferred_ids.add(claim["id"])
        for claim in selected[:8]:
            if claim["status"] == "hypothesis":
                continue
            epistemic = "dedução condicional" if claim["status"] == "deduced" else "premissa informada"
            sentence = ("Registrei como %s: " % epistemic if learned else "Segundo a %s registrada: " % epistemic) + claim_text(claim) + ". [M%s]" % claim["id"]
            sentences.append(sentence)
            conclusions.append({"claim_id": claim["id"], "text": claim_text(claim), "status": claim["status"],
                                "premise_ids": claim.get("premises", [])})
        hypothesis_sentences = []
        for claim in inferred[:4]:
            if claim["status"] == "hypothesis":
                label = "Hipótese informada" if claim.get("origin") == "user" else "Hipótese a testar"
                hypothesis_sentences.append(label + ": " + claim_text(claim) + ". " + claim.get("explanation", "") +
                    " Essa proposta não demonstra existência ou validade. [M%s]" % claim["id"])
                hypotheses.append({"claim_id": claim["id"], "subject": claim["subject"], "predicate": claim["predicate"],
                    "object": claim["object"], "text": claim_text(claim), "premise_ids": claim.get("premises", []),
                    "test": claim.get("validation", ""), "explanation": claim.get("explanation", ""),
                    "method": claim.get("method", ""), "status": "hypothesis"})
            elif claim["id"] not in {c["claim_id"] for c in conclusions}:
                sentences.append("Dedução condicional às premissas registradas: " + claim_text(claim) + ". [M%s]" % claim["id"])
                conclusions.append({"claim_id": claim["id"], "text": claim_text(claim), "status": claim["status"],
                                    "premise_ids": claim.get("premises", [])})
        assumptions = frame.get("temporary_assumptions", [])
        for claim in temporary[:4]:
            from src.chat.reasoner import verify_hypothesis
            supported = bool(assumptions) and (not target or claim["subject"] == target) and all(pid in by_id and _verify_memory_claim(by_id[pid], by_id)
                                                and by_id[pid]["status"] in {"asserted", "deduced"} for pid in claim["premises"])
            supported = supported and verify_hypothesis(claim, by_id, assumptions)
            verification.append({"check": "temporary_assumption_and_active_sources", "passed": supported})
            if not supported:
                continue
            hypothesis_sentences.append("Sob a suposição desta pergunta, hipótese a testar: " + claim_text(claim) + ". " +
                claim["explanation"] + " Essa proposta não demonstra existência ou validade e não foi registrada como fato.")
            hypotheses.append({"subject": claim["subject"], "predicate": claim["predicate"], "object": claim["object"],
                "text": claim_text(claim), "premise_ids": claim["premises"], "temporary_assumptions": assumptions,
                "scope": "current_question", "test": claim["validation"], "method": claim["method"], "status": "hypothesis"})
        if hypotheses:
            # Lead with the new, relevant content. Supporting memory is retained
            # below and in the evidence panel rather than substituting for it.
            if all(h.get("method") == "opposition" for h in hypotheses):
                sentences = _opposition_text(hypotheses, by_id) + sentences
            else:
                sentences = hypothesis_sentences + sentences
                tests = list(dict.fromkeys(h["test"] for h in hypotheses if h.get("test")))
                if tests:
                    sentences.append("Como testar: " + " ".join(tests[:2]))
        if invalidated:
            sentences.append("A correção retirou %s conclusões ou conhecimentos dependentes da versão anterior." % len(set(invalidated)))
        if problem.intent == "greeting":
            sentences = ["Olá. Posso aprender premissas, verificar deduções, explorar hipóteses e compor funções neste laboratório."]
        if mode == "ask_relation" and target and reference and not hypotheses:
            links = [c for c in projected_claims(list(by_id.values())) if c["predicate"] == "oposto_de"
                     and c["status"] == "asserted" and {c["subject"], c["object"]} == {target, reference}]
            if not links:
                message = ("Você perguntou sobre %s usando %s como referência. Ainda não tenho uma relação demonstrada entre eles. "
                           "Podemos explorar uma hipótese de oposição ou analogia, mas preciso que você indique qual relação pretende assumir." % (target, reference))
                return _unknown(problem, message, clarification=["Qual relação entre %s e %s devo explorar?" % (target, reference)])
        trace = context.get("reasoning_trace", [])
        if problem.intent == "creation" and trace and trace[-1].get("symbolic_goal_verified") is False:
            return _unknown(problem, "Não encontrei uma sequência das funções informadas que transforme %s em %s. "
                "Falta uma etapa de conversão ou uma revisão dos recursos disponíveis." % (trace[-1]["input"], trace[-1]["goal"]),
                calculations=trace, operations=context.get("memory_operations", 0))
        if not sentences:
            message = "Ainda não tenho premissas suficientes" + (" sobre " + target if target else " para responder a esse pedido") + "."
            if mode == "assume_relation" and any(not a.get("polarity", True) for a in assumptions):
                message = "Sob a suposição desta pergunta de que a relação de oposição não vale, não posso usar essa inversão para concluir propriedades de " + target + "."
            if problem.intent == "creation":
                message += " Informe uma meta verificável, recursos e ações disponíveis para construir e testar uma solução."
            else:
                message += " Posso explorar hipóteses com relações e observações fornecidas; não tenho uma conclusão para esse alvo."
            return _unknown(problem, message)
        qualifications = problem.payload.get("qualifications", []) or frame.get("qualifications", [])
        if qualifications:
            sentences.append("Mantive as causas e qualificações como informações fornecidas; não as confirmei nem as inverti automaticamente.")
        return AnswerPackage.build(problem, "answered", sentences, conclusions=conclusions, hypotheses=hypotheses,
            premises=[{"claim_id": by_id[cid]["id"], "text": claim_text(by_id[cid]), "status": by_id[cid]["status"]}
                      for cid in sorted(evidence_ids) if cid in by_id][:112] +
                     [{"assumption": a, "scope": "current_question"} for a in assumptions],
            sources=[{"id": "M" + str(cid), "message_ids": [s["message_id"] for s in by_id[cid].get("sources", [])]}
                     for cid in sorted(evidence_ids) if cid in by_id][:128],
            calculations=trace + ([{"qualifications": qualifications}] if qualifications else []),
            verification=verification[:128], operations=min(100000, context.get("memory_operations", 0) + len(verification)),
            uncertainty={"hypotheses_are_unconfirmed": True} if hypotheses else {},
            limitations=["As afirmações do usuário são premissas, não confirmação científica independente.",
                         "Oposição e analogia geram hipóteses; composição de funções só verifica a sequência simbólica, não a viabilidade física."], domain="memory")
