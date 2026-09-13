"""Validated, provenance-preserving ingestion for bounded rediscovery studies."""

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from .numerics import finite, least_squares, rmse
from .symbolic import discover, predict

CORPUS = Path(__file__).resolve().parents[2]/"experiments"/"science"/"corpus"


def ingest(records, metadata):
    """Normalize anonymous two-column measurements; metadata stays outside learner view."""
    required = {"source_url", "retrieved_at", "license", "units", "measurement_conditions",
                "uncertainty", "data_kind", "sha256"}
    if not isinstance(metadata, dict) or not required <= set(metadata):
        raise ValueError("missing corpus provenance")
    if metadata["data_kind"] != "observed":
        raise ValueError("real-data ingestion requires observed data designation")
    source = urlsplit(metadata["source_url"])
    if source.scheme != "https" or not source.netloc or source.username or source.password:
        raise ValueError("source URL must be an attributed HTTPS location without credentials")
    datetime.fromisoformat(metadata["retrieved_at"].replace("Z", "+00:00"))
    if not isinstance(metadata["sha256"], str) or not re.fullmatch("[a-f0-9]{64}", metadata["sha256"]):
        raise ValueError("source sha256 must contain 64 lowercase hex digits")
    if not isinstance(metadata["license"], dict) or not metadata["license"].get("policy_url") or not metadata["license"].get("designation"):
        raise ValueError("license policy and designation required")
    if not isinstance(metadata["units"], dict) or any(not isinstance(metadata["units"].get(k), str) or not metadata["units"][k] for k in ("x", "y")):
        raise ValueError("explicit units or unspecified designation required for both columns")
    if any(not isinstance(metadata[k], dict) or not metadata[k] for k in ("measurement_conditions", "uncertainty")):
        raise ValueError("conditions and uncertainty must be explicit nonempty records")
    if not isinstance(records, list) or not 4 <= len(records) <= 10000:
        raise ValueError("4 to 10000 observed rows required")
    rows = [{"variables": {"q": finite(row["x"], "x")}, "target": finite(row["y"], "y")}
            for row in records]
    return {"rows": rows, "provenance": dict(metadata),
            "units_declared": all(metadata["units"].get(k) not in (None, "unspecified") for k in ("x", "y")),
            # Receiving metadata cannot itself certify its physical interpretation.
            "physical_interpretation_approved": False,
            "allowed_use": "numerical relation study; no physical-unit claim when source units are unspecified"}


def prior_art_search(query, records=None):
    """Search the declared primary-source catalog; absence never proves novelty."""
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ValueError("nonempty bounded search query required")
    if records is None:
        records = json.loads((CORPUS/"prior-art.v1.json").read_text())["records"]
    if not isinstance(records, list) or len(records) > 1000:
        raise ValueError("catalog exceeds bounds")

    def tokens(text):
        plain = "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")
        return set(re.findall(r"[a-z0-9]+", plain))

    wanted = tokens(query)
    matches = []
    for record in records:
        haystack = tokens(record["title"]+" "+record["description"]+" "+" ".join(record["keywords"]))
        overlap = wanted & haystack
        if overlap:
            matches.append({"id": record["id"], "title": record["title"], "url": record["url"],
                            "matched_terms": sorted(overlap), "score": len(overlap)/len(wanted),
                            "known_relation": record.get("known_relation")})
    matches.sort(key=lambda r: (-r["score"], r["id"]))
    return {"query": query, "searched_records": len(records), "matches": matches,
            "scope": "versioned primary-source catalog only; initial web queries recorded in dossier",
            "novelty": "known_related_work" if matches else "not_found_in_catalog",
            "scientific_novelty_established": False}


