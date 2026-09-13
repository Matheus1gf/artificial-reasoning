"""Own Portuguese/JSON question processor with explicit ambiguity and scope.

This finite grammar does not claim open-language understanding. Original words,
negation, units, source spans and typed requests survive before any rendering.
"""
import json
import re
from dataclasses import asdict

from .contracts import ProblemSpec
from src.chat.domain import concept, normalize
from src.chat.extraction import extract_local_details, is_correction
from src.chat.discourse import question_frame
from src.chat.reasoner import requested_subject


UNITS = {
    "m": (1.0, [1, 0, 0]), "metro": (1.0, [1, 0, 0]), "metros": (1.0, [1, 0, 0]),
    "cm": (0.01, [1, 0, 0]), "km": (1000.0, [1, 0, 0]),
    "s": (1.0, [0, 1, 0]), "segundo": (1.0, [0, 1, 0]), "segundos": (1.0, [0, 1, 0]),
    "min": (60.0, [0, 1, 0]), "h": (3600.0, [0, 1, 0]),
    "kg": (1.0, [0, 0, 1]), "g": (0.001, [0, 0, 1]),
    "m/s": (1.0, [1, -1, 0]), "km/h": (1000.0 / 3600.0, [1, -1, 0]),
    "m/s2": (1.0, [1, -2, 0]), "m/s²": (1.0, [1, -2, 0]),
    "n": (1.0, [1, -2, 1]), "j": (1.0, [2, -2, 1]), "hz": (1.0, [0, -1, 0]),
}
UNIT_PATTERN = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
QUANTITY = re.compile(r"(?<![\w.])([+-]?\d+(?:[.,]\d+)?)\s*(" + UNIT_PATTERN + r")(?![\w/])", re.I)
PRONOUN = re.compile(r"\b(ele|ela|isso|isto|esse objeto|essa entidade)\b")
STRUCTURED_TASKS = {"deduce": "question", "plan": "plan", "induce": "induction", "abduce": "abduction",
                    "analogy": "analogy", "causal": "causal", "counterfactual": "counterfactual",
                    "invent": "creation", "calculate": "calculation", "classify": "question",
                    "learn_operator": "induction", "apply_operator": "calculation", "test_operator": "correction"}


def conversation_context(history):
    """Use only the supplied conversation, never a global last message."""
    for item in reversed(history or []):
        if item.get("role") != "assistant":
            continue
        metadata = item.get("metadata", {})
        problem = metadata.get("problem", {})
        focus = metadata.get("focus", "")
        entities = problem.get("entities", []) or ([focus] if focus else [])
        package = metadata.get("answer_package")
        return {"subject": focus, "entities": entities[:8], "active_goal": problem.get("goals", []),
                "pending": package.get("clarification", []) if isinstance(package, dict) else [],
                "previous_approved": package if isinstance(package, dict) else None,
                "message_id": item.get("id")}
    return {"subject": "", "entities": [], "active_goal": [], "pending": [], "message_id": None}


def quantities_in(message):
    quantities = []
    for index, match in enumerate(QUANTITY.finditer(message)):
        value = float(match.group(1).replace(",", "."))
        if abs(value) > 1e12:
            raise ValueError("Quantidade fora do intervalo suportado (±10¹²).")
        unit = match.group(2).lower()
        factor, dimensions = UNITS[unit]
        quantities.append({"id": "q" + str(index), "value": value, "unit": unit,
                           "si_value": value * factor, "dimensions": dimensions,
                           "quote": match.group(), "span": list(match.span())})
    return quantities


