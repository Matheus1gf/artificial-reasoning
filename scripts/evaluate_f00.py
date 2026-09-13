#!/usr/bin/env python3
"""Run F00 offline references without importing or starting chatbot providers."""
import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.research.evaluation import DEFAULT_PROTOCOL, run_evaluation  # noqa: E402


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--split", choices=("development", "validation"), default="validation")
    parser.add_argument("--output", type=Path, help="Write JSON to a NEW file (never overwrite evidence).")
    args = parser.parse_args(argv)
    if args.output is not None and args.output.exists():
        parser.error("output already exists; choose a new path to preserve prior results")
    try:
        report = run_evaluation(args.protocol, args.split)
        serialized = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output is not None:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(serialized)
            print(json.dumps({"report": str(args.output.resolve()), "summary": report["summary"],
                              "reserved_evaluated": False, "qwen_calls": 0}, ensure_ascii=False, indent=2))
        else:
            print(serialized, end="")
    except (OSError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
