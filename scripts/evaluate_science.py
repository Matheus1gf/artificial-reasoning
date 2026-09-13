#!/usr/bin/env python3
"""Run the registered bounded science pilots; preserve existing result files."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.science.evaluation import evaluate, code_hashes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--register", action="store_true", help="write current source hashes only, before experiment scoring")
    args = parser.parse_args(argv)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    # Reserve first so an existing report causes no expensive experiment run.
    with args.output.open("x") as handle:
        if args.register:
            from datetime import datetime, timezone
            result = {"registered_at": datetime.now(timezone.utc).isoformat(), "code_hashes": code_hashes(), "scored": False}
        else:
            result = evaluate()
        json.dump(result, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"output": str(args.output), "registered_only": args.register}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