def _structured(message, cid, context):
    try:
        value = json.loads(message)
    except (ValueError, RecursionError):
        raise ValueError("A entrada estruturada deve ser JSON válido.")
    if not isinstance(value, dict):
        raise ValueError("A tarefa estruturada deve ser um objeto JSON.")
    if "domain" in value:
        if (set(value) - {"domain", "operation", "parameters"} or not isinstance(value["domain"], str)
                or value["domain"] not in {"physics", "quantum", "discovery"}):
            raise ValueError("Domínio ou campos da solicitação científica inválidos.")
        if not isinstance(value.get("operation"), str) or not isinstance(value.get("parameters", {}), dict):
            raise ValueError("Informe operation e parameters no pedido científico.")
        return ProblemSpec.build(message, cid, "domain_request", payload={"request": value}, context=context)
    task = value.get("task")
    if not isinstance(task, str) or task not in STRUCTURED_TASKS:
        raise ValueError("Tarefa estruturada desconhecida. Use deduce, plan, induce, abduce, analogy, causal, counterfactual, invent ou calculate.")
    return ProblemSpec.build(message, cid, STRUCTURED_TASKS[task], payload={"structured": value},
                             question={"task": task}, context=context,
                             goals=[{"target": value["goal"]}] if "goal" in value else [])


