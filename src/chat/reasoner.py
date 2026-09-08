"""Bounded inference with premises; analogies are proposals, never existence proofs."""
import re
from collections import defaultdict

from .domain import Proposal, claim_text, concept, normalize, predicate, tokens


# Linguistic transformations, not assertions about physics or the existence of objects.
VERBAL_PAIRS = [("absorve", "expulsa"), ("aquece", "resfria"), ("produz", "consome"),
                ("armazena", "libera"), ("aumenta", "diminui"), ("emite", "recebe"), ("permite", "impede")]
NAME_PAIRS = [("negro", "branco"), ("quente", "frio"), ("claro", "escuro"), ("entrada", "saida")]


def requested_subject(query):
    """Recognize an explicitly named topic without a domain-specific vocabulary."""
    q = normalize(query)
    match = re.match(r"^(?:o que (?:e|significa)|o que (?:voce )?(?:sabe|lembra) sobre|(?:qual (?:e|seria) )?(?:o )?(?:oposto|contrario) (?:de|do|da)|(?:explique|descreva|defina)(?: o que e)?)\s+(.+)", q)
    if not match:
        return ""
    target = re.split(r"[?!.;]|\b(?:em poucas|em termos|de forma|com um exemplo|por favor)\b", match.group(1))[0].strip()
    return concept(target)


def refers_to_previous(query):
    q = normalize(query)
    return bool(re.search(r"\b(ele|ela|eles|elas|isso|isto|dele|dela|seu|sua|esse|essa|esses|essas)\b", q)
                or re.fullmatch(r"(?:e )?(?:qual seria )?(?:o )?(?:oposto|contrario)", q))


def retrieve(query, claims, previous_subject="", limit=12, conversation_id=None):
    q = tokens(query)
    target = requested_subject(query)
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

    def explore(self, query, claims, relevant, previous_subject=""):
        q = normalize(query)
        if re.search(r"\b(oposto|contrario|inverta|inverso|oposicao)\b", q):
            return self.opposition(claims, relevant)
        if re.search(r"\b(crie|invente|combine|inove|proponha|solucao|projeto)\b", q):
            return self.compose(query, relevant)
        if re.search(r"\b(analogia|analogias|semelhante|semelhantes|paralelo|paralelos|compare|transfira|deduza)\b", q):
            return self.analogies(claims, relevant)
        return []

    def opposition(self, claims, relevant):
        inverses = {}
        for left, right in VERBAL_PAIRS:
            inverses[left], inverses[right] = (right, None), (left, None)
        names = {}
        for left, right in NAME_PAIRS:
            names[left], names[right] = right, left
        explicit_names = {}
        for c in sorted(claims, key=lambda c: c["id"]):
            if c["status"] != "asserted" or c["predicate"] != "oposto_de" or not c["polarity"]:
                continue
            l, r = predicate(c["subject"]), predicate(c["object"])
            inverses[l], inverses[r] = (r, c["id"]), (l, c["id"])
            explicit_names[c["subject"]] = (c["object"], c["id"])
            explicit_names[c["object"]] = (c["subject"], c["id"])
        proposals = []
        for c in relevant:
            if c["status"] not in {"asserted", "deduced"} or not c["polarity"] or c["predicate"] not in inverses:
                continue
            opposite, rule_id = inverses[c["predicate"]]
            premises = [c["id"]] + ([rule_id] if rule_id else [])
            if c["subject"] in explicit_names:
                name, name_id = explicit_names[c["subject"]]
                premises.append(name_id)
            else:
                name = " ".join(names.get(word, word) for word in c["subject"].split())
                if name == c["subject"]:
                    name = f"contraparte de {c['subject']}"
            proposals.append(Proposal(name, opposite, c["object"], "opposition", premises,
                f"Parti de ‘{claim_text(c)}’ e inverti a relação {c['predicate']} → {opposite}. "
                f"‘{name}’ é um nome proposto por oposição conceitual, não uma descoberta comprovada.",
                "Existe um mecanismo consistente que realize essa função? Que observação ou experimento distinguiria a hipótese de uma construção conceitual?"))
            if len(proposals) == 2:
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

    def compose(self, query, relevant):
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
