"""Published aggregate human data, separate from the synthetic context pilot."""

import hashlib
import json
import math
import random
from pathlib import Path

from .numerics import integer, bounded
from . import quantum

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT/"experiments"/"science"/"corpus"/"human-context.observations.v1.json"
PROTOCOL = ROOT/"experiments"/"science"/"human-context.protocol.v1.json"


def reconstruct_counts(probabilities, sample_size, decimals=4):
    integer(sample_size, 1, 10000, "sample_size")
    integer(decimals, 1, 6, "decimals")
    if not isinstance(probabilities, list) or len(probabilities) != 4:
        raise ValueError("four joint probabilities required")
    probabilities = [bounded(p, 0, 1, "probability") for p in probabilities]
    half_interval, counts = .5*10**(-decimals), []
    for probability in probabilities:
        compatible = [n for n in range(sample_size+1) if abs(n/sample_size-probability) < half_interval+1e-12]
        if len(compatible) != 1:
            raise ValueError("published rounding does not identify a unique count")
        counts.append(compatible[0])
    if sum(counts) != sample_size:
        raise ValueError("reconstructed counts do not sum to sample size")
    return counts


def load_experiments():
    document = json.loads(DATA.read_text())
    if document.get("data_kind") != "observed_human_aggregate":
        raise ValueError("human and synthetic data must remain distinct")
    experiments = []
    for experiment in document["experiments"]:
        orders = [{"order": row["order"], "counts": reconstruct_counts(row["probabilities"], row["sample_size"], document["precision_decimals"])}
                  for row in experiment["orders"]]
        experiments.append({"id": experiment["id"], "orders": orders})
    return document, experiments


def partition(orders, seed):
    integer(seed, 0, 2**32-1, "seed")
    generator, training, evaluation = random.Random(seed), [], []
    for row in orders:
        tokens = [category for category, count in enumerate(row["counts"]) for _ in range(count)]
        generator.shuffle(tokens)
        cut = len(tokens)//2
        for destination, selected in ((training, tokens[:cut]), (evaluation, tokens[cut:])):
            destination.append({"order": row["order"], "counts": [selected.count(k) for k in range(4)]})
    return training, evaluation


def score(fit, observations):
    function = quantum.sequential_probability if fit["model"] == "quantum" else quantum.classical_context_probability
    total, loss, residual = 0, 0.0, 0.0
    for row in observations:
        n = sum(row["counts"])
        total += n
        for k, count in enumerate(row["counts"]):
            probability = function(fit["theta"], fit["phi"], row["order"], k//2, k % 2)
            loss -= count*math.log(max(probability, 1e-15))
            residual = max(residual, abs(count/n-probability))
    return {"nll": loss, "nll_per_response": loss/total, "response_count": total,
            "maximum_absolute_probability_residual": residual}


def evaluate():
    protocol = json.loads(PROTOCOL.read_text())
    document, experiments = load_experiments()
    results = []
    for experiment in experiments:
        full, partitions = {}, []
        for model in protocol["models"]:
            fit = quantum.contextual_fit(experiment["orders"], model, protocol["grid_size"])
            fit["data_kind"] = "observed_human_aggregate"
            full[model] = {"fit": fit, "score": score(fit, experiment["orders"])}
        for seed in protocol["seeds"]:
            training, evaluation = partition(experiment["orders"], seed)
            outcomes = {}
            for model in protocol["models"]:
                fit = quantum.contextual_fit(training, model, protocol["grid_size"])
                fit["data_kind"] = "observed_human_aggregate"
                outcomes[model] = {"fit": fit, "evaluation": score(fit, evaluation)}
            partitions.append({"seed": seed, "training": training, "evaluation": evaluation, "outcomes": outcomes})
        results.append({"id": experiment["id"], "full_data": full, "partitions": partitions,
                        "restricted_model_rejected": full["quantum"]["score"]["maximum_absolute_probability_residual"] > .10})
    return {"protocol_id": protocol["protocol_id"], "source_doi": document["source_doi"],
            "source_url": document["source_url"], "data_kind": document["data_kind"],
            "transcription_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
            "experiments": results, "unique_response_count": sum(sum(r["counts"]) for e in experiments for r in e["orders"]),
            "new_human_data_collected": False,
            "limits": ["Repeated aggregate partitions are not new independent participants or replications.",
                       "Our 2D real-state model is narrower than general quantum cognition.",
                       "The equivalent classical model prevents a quantum-superiority claim from fit alone.",
                       "No inference about any individual or demographic population is authorized by this numerical reanalysis."]}
