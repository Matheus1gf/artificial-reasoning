#!/usr/bin/env python3
"""Reproduce the bounded own intent network, with protocol written before fitting."""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.cognition.datasets import language_corpus, context_corpus
from src.cognition.neural import IntentNetwork, FEATURES, HIDDEN


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def accuracy(model, rows):
    predictions = [{"id": row["id"], "expected": row["intent"], **model.predict(row["text"])} for row in rows]
    return {"correct": sum(p["intent"] == p["expected"] for p in predictions), "count": len(rows),
            "accuracy": sum(p["intent"] == p["expected"] for p in predictions) / len(rows), "predictions": predictions}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists():
        parser.error("Escolha um diretório novo para preservar o protocolo e os resultados anteriores.")
    args.output_dir.mkdir(parents=True)
    corpus = language_corpus()
    write_new(args.output_dir / "language-corpus.v1.json", corpus)
    write_new(args.output_dir / "context-corpus.v1.json", context_corpus())
    protocol = {"id": "intent-own-mlp-reproduction-v2", "architecture": {"features": FEATURES, "hidden_tanh": HIDDEN, "output": "10-class softmax"},
                "seeds": [17, 29, 47], "epochs": 45, "learning_rate": 0.12,
                "splits": {key: {"size": len(rows), "template_ids": sorted({r["template_id"] for r in rows})} for key, rows in corpus.items()},
                "selected_checkpoint_seed": 17, "checkpoint_selection": "fixed before fitting, not best held-out result",
                "corpus_sha256": hashlib.sha256((args.output_dir / "language-corpus.v1.json").read_bytes()).hexdigest(),
                "priors": ["signed character n-gram hashing", "fixed intent vocabulary", "project-authored annotated templates"],
                "decision": "Measure held-out intent accuracy and report every seed; no general-language or human-reasoning claim.",
                "runtime_use": "Diagnostic proposals only: adopted=False for every confidence. Prior v1 held-out scores 58-68% motivated withholding semantic authority.",
                "historical_protocol": "experiments/cognition/intent-protocol.v1.json is preserved; its threshold proposal was not adopted after evaluation."}
    write_new(args.output_dir / "intent-protocol.v1.json", protocol)
    source_files = ["src/cognition/neural.py", "src/cognition/datasets.py", "src/cognition/processor.py", "scripts/train_cognition.py"]
    write_new(args.output_dir / "intent-registration.v2.json", {"protocol_id": protocol["id"], "created_unix": time.time(),
        "protocol_sha256": hashlib.sha256((args.output_dir / "intent-protocol.v1.json").read_bytes()).hexdigest(),
        "sources_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_files},
        "held_out_previously_observed": True, "meaning": "Reproduction of a known pilot, not a new untouched scientific evaluation."})
    report = {"protocol": protocol["id"], "python": platform.python_version(), "network_calls": 0, "qwen_calls": 0, "runs": []}
    for seed in protocol["seeds"]:
        model = IntentNetwork(seed)
        before = accuracy(model, corpus["held_out"])
        started = time.perf_counter()
        model.train(corpus["training"], epochs=protocol["epochs"], learning_rate=protocol["learning_rate"])
        seconds = time.perf_counter() - started
        result = {"seed": seed, "training_seconds": seconds, "loss_curve": model.loss_curve,
                  "before_held_out": before, **{key: accuracy(model, rows) for key, rows in corpus.items()}}
        report["runs"].append(result)
        if seed == protocol["selected_checkpoint_seed"]:
            write_new(args.output_dir / "intent-model.v1.json", model.artifact())
    write_new(args.output_dir / "intent-results.v1.json", report)
    print(json.dumps({"output": str(args.output_dir.resolve()), "runs": [{"seed": r["seed"], "train": r["training"]["accuracy"],
                      "validation": r["validation"]["accuracy"], "held_out": r["held_out"]["accuracy"], "seconds": r["training_seconds"]} for r in report["runs"]]}, indent=2))


if __name__ == "__main__":
    main()
