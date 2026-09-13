"""Small, explicit knowledge representation shared by memory and reasoning."""
import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import List


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.casefold())
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text).strip(" .!?;:\"'")


def concept(text: str) -> str:
    return re.sub(r"^(?:um|uma|o|a|os|as)\s+", "", normalize(text)).strip()


STOPWORDS = set("a o as os um uma de da do das dos em no na e que qual quais como por para com se ele ela isso esse essa sobre me voce eu meu minha pode seria existe explique sabe saber aprenda seria podemos sabemos".split())


def tokens(text: str) -> set:
    return {w for w in re.findall(r"[a-z0-9_-]+", normalize(text)) if len(w) > 1 and w not in STOPWORDS}


VERBS = {
    "absorver": "absorve", "absorvem": "absorve", "absorve": "absorve",
    "expelir": "expulsa", "expelindo": "expulsa", "expele": "expulsa", "expila": "expulsa", "expulsar": "expulsa", "expulsa": "expulsa",
    "aquecer": "aquece", "aquece": "aquece", "esfriar": "resfria", "resfriar": "resfria", "resfria": "resfria",
    "produzir": "produz", "produz": "produz", "produzem": "produz", "consumir": "consome", "consome": "consome",
    "armazenar": "armazena", "armazena": "armazena", "liberar": "libera", "libera": "libera",
    "aumentar": "aumenta", "aumenta": "aumenta", "diminuir": "diminui", "diminui": "diminui",
    "conduzir": "conduz", "conduz": "conduz", "conduzem": "conduz",
    "emitir": "emite", "emite": "emite", "receber": "recebe", "recebe": "recebe",
    "ter": "tem", "tem": "tem", "possui": "tem", "possuem": "tem",
    "causar": "causa", "causa": "causa", "requer": "requer", "precisa": "requer",
    "permite": "permite", "impede": "impede", "transformar": "transforma", "transforma": "transforma", "filtrar": "filtra", "filtra": "filtra",
    "usa": "usa", "utiliza": "usa", "protege": "protege", "remove": "remove",
    "converter": "converte", "converte": "converte", "convertem": "converte",
    "transportar": "transporta", "transporta": "transporta", "transportam": "transporta",
    "usar": "usa", "utilizar": "usa", "proteger": "protege", "remover": "remove",
    "gosta": "gosta", "prefere": "prefere",
    "e": "é", "sao": "é", "ser": "é",
}


def predicate(text: str) -> str:
    return VERBS.get(normalize(text), normalize(text))


@dataclass
class Assertion:
    subject: str
    predicate: str
    object: str
    quote: str
    polarity: bool = True
    scope: str = "instance"
    tentative: bool = False

    def clean(self):
        self.subject = concept(self.subject)
        self.predicate = predicate(self.predicate)
        self.object = concept(self.object)
        return self


@dataclass
class Proposal:
    subject: str
    predicate: str
    object: str
    method: str
    premises: List[int]
    explanation: str
    validation: str
    status: str = "hypothesis"
    polarity: bool = True
    scope: str = "instance"


def claim_text(claim: dict) -> str:
    subject = ("Todo " if claim.get("scope") == "universal" else "") + claim["subject"]
    if claim["predicate"] == "oposto_de":
        return f"{subject} {'' if claim.get('polarity', True) else 'não '}é o oposto de {claim['object']}"
    return f"{subject} {'' if claim.get('polarity', True) else 'não '}{claim['predicate']} {claim['object']}"


STATUS_LABELS = {
    "asserted": "Informado por você", "deduced": "Dedução condicional",
    "hypothesis": "Hipótese", "disputed": "Em conflito", "retracted": "Retirado",
}