def load_corpus():
    metadata_path, observations_path = CORPUS/"nist-norris.metadata.v1.json", CORPUS/"nist-norris.observations.v1.json"
    metadata = json.loads(metadata_path.read_text())
    raw = (CORPUS/"Norris.dat").read_bytes()
    if hashlib.sha256(raw).hexdigest() != metadata["sha256"]:
        raise ValueError("source corpus checksum mismatch")
    observations_bytes = observations_path.read_bytes()
    if hashlib.sha256(observations_bytes).hexdigest() != metadata["observations_sha256"]:
        raise ValueError("normalized observation checksum mismatch")
    return ingest(json.loads(observations_bytes), metadata)


def calibration_study(rows, train_indices, evaluation_indices):
    if not train_indices or not evaluation_indices or set(train_indices) & set(evaluation_indices):
        raise ValueError("nonempty disjoint train/evaluation indices required")
    if any(type(i) is not int or not 0 <= i < len(rows) for i in train_indices+evaluation_indices):
        raise ValueError("invalid data row index")
    if len(set(train_indices)) != len(train_indices) or len(set(evaluation_indices)) != len(evaluation_indices):
        raise ValueError("indices must be unique")
    train, evaluation = [rows[i] for i in train_indices], [rows[i] for i in evaluation_indices]
    # All constants/degrees are experimental priors. No certified parameters are passed.
    model = discover(train, max_degree=2, max_terms=2, max_candidates=10, tolerance=.05)
    truth = [row["target"] for row in evaluation]
    predictions = [predict(model, row["variables"]) for row in evaluation]
    mean = sum(row["target"] for row in train)/len(train)
    linear = least_squares([[1, row["variables"]["q"]] for row in train], [row["target"] for row in train])
    simple_predictions = [linear["coefficients"][0]+linear["coefficients"][1]*row["variables"]["q"] for row in evaluation]
    return {"model": model, "train_rows": len(train), "evaluation_rows": len(evaluation),
            "rmse": rmse(truth, predictions), "mean_baseline_rmse": rmse(truth, [mean]*len(truth)),
            "ordinary_least_squares_rmse": rmse(truth, simple_predictions),
            "predictions": predictions, "expected": truth,
            "novelty": "controlled rediscovery of an existing published calibration relation",
            "physical_units": "unspecified in primary file; native values only"}


def resolve(request):
    parameters = request.get("parameters", {})
    if not isinstance(parameters, dict):
        raise ValueError("parameters must be an object")
    if request.get("operation") == "prior_art":
        result = prior_art_search(**parameters)
        sentence = "A busca no catálogo de {} fontes primárias encontrou {} referências relacionadas; isso não prova novidade científica.".format(result["searched_records"], len(result["matches"]))
        return {"status": "answered", "values": result, "sentences": [sentence], "conclusions": [sentence],
                "verification": {"passed": True, "checks": ["bounded lexical catalog search"]},
                "premises": [r["url"] for r in result["matches"]], "units": {},
                "limitations": [result["scope"]]}
    if request.get("operation") != "calibration":
        raise ValueError("only calibration operation is available")
    if parameters:
        raise ValueError("published calibration study does not accept runtime parameter overrides")
    # Core accesses approved observed data; never scientific reserved splits.
    corpus = load_corpus()
    indices = [i for i in range(len(corpus["rows"])) if i % 3 != 0]
    result = calibration_study(corpus["rows"], indices, [i for i in range(len(corpus["rows"])) if i % 3 == 0])
    sentence = "Na redescoberta controlada da calibração publicada pelo NIST, o erro de previsão foi {:.8g} nas unidades nativas não especificadas da fonte.".format(result["rmse"])
    return {"status": "answered", "values": result, "sentences": [sentence], "conclusions": [sentence],
            "verification": {"passed": True, "checks": ["source and observations SHA256", "disjoint fitting and evaluation rows"]},
            "units": {"x": "unspecified", "y": "unspecified"},
            "premises": [corpus["provenance"]["source_url"]],
            "limitations": ["Relação já publicada; não é descoberta inédita.",
                            "Sem incerteza instrumental e unidade documentadas, não aprova uso metrológico."]}
