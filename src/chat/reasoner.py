"""Bounded inference with premises; analogies are proposals, never existence proofs."""
import re
from collections import defaultdict

from .domain import Proposal, claim_text, concept, normalize, predicate, tokens


# Linguistic transformations, not assertions about physics or the existence of objects.
VERBAL_PAIRS = [("absorve", "expulsa"), ("aquece", "resfria"), ("produz", "consome"),
                ("armazena", "libera"), ("aumenta", "diminui"), ("emite", "recebe"), ("permite", "impede")]

def projected_claims(claims):
    """Read legacy definitions structurally without rewriting their provenance.

    Several views may share a claim ID: each is a literal clause of that source,
    not a new observation or independently corroborated fact.
    """
    from .extraction import extract_local
    result, seen = [], set()
    for claim in claims:
        views = [claim]
        if claim["status"] in {"asserted", "deduced", "disputed"}:
            parsed = extract_local(claim_text(claim) + ".")
            if parsed:
                views = []
            for assertion in parsed:
                views.append(dict(claim, subject=assertion.subject, predicate=assertion.predicate,
                                  object=assertion.object, polarity=assertion.polarity,
                                  scope=assertion.scope, projected_from=claim["id"]))
        for view in views:
            key = (view["id"], view["subject"], view["predicate"], view["object"], view["polarity"], view["scope"])
            if key not in seen:
                result.append(view); seen.add(key)
    return result


def verify_hypothesis(claim, by_id, assumptions=None):
    """Replay a proposed transformation; this does not verify it in the world."""
    ids = claim.get("premises", [])
    if claim.get("polarity", True) is not True or claim.get("scope", "instance") != "instance":
        return False
    if not ids or any(pid not in by_id or by_id[pid]["status"] not in {"asserted", "deduced"} for pid in ids):
        return False
    premises = projected_claims([by_id[pid] for pid in ids])
    positive = [p for p in premises if p["polarity"]]
    target, relation, obj = claim["subject"], claim["predicate"], claim["object"]
    if any(c["subject"] == target and c["predicate"] == relation and c["object"] == obj
           and not c["polarity"] and c["status"] in {"asserted", "deduced", "disputed"} for c in by_id.values()):
        return False
    if claim.get("method") == "opposition":
        mappings = {a: b for left, right in VERBAL_PAIRS for a, b in ((left, right), (right, left))}
        mapping_sources = {}
        current = projected_claims(list(by_id.values()))
        # A newly supplied mapping replaces the linguistic default. Replaying
        # an old proposal must use today's mapping, not just its old parents.
        for p in sorted(current, key=lambda p: p["id"]):
            if p["predicate"] == "oposto_de" and p["polarity"] and p["status"] == "asserted":
                a, b = predicate(p["subject"]), predicate(p["object"])
                mappings[a], mappings[b] = b, a
                mapping_sources[a] = mapping_sources[b] = p["id"]
        for p in current:
            if p["predicate"] == "oposto_de" and p["status"] in {"asserted", "deduced", "disputed"} and (not p["polarity"] or p["status"] == "disputed"):
                a, b = predicate(p["subject"]), predicate(p["object"])
                if mappings.get(a) == b:
                    mappings.pop(a, None)
                if mappings.get(b) == a:
                    mappings.pop(b, None)
        for source in positive:
            if mappings.get(source["predicate"]) != relation or source["object"] != obj:
                continue
            if mapping_sources.get(source["predicate"]) and mapping_sources[source["predicate"]] not in ids:
                continue
            if any(p.get("predicate") == "oposto_de" and not p.get("polarity", True)
                   and {p["subject"], p["object"]} == {target, source["subject"]} for p in assumptions or []):
                continue
            if not assumptions and any(p["predicate"] == "oposto_de" and not p["polarity"]
                and p["status"] in {"asserted", "deduced", "disputed"}
                and {p["subject"], p["object"]} == {target, source["subject"]} for p in projected_claims(list(by_id.values()))):
                continue
            if target == "contraparte de " + source["subject"]:
                return True
            links = list(assumptions) if assumptions else positive
            if any(p.get("predicate") == "oposto_de" and p.get("polarity", True)
                   and {p["subject"], p["object"]} == {target, source["subject"]} for p in links):
                return True
        return False
    if claim.get("method") == "analogy":
        target_features = {(p["predicate"], p["object"]) for p in positive if p["subject"] == target}
        for source in positive:
            if source["subject"] == target or (source["predicate"], source["object"]) != (relation, obj):
                continue
            source_features = {(p["predicate"], p["object"]) for p in positive if p["subject"] == source["subject"]}
            if target_features & source_features and (relation, obj) not in target_features:
                return True
        return False
    if claim.get("method") == "conversion_composition":
        goal = re.fullmatch(r"(.+?) em (.+)", obj)
        if not goal or relation != "transforma":
            return False
        start, end = goal.groups()
        edges = []
        for p in positive:
            parts = re.fullmatch(r"(.+?) em (.+)", p["object"])
            if p["predicate"] in {"converte", "transforma"} and parts:
                edges.append((*tuple(concept(v) for v in parts.groups()), p["subject"]))
        frontier = [(start, [])]
        seen = set()
        for _ in range(6):
            following = []
            for state, components in frontier:
                for left, right, component in edges:
                    if state != left:
                        continue
                    path = components + [component]
                    if right == end and target == "sistema de " + " e ".join(path):
                        return True
                    key = (right, tuple(path))
                    if key not in seen:
                        seen.add(key); following.append((right, path))
                    if len(seen) > 4096:
                        return False
            frontier = following
        return False
    if claim.get("method") == "composition":
        functions = [p for p in positive if p["predicate"] not in {"é", "oposto_de"}]
        return (relation == "combina" and len({p["subject"] for p in functions}) >= 2
                and set(obj.split("; ")) == {claim_text(p) for p in functions})
    return False


