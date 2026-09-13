"""Small own discourse frames, independent of an LLM or privileged subject names.

Frames identify the requested target and temporary premises. They never invent
a relation from entity names or promote a premise inside a question to memory.
"""
import re

from .domain import VERBS, concept, normalize, predicate


OPPOSITE = r"(?:oposto|oposta|inverso|inversa|contrario|contraria)"
OPPOSITION = re.compile(r"^(.+?)\s+(nao\s+)?(?:e|seria)\s+(?:(?:o|a|um|uma)\s+)?(" + OPPOSITE + r")\s+(?:de|do|da)\s+(.+)$")
INTRO = re.compile(r"^(considerando|supondo|admitindo|assumindo|sabendo|dado)(?:\s+que)?\s+(.+?)\s*,\s*(.+)$")
QUESTION_START = re.compile(r"^(?:o que|qual|quais|como|quem|onde|quando|por que|seria|sera que|explique|descreva|defina|deduza|explore|investigue|crie|invente|imagine|proponha|compare)\b")
MODAL = re.compile(r"\b(?:pode|poderia|deve|deveria|disse que|diz que|afirme|finja)\b")
QUOTED = re.compile(r'["“”‘’`]|\b(?:segundo|citando|a frase|o texto diz|foi dito que)\b')
VERB_PATTERN = "|".join(sorted((re.escape(v) for v in VERBS if v not in {"e", "sao", "ser"}), key=len, reverse=True))


def _entity(text):
    value = concept(text).strip(" ,:")
    if not 0 < len(value) <= 120 or re.search(r"[,;.!?]|\b(?:que|se|porque|por causa|devido|talvez)\b", value):
        return ""
    return value


def opposition_statement(sentence):
    """Parse an explicitly stated lexical opposition; truth is not decided here."""
    q = normalize(sentence)
    match = OPPOSITION.fullmatch(q)
    if match:
        left, negative, label, right = match.groups()
        left, right = _entity(left), _entity(right)
        if left and right:
            return {"subject": predicate(left), "predicate": "oposto_de", "object": predicate(right),
                    "polarity": not bool(negative), "scope": "instance", "relation_label": label}
    match = re.fullmatch(r"(?:o |a )?(" + OPPOSITE + r")\s+(?:de|do|da)\s+(.+?)\s+e\s+(.+)", q)
    if match:
        label, left, right = match.groups()
        left, right = _entity(left), _entity(right)
        if left and right:
            return {"subject": predicate(left), "predicate": "oposto_de", "object": predicate(right),
                    "polarity": True, "scope": "instance", "relation_label": label}
    return None


def _question_target(text):
    q = normalize(text)
    # Search the final interrogative span. The prefatory topic is not its target.
    matches = list(re.finditer(r"\b(?:o que|quem)\s+(?:e|seria|sao|seriam)\s+(.+)$", q))
    if matches:
        candidate = matches[-1].group(1)
        candidate = re.split(r"\s+(?:considerando|sabendo|se)\b|,", candidate, maxsplit=1)[0]
        return _entity(candidate)
    match = re.fullmatch(r"(?:explique|descreva|defina)(?:\s+(?:o que e|sobre))?\s+(.+)", q)
    if match:
        return _entity(match.group(1))
    match = re.fullmatch(r"(?:o que (?:voce )?(?:sabe|conhece)|quais (?:as )?propriedades|qual (?:e )?a funcao)\s+(?:sobre|de|do|da)\s+(.+)", q)
    if match:
        return _entity(match.group(1))
    match = re.fullmatch(r"como\s+(.+?)\s+(?:funciona|funcionaria|se comporta|se comportaria)", q)
    if match:
        return _entity(match.group(1))
    match = re.match(r"(?:o que|como)\s+(.+?)\s+(?:faria|faz|poderia fazer|funcionaria|se comportaria)(?:\s|$)", q)
    return _entity(match.group(1)) if match else ""


