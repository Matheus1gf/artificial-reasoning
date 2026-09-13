"""Small own neural intent model: hashed character features -> tanh -> softmax.

Weights start from seeded random values. Training examples are project-authored
templates with declared labels, not Qwen outputs or user conversations. This
classifier proposes intent only; it cannot add premises or bypass verification.
"""
import hashlib
import json
import math
import random
import re
import unicodedata
from pathlib import Path


LABELS = ["statement", "question", "calculation", "creation", "correction", "hypothesis", "summary", "greeting", "analogy", "preference"]
FEATURES = 128
HIDDEN = 16
MODEL_VERSION = "intent-mlp-1"
DEFAULT_CHECKPOINT = Path(__file__).resolve().parents[2] / "experiments" / "cognition" / "intent-model.v1.json"


def features(text):
    if not isinstance(text, str) or len(text) > 8000:
        raise ValueError("Texto inválido para o classificador.")
    normalized = unicodedata.normalize("NFKD", text.casefold())
    normalized = "^" + re.sub(r"\s+", " ", "".join(c for c in normalized if not unicodedata.combining(c))) + "$"
    vector = {}
    for length in (2, 3, 4):
        for start in range(max(0, len(normalized) - length + 1)):
            gram = normalized[start:start + length].encode("utf-8")
            digest = hashlib.blake2b(gram, digest_size=4).digest()
            index = int.from_bytes(digest[:2], "big") % FEATURES
            vector[index] = vector.get(index, 0.0) + (1.0 if digest[2] & 1 else -1.0)
    norm = math.sqrt(sum(v * v for v in vector.values())) or 1.0
    return {k: v / norm for k, v in vector.items() if v}