def requested_subject(query):
    """Recognize an explicitly named topic without a domain-specific vocabulary."""
    q = normalize(query)
    from .discourse import focus_subject
    focused = focus_subject(query)
    if focused:
        return focused
    match = re.match(r"^(?:o que (?:e|significa)|o que (?:voce )?(?:sabe|lembra) sobre|(?:qual (?:e|seria) )?(?:o )?(?:oposto|contrario) (?:de|do|da)|(?:explique|descreva|defina)(?: o que e)?)\s+(.+)", q)
    if not match:
        return ""
    target = re.split(r"[?!.;]|\b(?:em poucas|em termos|de forma|com um exemplo|por favor)\b", match.group(1))[0].strip()
    return concept(target)


def refers_to_previous(query):
    q = normalize(query)
    return bool(re.search(r"\b(ele|ela|eles|elas|isso|isto|dele|dela|seu|sua|esse|essa|esses|essas)\b", q)
                or re.fullmatch(r"(?:e )?(?:qual seria )?(?:o )?(?:oposto|contrario)", q))


def retrieve(query, claims, previous_subject="", limit=12, conversation_id=None, frame=None):
    q = tokens(query)
    target = (frame or {}).get("target") or requested_subject(query)
    if refers_to_previous(query) and previous_subject and (not target or target in {"ele", "ela", "isso"}):
        q |= tokens(previous_subject)
        target = previous_subject
    if re.search(r"\b(meu|minha|prefiro)\b", normalize(query)):
        q.add("usuario")
    ranked = []
    for c in claims:
        words = tokens(claim_text(c))
        overlap = len(words & q)
        subject_words = tokens(c["subject"])
        direct_subject = bool(subject_words) and subject_words <= q
        object_words = tokens(c["object"])
        direct_object = bool(object_words) and object_words <= q
        if target:
            # 'Buraco de minhoca' must not match 'buraco negro' solely through
            # 'buraco'. The same rule applies to any compound concept.
            target_words = tokens(target)
            if not target_words <= words:
                continue
        coverage = overlap / max(1, min(len(q), len(words)))
        if overlap and (direct_subject or direct_object or coverage >= 0.67):
            local = any(s["conversation_id"] == conversation_id for s in c.get("sources", []))
            ranked.append((overlap * 3 + int(direct_subject) * 5 + int(local) * 2, c["id"], c))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    selected = [item[2] for item in ranked[:limit]]
    selected_ids = {c["id"] for c in selected}
    # Bring the supporting premises alongside a generated claim.
    by_id = {c["id"]: c for c in claims}
    for c in list(selected):
        for pid in c.get("premises", []):
            if pid in by_id and pid not in selected_ids:
                selected.append(by_id[pid])
                selected_ids.add(pid)
    return selected[:24]


