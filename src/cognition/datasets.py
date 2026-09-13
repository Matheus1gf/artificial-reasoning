"""Project-authored annotated fixtures, with template and entity split manifests."""
import hashlib


TEMPLATES = {
    "statement": ["{e} emite luz.", "{e} absorve energia.", "Todo {e} conduz calor.", "Aprenda: {e} armazena água.", "Lembre: {e} produz energia."],
    "question": ["O que sabe sobre {e}?", "Qual é a função de {e}?", "Explique {e}.", "Você sabe o que é {e}?", "Pode me dizer o que {e} faz?"],
    "calculation": ["Calcule {n} + 3.", "Quanto é {n} vezes 2?", "Calcule {n} m + 20 cm.", "Qual o resultado de {n} / 2?", "Faça a conta {n} + 4."],
    "creation": ["Crie uma solução usando {e}.", "Invente uma máquina com {e}.", "Proponha uma solução para {e}.", "Combine as funções de {e} em um projeto.", "Desenvolva uma ideia de sistema para {e}."],
    "correction": ["Corrigindo: {e} não emite luz.", "Na verdade, {e} absorve calor.", "Correção: {e} armazena água.", "Retificando: {e} não produz energia.", "Corrija: {e} emite calor."],
    "hypothesis": ["Talvez {e} produza luz.", "Acho que {e} absorve energia.", "Hipótese: {e} emite luz.", "Suponho que {e} conduza calor.", "Penso que {e} pode produzir energia."],
    "summary": ["Resuma a última resposta.", "Reescreva isso em {n} palavras.", "Explique isso melhor.", "Repita a resposta anterior.", "Faça um resumo do que você acabou de responder."],
    "greeting": ["Olá!", "Oi, tudo bem?", "Bom dia.", "Boa tarde, vamos conversar.", "Boa noite!"],
    "analogy": ["Faça uma analogia para {e}.", "Compare {e} com o outro objeto.", "Transfira as relações por analogia para {e}.", "Que analogias podemos criar para {e}?", "Encontre uma relação semelhante à de {e}."],
    "preference": ["Prefiro respostas curtas.", "Meu nome é {e}.", "Eu prefiro explicações com {n} exemplos.", "Prefiro aprender com exemplos de {e}.", "Meu nome é {e} e prefiro linguagem simples."],
}
NAMES = {"training": ["Aran", "Beral", "Cetra", "Dorin", "Elera", "Feron"],
         "validation": ["Ganor", "Heral", "Ivera", "Jorin", "Kelar", "Luron"],
         "held_out": ["Miren", "Naral", "Ovel", "Pirel", "Queral", "Ravel"]}


def language_corpus():
    corpus = {key: [] for key in NAMES}
    seen_texts = set()
    for split, names in NAMES.items():
        template_indices = range(3) if split == "training" else [3] if split == "validation" else [4]
        for label, templates in TEMPLATES.items():
            for index in template_indices:
                for number, entity in enumerate(names, 2):
                    text = templates[index].format(e=entity, n=number)
                    # Identical greetings/summaries are one observation, not six
                    # artificial repetitions. Corpus text never crosses splits.
                    if text in seen_texts:
                        continue
                    seen_texts.add(text)
                    corpus[split].append({"id": hashlib.sha256((split + ":" + label + ":" + text).encode()).hexdigest()[:20],
                                          "text": text, "intent": label, "template_id": label + ":" + str(index),
                                          "entities_used": [entity] if "{e}" in templates[index] else [],
                                          "provenance": "project-authored controlled templates; no Qwen generation or user conversations"})
    return corpus


def context_corpus():
    """Semantic annotations beyond intent: context, negation, typo, quantities."""
    def history(entities):
        return [{"role": "assistant", "metadata": {"focus": entities[0] if entities else "",
                  "problem": {"entities": entities, "goals": []}}}]
    return [
        {"id": "context-single", "text": "Ele emite luz.", "history": history(["neral"]), "expected": {"intent": "statement", "entities": ["neral"], "ambiguous": False}},
        {"id": "context-multiple", "text": "Ele emite luz.", "history": history(["neral", "vetra"]), "expected": {"entities": [], "ambiguous": True, "facts": []}},
        {"id": "context-empty", "text": "Ele emite luz.", "history": [], "expected": {"ambiguous": True, "facts": []}},
        {"id": "context-switch", "text": "O que é um buraco de minhoca?", "history": history(["buraco negro"]), "expected": {"intent": "question", "entities": ["buraco de minhoca"], "ambiguous": False}},
        {"id": "negation", "text": "Neral não emite luz.", "history": [], "expected": {"intent": "statement", "polarity": False}},
        {"id": "universal", "text": "Todo cristal emite luz.", "history": [], "expected": {"scope": "universal"}},
        {"id": "correction", "text": "Corrigindo: Neral não emite luz.", "history": [], "expected": {"intent": "correction", "polarity": False}},
        {"id": "typo-object", "text": "Neral emite luzz.", "history": [], "expected": {"intent": "statement", "object": "luzz"}},
        {"id": "typo-question", "text": "Explike o que é Neral?", "history": [], "expected": {"intent": "question"}},
        {"id": "unit-conversion", "text": "Calcule 2 m + 30 cm.", "history": [], "expected": {"intent": "calculation", "quantities": 2}},
        {"id": "unit-negative", "text": "Calcule -2 m / 4 s.", "history": [], "expected": {"intent": "calculation", "quantities": 2}},
        {"id": "temporal-spacing", "text": "Neral  emite luz antes de Vetra.", "history": [], "expected": {"temporal": "antes"}},
    ]