def question_frame(text, previous_subject=""):
    frame = {"target": "", "reference": "", "relation": "", "mode": "", "temporary_assumptions": [],
             "qualifications": [], "ambiguities": []}
    if not isinstance(text, str) or not text.strip() or len(text) > 8000:
        return frame
    q = normalize(text)
    if QUOTED.search(q) or QUOTED.search(text.casefold()):
        return frame
    intro, main = "", q
    prefix = INTRO.fullmatch(q)
    if prefix:
        _, intro, main = prefix.groups()
    treated = re.fullmatch(r"tratando\s+(.+?)\s+como\s+(?:(?:o|a|um|uma)\s+)?(" + OPPOSITE + r")\s+(?:de|do|da)\s+(.+?),\s*(.+)", q)
    if treated:
        subject, label, reference, main = treated.groups()
        intro = subject + " e o " + label + " de " + reference
    trailing = re.fullmatch(r"(.+?),\s*(?:considerando|tendo em vista)(?:\s+o que (?:sabemos|sabe) sobre)?\s+(.+)", main)
    if trailing and not intro:
        main, intro = trailing.groups()
    is_query = "?" in text or bool(QUESTION_START.match(main)) or bool(prefix and QUESTION_START.match(main))
    if not is_query:
        return frame
    frame["target"] = _question_target(main)
    frame["mode"] = "describe"
    if re.search(r"\b(?:crie|invente|imagine|proponha|combine)\b", main):
        frame["mode"] = "create"
    elif re.search(r"\b(?:explore|investigue|deduza|hipotese|hipoteses|poderia)\b", main):
        frame["mode"] = "explore"
    if intro:
        assumption = opposition_statement(intro)
        if assumption and not MODAL.search(intro):
            frame["target"] = frame["target"] or assumption["subject"]
            if frame["target"] in {assumption["subject"], assumption["object"]}:
                # Orient the discourse around the entity actually questioned.
                # Preserve the original assumption's direction for provenance.
                frame["reference"] = assumption["object"] if frame["target"] == assumption["subject"] else assumption["subject"]
                frame["relation"] = "opposition"
                frame["mode"] = "assume_relation"
                frame["temporary_assumptions"] = [{k: v for k, v in assumption.items() if k != "relation_label"}]
                frame["temporary_assumptions"][0].update(quote=text, tentative=True)
                frame["relation_label"] = assumption["relation_label"]
            else:
                frame["qualifications"].append({"kind": "unrelated_temporary_assumption", "assumption": assumption,
                                                "quote": text, "applied_to_target": False})
        else:
            frame["reference"] = _entity(intro)
            if frame["reference"]:
                frame["mode"] = "ask_relation"
    explicit_question = opposition_statement(main)
    if explicit_question:
        frame.update(target=explicit_question["subject"], reference=explicit_question["object"], relation="opposition", mode="ask_relation",
                     queried_polarity=explicit_question["polarity"], relation_label=explicit_question["relation_label"])
    role_question = re.fullmatch(r"(?:o que|como)\s+(.+?)\s+(?:faria|faz|poderia fazer|funcionaria|se comportaria)\s+(?:como\s+(?:(?:o|a|um|uma)\s+)?(" + OPPOSITE + r")\s+(?:de|do|da)|em oposicao (?:a|ao|aos|as))\s+(.+)", main)
    if role_question:
        target, label, reference = role_question.groups()
        target, reference = _entity(target), _entity(reference)
        if target and reference:
            frame.update(target=target, reference=reference, relation="opposition", mode="ask_relation", relation_label=label or "oposicao")
    opposite_query = re.search(r"\b(?:o que (?:e|seria)|qual (?:e|seria)|(?:crie|invente|imagine|proponha)(?:\s+uma? (?:hipotese|conceito))?(?:\s+para)?)\s+(?:(?:o|a|um|uma)\s+)?(" + OPPOSITE + r")\s+(?:de|do|da)\s+(.+)$", main)
    if opposite_query:
        reference = _entity(opposite_query.group(2))
        if reference:
            frame.update(target="", reference=reference, relation="opposition", relation_label=opposite_query.group(1))
            if frame["mode"] not in {"create", "explore"}:
                frame["mode"] = "ask_relation"
    # Ordinary creative requests retain their human-readable goal; supplied
    # prepositional topics become references, never new asserted properties.
    if frame["mode"] in {"create", "explore"} and not frame["reference"]:
        topic = re.search(r"\b(?:sobre|considerando|a partir de|com base em)\s+(.+)$", main)
        if topic:
            frame["reference"] = _entity(topic.group(1))
        elif re.search(r"\b(?:isso|ele|ela|esse objeto|essa entidade)\b", main):
            frame["reference"] = concept(previous_subject) if previous_subject else ""
    if frame["target"] in {"ele", "ela", "isso", "isto", "esse objeto", "essa entidade"} and previous_subject:
        frame["target"] = concept(previous_subject)
    return frame


def focus_subject(text):
    """Return only an explicitly requested entity, not a prefatory reference."""
    return question_frame(text).get("target", "")