class IntentNetwork:
    def __init__(self, seed=17, artifact=None):
        if type(seed) is not int or not 0 <= seed < 2 ** 32:
            raise ValueError("Semente neural inválida.")
        if artifact is not None:
            self._load(artifact)
            return
        rng = random.Random(seed)
        self.w1 = [[rng.uniform(-0.2, 0.2) for _ in range(FEATURES)] for _ in range(HIDDEN)]
        self.b1 = [0.0] * HIDDEN
        self.w2 = [[rng.uniform(-0.2, 0.2) for _ in range(HIDDEN)] for _ in LABELS]
        self.b2 = [0.0] * len(LABELS)
        self.seed, self.training_ids, self.loss_curve = seed, [], []

    def _load(self, artifact):
        required = {"version", "labels", "features", "hidden", "seed", "w1", "b1", "w2", "b2", "training_ids", "loss_curve"}
        if not isinstance(artifact, dict) or set(artifact) != required:
            raise ValueError("Checkpoint neural fora do esquema.")
        if artifact["version"] != MODEL_VERSION or artifact["labels"] != LABELS or artifact["features"] != FEATURES or artifact["hidden"] != HIDDEN:
            raise ValueError("Arquitetura neural incompatível.")
        if type(artifact["seed"]) is not int or not 0 <= artifact["seed"] < 2 ** 32:
            raise ValueError("Semente do checkpoint inválida.")
        for name, rows, cols in (("w1", HIDDEN, FEATURES), ("w2", len(LABELS), HIDDEN)):
            matrix = artifact[name]
            if not isinstance(matrix, list) or len(matrix) != rows or any(not isinstance(row, list) or len(row) != cols for row in matrix):
                raise ValueError("Dimensões incorretas nos pesos.")
            if any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 100 for row in matrix for v in row):
                raise ValueError("Peso neural inválido.")
        for name, length in (("b1", HIDDEN), ("b2", len(LABELS))):
            if not isinstance(artifact[name], list) or len(artifact[name]) != length or any(type(v) not in (float, int) or not math.isfinite(v) or abs(v) > 100 for v in artifact[name]):
                raise ValueError("Viés neural inválido.")
        if not isinstance(artifact["training_ids"], list) or any(not isinstance(i, str) for i in artifact["training_ids"]):
            raise ValueError("IDs de treinamento inválidos.")
        if not isinstance(artifact["loss_curve"], list) or any(type(v) not in (float, int) or not math.isfinite(v) or v < 0 for v in artifact["loss_curve"]):
            raise ValueError("Curva de perda inválida.")
        copied = json.loads(json.dumps(artifact, allow_nan=False))
        for name in ("w1", "b1", "w2", "b2", "seed", "training_ids", "loss_curve"):
            setattr(self, name, copied[name])

    def _forward(self, vector):
        hidden = [math.tanh(bias + sum(weights[i] * value for i, value in vector.items())) for weights, bias in zip(self.w1, self.b1)]
        logits = [bias + sum(w * h for w, h in zip(weights, hidden)) for weights, bias in zip(self.w2, self.b2)]
        maximum = max(logits)
        exp = [math.exp(x - maximum) for x in logits]
        total = sum(exp)
        return hidden, [x / total for x in exp]

    def predict(self, text):
        _, probabilities = self._forward(features(text))
        order = sorted(range(len(LABELS)), key=lambda i: (-probabilities[i], i))
        return {"intent": LABELS[order[0]], "probability": probabilities[order[0]],
                "margin": probabilities[order[0]] - probabilities[order[1]],
                "probabilities": dict(zip(LABELS, probabilities)), "version": MODEL_VERSION}

    def train(self, examples, epochs=45, learning_rate=0.12):
        if not isinstance(examples, list) or not 10 <= len(examples) <= 5000:
            raise ValueError("Treino exige entre 10 e 5.000 exemplos anotados.")
        if type(epochs) is not int or not 1 <= epochs <= 200 or type(learning_rate) not in (int, float) or not 0 < learning_rate <= 1:
            raise ValueError("Orçamento de treinamento inválido.")
        prepared, ids = [], []
        for example in examples:
            if not isinstance(example, dict) or example.get("intent") not in LABELS or not isinstance(example.get("id"), str):
                raise ValueError("Exemplo precisa de id, text e intent válidos.")
            prepared.append((features(example["text"]), LABELS.index(example["intent"])))
            ids.append(example["id"])
        if len(set(ids)) != len(ids):
            raise ValueError("IDs de treinamento repetidos.")
        rng = random.Random(self.seed + 1)
        for epoch in range(epochs):
            order = list(range(len(prepared))); rng.shuffle(order)
            loss = 0.0
            rate = learning_rate / (1 + epoch / 40)
            for index in order:
                vector, target = prepared[index]
                hidden, probabilities = self._forward(vector)
                loss -= math.log(max(probabilities[target], 1e-12))
                gradient = [p - int(i == target) for i, p in enumerate(probabilities)]
                hidden_gradient = [(1 - h * h) * sum(gradient[k] * self.w2[k][j] for k in range(len(LABELS)))
                                   for j, h in enumerate(hidden)]
                for k in range(len(LABELS)):
                    self.b2[k] -= rate * gradient[k]
                    for j, h in enumerate(hidden):
                        self.w2[k][j] -= rate * gradient[k] * h
                for j in range(HIDDEN):
                    self.b1[j] -= rate * hidden_gradient[j]
                    for feature, value in vector.items():
                        self.w1[j][feature] -= rate * hidden_gradient[j] * value
            self.loss_curve.append(loss / len(prepared))
        self.training_ids = list(dict.fromkeys(self.training_ids + ids))
        return self.artifact()

    def artifact(self):
        return json.loads(json.dumps({"version": MODEL_VERSION, "labels": LABELS, "features": FEATURES, "hidden": HIDDEN,
                                     "seed": self.seed, "w1": self.w1, "b1": self.b1, "w2": self.w2, "b2": self.b2,
                                     "training_ids": self.training_ids, "loss_curve": self.loss_curve}, allow_nan=False))


_default = None


def local_intent(text):
    global _default
    if _default is None:
        if not DEFAULT_CHECKPOINT.is_file():
            return None
        _default = IntentNetwork(artifact=json.loads(DEFAULT_CHECKPOINT.read_text(encoding="utf-8")))
    return _default.predict(text)