def process_message(message, history=None, claims=None, conversation_id="local"):
    if not isinstance(message, str) or not message.strip() or len(message) > 8000:
        raise ValueError("Escreva uma mensagem de até 8.000 caracteres.")
    context = conversation_context(history)
    if message.lstrip().startswith("{") or message.lstrip().startswith("["):
        return _structured(message, conversation_id, context)
    q = normalize(message)
    ambiguities, constraints, entities, goals = [], {}, [], []
    discourse = question_frame(message, context["subject"])
    current_subject = discourse["target"] or requested_subject(message)
    referents = list(dict.fromkeys(context["entities"]))
    has_reference = bool(PRONOUN.search(q))
    if has_reference and (not current_subject or current_subject in {"ele", "ela", "isso", "isto"}):
        if len(referents) == 1:
            current_subject = referents[0]
        else:
            ambiguities.append({"kind": "referent", "candidates": referents,
                                "question": "A qual entidade você se refere?"})
    previous_subject = current_subject if has_reference and not ambiguities else context["subject"]
    extracted = {"assertions": [], "qualifications": [], "ambiguities": []} if ambiguities else extract_local_details(message, previous_subject)
    assertions = [asdict(a) for a in extracted["assertions"]]
    ambiguities.extend(extracted["ambiguities"])
    ambiguities.extend(discourse["ambiguities"])
    discourse["qualifications"].extend(extracted["qualifications"])
    entities = list(dict.fromkeys(a["subject"] for a in assertions))
    if current_subject and current_subject not in {"ele", "ela", "isso", "isto"} and current_subject not in entities:
        entities.append(current_subject)
    if not entities and has_reference and not ambiguities:
        entities = referents
    intent = "unknown"
    if is_correction(message):
        intent = "correction"
    elif re.match(r"^(?:talvez|hipotese|acho que|suponho que|penso que)\b", q):
        intent = "hypothesis"
    elif re.match(r"^(?:oi|ola|bom dia|boa tarde|boa noite|obrigad[oa])\b", q):
        intent = "greeting"
    elif re.match(r"^(?:resuma|reescreva|explique (?:isso|melhor)|repita)\b", q) or "ultima resposta" in q:
        intent = "summary"
        if not context.get("previous_approved"):
            ambiguities.append({"kind": "previous_content", "question": "Ainda não há uma resposta aprovada pelo núcleo nesta conversa para retomar."})
        else:
            entities = referents
    elif re.match(r"^(?:calcule|quanto (?:e|da)|qual (?:e )?o resultado)\b", q):
        intent = "calculation"
    elif re.search(r"\b(crie|invente|combine|proponha|solucao)\b", q):
        intent = "creation"
        goals = [{"description": message}]
    elif discourse["mode"] == "explore":
        intent = "question"
    elif re.search(r"\b(analogia|analogias|compare|transfira|semelhante)\b", q):
        intent = "analogy"
    elif re.match(r"^(?:aprenda|lembre|considere)\b", q) and assertions:
        intent = "statement"
    elif discourse["mode"] or "?" in message or re.match(r"^(?:o que|qual|quais|como|quem|onde|quando|por que|explique|descreva|defina|deduza)\b", q):
        intent = "question"
    elif assertions:
        intent = "preference" if all(a["predicate"] in {"prefere", "chama-se"} for a in assertions) else "statement"

    word_limit = re.search(r"(?:exatamente|ate|em)\s+(\d+)\s+palavras", q)
    if word_limit:
        count = int(word_limit.group(1))
        if not 1 <= count <= 1000:
            ambiguities.append({"kind": "format", "question": "Use um limite entre 1 e 1.000 palavras."})
        constraints["words"] = {"value": count, "exact": "exatamente" in word_limit.group()}
    if re.search(r"\b(?:em|formato) json\b", q):
        constraints["format"] = "json"
    if re.search(r"\bnao\b", q):
        constraints["negation_present"] = True
    quantities = quantities_in(message)
    intervals = []
    for match in re.finditer(r"entre\s+([+-]?\d+(?:[.,]\d+)?)\s+e\s+([+-]?\d+(?:[.,]\d+)?)\s*(" + UNIT_PATTERN + r")\b", message, re.I):
        low, high = [float(v.replace(",", ".")) for v in match.groups()[:2]]
        intervals.append({"lower": low, "upper": high, "unit": match.group(3).lower(), "quote": match.group()})
        if low > high:
            ambiguities.append({"kind": "interval", "question": "O limite inferior do intervalo excede o superior; confirme os valores."})
    payload = {"quantities": quantities, "intervals": intervals,
               "equations": re.findall(r"\b[A-Za-z][A-Za-z0-9_]*\s*=\s*[^;\n]+", message),
               "temporal": [{"relation": normalize(match.group()), "span": list(match.span())}
                            for match in re.finditer(r"\b(antes|depois|ontem|hoje|amanh[ãa]|agora|durante)\b", message, re.I)],
               "conditional": q.startswith("se ") or bool(discourse["temporary_assumptions"]),
               "discourse": discourse,
               "qualifications": extracted["qualifications"],
               "scope": "Português controlado: afirmações, correções, referências, cálculo e pedidos estruturados."}
    # The measured classifier has weak held-out accuracy. Keep its proposal
    # inspectable, but never let a neural probability manufacture a fact.
    from .neural import local_intent
    try:
        proposal = local_intent(message)
        if proposal:
            payload["neural_proposal"] = dict(proposal, adopted=False,
                role="experimental intent proposal; grammar controls semantic extraction")
    except (ValueError, OSError, KeyError):
        payload["neural_proposal"] = {"adopted": False, "status": "checkpoint_unavailable"}
    if intent == "calculation":
        expression = re.sub(r"^(?:calcule|quanto (?:é|e|dá|da)|qual (?:é |e )?o resultado(?: de)?)\s*", "", message, flags=re.I).strip(" .?!")
        variables = {}
        # Replace original quantity spans within the expression, longest first.
        for quantity in quantities:
            name = "q" + str(len(variables))
            if quantity["quote"] in expression:
                expression = expression.replace(quantity["quote"], name, 1)
                variables[name] = {"value": quantity["si_value"], "dimensions": quantity["dimensions"]}
        expression = expression.replace("×", "*").replace("÷", "/")
        expression = re.sub(r"(?<=\d),(?=\d)", ".", expression)
        payload["calculation"] = {"expression": expression, "variables": variables}
    relations = [{"predicate": a["predicate"], "arguments": [a["subject"], a["object"]],
                  "polarity": a["polarity"], "scope": a["scope"]} for a in assertions]
    return ProblemSpec.build(message, conversation_id, intent, entities=entities[:32], facts=assertions,
                             relations=relations, question={"subject": current_subject, "text": message},
                             goals=goals, constraints=constraints, context=context,
                             ambiguities=ambiguities, payload=payload)