def definition_parts(sentence, quote, previous_subject=""):
    """Conservative asserted relative clauses, with causal text kept separate.

    Input has already had correction/tentative prefixes removed by extraction.
    Return None for ordinary sentences; a recognized-but-unsafe definition
    returns no facts plus a qualification instead of a giant object string.
    """
    q = normalize(sentence)
    match = re.fullmatch(r"(.+?)\s+(nao\s+)?e\s+(?:(?:um|uma|o|a)\s+)?(.+?)\s+que\s+(.+)", q)
    if not match:
        return None
    subject, negative, kind, relative = match.groups()
    subject = concept(previous_subject) if subject in {"ele", "ela", "isso", "esse objeto", "essa entidade"} and previous_subject else _entity(subject)
    kind = _entity(kind)
    result = {"facts": [], "qualifications": [], "ambiguities": []}
    if not subject or not kind or subject in {"ele", "ela", "isso", "esse objeto", "essa entidade"}:
        return result
    if negative:
        result["ambiguities"].append({"kind": "negated_relative_scope", "question": "A negação se refere ao tipo de " + subject + " ou à propriedade descrita depois de 'que'?"})
        return result
    if QUOTED.search(q) or QUOTED.search(quote.casefold()) or MODAL.search(q) or re.search(r"\b(?:se|talvez|possivelmente)\b", q):
        result["qualifications"].append({"kind": "unresolved_definition", "subject": subject, "quote": quote,
                                         "meaning": "Citação, modalidade ou condição não foi promovida a fato."})
        return result
    result["facts"].append({"subject": subject, "predicate": "é", "object": kind, "polarity": True})
    return _action_clauses(result, subject, relative, quote)


def action_parts(sentence, quote, previous_subject=""):
    """Parse ordinary functional clauses with the same causal/negation limits."""
    q = normalize(sentence)
    match = re.fullmatch(r"(.+?)\s+(nao\s+)?(" + VERB_PATTERN + r")\s+(.+)", q)
    if not match:
        return None
    subject, negative, verb, objects = match.groups()
    if subject in {"ele", "ela", "isso", "esse objeto", "essa entidade"}:
        subject = concept(previous_subject) if previous_subject else ""
    else:
        subject = _entity(subject)
    result = {"facts": [], "qualifications": [], "ambiguities": []}
    if not subject:
        return result
    if QUOTED.search(q) or QUOTED.search(quote.casefold()) or MODAL.search(q) or re.search(r"\b(?:se|talvez|possivelmente)\b", q):
        result["qualifications"].append({"kind": "unresolved_function", "subject": subject, "quote": quote})
        return result
    return _action_clauses(result, subject, (negative or "") + verb + " " + objects, quote)


def _action_clauses(result, subject, relative, quote):
    cause = re.split(r"\s+(?:(?:por causa|em razao|por conta) (?:de|do|da|dos|das)|(?:devido|gracas) (?:a|ao|aos|as)|porque)\s+", relative, maxsplit=1)
    relative = cause[0]
    if len(cause) == 2:
        result["qualifications"].append({"kind": "reported_cause", "subject": subject, "text": cause[1], "quote": quote,
                                         "epistemic_status": "user_supplied_qualification", "causal_model_inferred": False,
                                         "transferable_by_opposition": False})
    clauses = re.split(r"\s+e\s+(?=(?:nao\s+)?(?:" + VERB_PATTERN + r")\s)", relative)
    if len(clauses) > 4:
        result["qualifications"].append({"kind": "unresolved_relative_clause", "subject": subject, "text": relative, "quote": quote})
        return result
    for clause in clauses:
        match = re.fullmatch(r"(nao\s+)?(" + VERB_PATTERN + r")\s+(.+)", clause)
        if not match:
            result["qualifications"].append({"kind": "unresolved_relative_clause", "subject": subject, "text": clause, "quote": quote})
            continue
        negative, verb, objects = match.groups()
        # Each repeated verb starts a separate polarity scope. Within one verb,
        # only uniform-polarity conjunctions of noun phrases are decomposed.
        if negative and re.search(r"\s+e\s+", objects):
            result["ambiguities"].append({"kind": "negative_conjunction_scope", "question": "A negação vale para cada objeto separadamente? Use 'nem ... nem ...' para negar ambos."})
            continue
        if negative:
            objects = re.sub(r"^nem\s+", "", objects)
        separator = r"\s+nem\s+" if negative else r"\s+e\s+"
        nouns = re.split(separator, objects)
        if (not 1 <= len(nouns) <= 4 or re.search(r"\b(?:ou|nao|que|se)\b", objects)
                or any(re.search(r"\b(?:" + VERB_PATTERN + r")\b", noun) for noun in nouns)
                or (not negative and re.search(r"\bnem\b", objects)) or not all(_entity(noun) for noun in nouns)):
            result["qualifications"].append({"kind": "unresolved_relative_clause", "subject": subject, "text": clause, "quote": quote})
            continue
        for obj in nouns:
            result["facts"].append({"subject": subject, "predicate": predicate(verb), "object": _entity(obj), "polarity": not bool(negative)})
    return result