class Reasoner:
    def __init__(self):
        self.operations = 0
        self.trace = []

    def deduce(self, claims):
        available = [c for c in claims if c["status"] in {"asserted", "deduced"}]
        universals = defaultdict(list)
        for c in available:
            if c["scope"] == "universal":
                universals[c["subject"]].append(c)
        proposals = []
        for member in available:
            if member["predicate"] != "é" or not member["polarity"] or member["scope"] != "instance":
                continue
            for rule in universals[member["object"]]:
                if rule["predicate"] == "oposto_de" or rule["object"] == member["subject"]:
                    continue
                proposals.append(Proposal(member["subject"], rule["predicate"], rule["object"], "deduction",
                    [member["id"], rule["id"]],
                    f"Se {claim_text(member)} e {claim_text(rule)}, a propriedade se aplica a {member['subject']}.",
                    "Verificar se a regra geral admite exceções e se as premissas são corretas.",
                    "deduced", rule["polarity"]))
                if len(proposals) >= 32:
                    return proposals
        return proposals

    def explore(self, query, claims, relevant, previous_subject="", frame=None):
        from .discourse import question_frame
        frame = frame or question_frame(query, previous_subject)
        self.operations, self.trace = 0, []
        claims = projected_claims(claims)
        relevant_ids = {c["id"] for c in relevant}
        relevant = [c for c in claims if c["id"] in relevant_ids]
        q = normalize(query)
        target = frame.get("target", "")
        has_link = any(c["predicate"] == "oposto_de" and c["status"] == "asserted" and c["polarity"]
                       and target in {c["subject"], c["object"]} for c in claims) if target else False
        if has_link or re.search(r"\b(oposto|contrario|inverta|inverso|oposicao)\b", q):
            return self.opposition(claims, relevant, frame)
        if re.search(r"\b(crie|invente|combine|inove|proponha|solucao|projeto)\b", q):
            return self.compose(query, relevant, claims)
        if re.search(r"\b(analogia|analogias|semelhante|semelhantes|paralelo|paralelos|compare|transfira|deduz|deduza|hipotese|hipoteses|poderia|preveja)\b", q):
            return self.analogies(claims, [c for c in relevant if not target or c["subject"] == target])
        return []

    def opposition(self, claims, relevant, frame=None):
        frame = frame or {}
        inverses = {}
        for left, right in VERBAL_PAIRS:
            inverses[left], inverses[right] = (right, None), (left, None)
        explicit_names = {}
        for c in sorted(claims, key=lambda c: c["id"]):
            if c["status"] != "asserted" or c["predicate"] != "oposto_de" or not c["polarity"]:
                continue
            l, r = predicate(c["subject"]), predicate(c["object"])
            inverses[l], inverses[r] = (r, c["id"]), (l, c["id"])
            explicit_names[c["subject"]] = (c["object"], c["id"])
            explicit_names[c["object"]] = (c["subject"], c["id"])
        for c in claims:
            if c["predicate"] == "oposto_de" and c["status"] in {"asserted", "deduced", "disputed"} and (not c["polarity"] or c["status"] == "disputed"):
                left, right = predicate(c["subject"]), predicate(c["object"])
                if inverses.get(left, (None,))[0] == right:
                    inverses.pop(left, None)
                if inverses.get(right, (None,))[0] == left:
                    inverses.pop(right, None)
        target, reference = frame.get("target", ""), frame.get("reference", "")
        mode = frame.get("mode", "")
        links = []
        for c in claims:
            if c["predicate"] != "oposto_de" or c["status"] != "asserted" or not c["polarity"]:
                continue
            if target == c["subject"] and (not reference or reference == c["object"]):
                links.append((c["object"], target, c["id"]))
            elif target == c["object"] and (not reference or reference == c["subject"]):
                links.append((c["subject"], target, c["id"]))
        if mode == "assume_relation":
            links = []  # The current hypothetical world overrides this link.
            for assumption in frame.get("temporary_assumptions", []):
                if assumption.get("predicate") == "oposto_de" and assumption.get("polarity", True):
                    if target == assumption["subject"]:
                        links.append((assumption["object"], target, None))
                    elif target == assumption["object"]:
                        links.append((assumption["subject"], target, None))
            if not links:
                return []
        if mode == "ask_relation" and target and not links:
            return []  # A question does not supply its own answer as a premise.
        if links:
            base = [(c, name, link_id) for source, name, link_id in links for c in claims if c["subject"] == source]
        else:
            # Only an explicit request to construct an opposite permits a new,
            # generic name. Color words never identify a scientific entity.
            base = []
            for c in relevant:
                if target and c["subject"] != target:
                    continue
                name, link_id = explicit_names.get(c["subject"], ("contraparte de " + c["subject"], None))
                base.append((c, name, link_id))
        proposals = []
        seen = set()
        for c, name, name_id in base:
            self.operations += 1
            if c["status"] not in {"asserted", "deduced"} or not c["polarity"] or c["predicate"] not in inverses:
                continue
            opposite, rule_id = inverses[c["predicate"]]
            premises = [c["id"]] + ([rule_id] if rule_id else [])
            if name_id is not None:
                premises.append(name_id)
            key = (name, opposite, c["object"])
            blocked = any(p["subject"] == name and p["predicate"] == opposite and p["object"] == c["object"]
                          and not p["polarity"] and p["status"] in {"asserted", "deduced", "disputed"} for p in claims)
            if blocked or key in seen:
                continue
            seen.add(key)
            self.trace.append({"operation": "functional_opposition", "source": c["subject"], "target": name,
                               "mapping": [c["predicate"], opposite], "object": c["object"],
                               "premise_ids": list(dict.fromkeys(premises)), "temporary": mode == "assume_relation",
                               "mapping_origin": "user_relation" if rule_id else "declared_linguistic_prior"})
            proposals.append(Proposal(name, opposite, c["object"], "opposition", premises,
                f"Parti de ‘{claim_text(c)}’ e explorei a oposição funcional {c['predicate']} → {opposite}. "
                f"Se essa for a função que você pretende inverter, a previsão a testar é ‘{name} {opposite} {c['object']}’. "
                "A relação de oposição, sozinha, não prova essa propriedade; outras características e causas não foram invertidas.",
                f"Verificar se {name} realmente {opposite} {c['object']}, sob condições definidas, e comparar com ausência dessa função. "
                "É necessário identificar um mecanismo e medições; o nome não demonstra existência."))
            if len(proposals) == 4:
                break
        return proposals

    def analogies(self, claims, relevant):
        entities = defaultdict(list)
        for c in claims:
            if c["status"] in {"asserted", "deduced"} and c["scope"] == "instance" and c["polarity"] and c["predicate"] != "oposto_de":
                entities[c["subject"]].append(c)
        target_names = list(dict.fromkeys(c["subject"] for c in relevant))[:4]
        candidates = []
        for target in target_names:
            target_features = {(c["predicate"], c["object"]): c for c in entities[target]}
            for source, source_claims in entities.items():
                self.operations += 1
                if source == target:
                    continue
                source_features = {(c["predicate"], c["object"]): c for c in source_claims}
                shared = set(target_features) & set(source_features)
                if not shared:
                    continue
                for feature in sorted(set(source_features) - set(target_features)):
                    transferred = source_features[feature]
                    blocked = any(c["subject"] == target and c["predicate"] == feature[0] and c["object"] == feature[1] and not c["polarity"] and c["status"] in {"asserted", "disputed"} for c in claims)
                    if blocked:
                        continue
                    premises = [transferred["id"]]
                    for f in sorted(shared)[:3]:
                        premises.extend([target_features[f]["id"], source_features[f]["id"]])
                    candidates.append((len(shared), Proposal(target, feature[0], feature[1], "analogy", premises,
                        f"{target} e {source} compartilham {len(shared)} relação(ões). "
                        f"Como {claim_text(transferred)}, proponho testar a mesma propriedade em {target}. Similaridade não garante transferência.",
                        f"Testar se {target} {feature[0]} {feature[1]} e buscar diferenças que invalidem a analogia.")))
        candidates.sort(key=lambda pair: pair[0], reverse=True)
        return [p for _, p in candidates[:3]]

    def compose(self, query, relevant, claims=None):
        goal = re.search(r"(?:transformar|converter|transforme|converta)\s+(.+?)\s+em\s+(.+?)(?:[.!?;]|$)", normalize(query))
        if goal:
            start, target = [concept(v) for v in goal.groups()]
            edges = []
            for c in claims or relevant:
                if c["status"] not in {"asserted", "deduced"} or not c["polarity"] or c["predicate"] not in {"converte", "transforma"}:
                    continue
                parts = re.fullmatch(r"(.+?) em (.+)", c["object"])
                if parts:
                    left, right = [concept(v) for v in parts.groups()]
                    edges.append((left, right, c))
            queue, visited = [(start, [])], {start}
            while queue and self.operations < 4096:
                current, path = queue.pop(0)
                if current == target and path:
                    chain = [start] + [right for _, right, _ in path]
                    # Replay the graph separately from the search's state.
                    state = start
                    for left, right, _ in path:
                        if left != state:
                            return []
                        state = right
                    artifact = {"operation": "conversion_composition", "input": start, "goal": target,
                                "steps": [{"component": c["subject"], "input": left, "output": right,
                                           "premise_id": c["id"]} for left, right, c in path],
                                "chain": chain, "symbolic_goal_verified": state == target,
                                "physical_feasibility_verified": False}
                    self.trace.append(artifact)
                    return [Proposal("sistema de " + " e ".join(c["subject"] for _, _, c in path), "transforma", start + " em " + target,
                        "conversion_composition", list(dict.fromkeys(c["id"] for _, _, c in path)),
                        "Construí a sequência " + " → ".join(chain) + ". Componentes: " + " → ".join(c["subject"] for _, _, c in path) +
                        ". A sequência atende à meta simbolicamente sob as funções informadas; perdas, escala e compatibilidade física precisam de teste.",
                        "Medir entrada e saída de cada etapa, verificar interfaces e comparar o resultado final com a meta, incluindo perdas e recursos.")]
                if len(path) >= 6:
                    continue
                for edge in edges:
                    self.operations += 1
                    if edge[0] == current and edge[1] not in visited:
                        visited.add(edge[1]); queue.append((edge[1], path + [edge]))
            self.trace.append({"operation": "conversion_composition", "input": start, "goal": target,
                               "symbolic_goal_verified": False, "reason": "no_path_in_supplied_functions"})
            return []
        relevant = [c for c in relevant if c["status"] in {"asserted", "deduced"} and c["polarity"] and c["predicate"] not in {"é", "oposto_de"}]
        by_subject = {}
        for c in relevant:
            by_subject.setdefault(c["subject"], c)
        if len(by_subject) < 2:
            return []
        parts = list(by_subject.values())[:3]
        purpose = "; ".join(claim_text(c) for c in parts)
        return [Proposal("sistema combinado de " + " e ".join(c["subject"] for c in parts), "combina", purpose,
            "composition", [c["id"] for c in parts],
            "Proponho combinar funções conhecidas: " + purpose + ". A compatibilidade entre os componentes ainda precisa ser testada.",
            "Definir a interface entre as funções; medir se o conjunto atende à meta; testar custos, incompatibilidades e efeitos indesejados.")]
