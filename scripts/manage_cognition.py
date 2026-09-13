#!/usr/bin/env python3
"""Explicit local administration of the cognition sidecar, never the chat DB."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.cognition.store import ExperienceStore


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    actions = parser.add_subparsers(dest="action", required=True)
    backup = actions.add_parser("backup")
    backup.add_argument("output", type=Path)
    export = actions.add_parser("export")
    export.add_argument("output", type=Path)
    export.add_argument("--owner", default="local")
    erase = actions.add_parser("forget")
    erase.add_argument("record_id")
    erase.add_argument("--owner", default="local")
    restore = actions.add_parser("restore")
    restore.add_argument("output", type=Path)
    args = parser.parse_args(argv)
    if not args.database.is_file():
        parser.error("database must already exist")
    if args.action == "restore":
        restored = ExperienceStore.restore(args.database, args.output)
        restored.close()
        print(json.dumps({"restored": str(args.output)}))
        return
    store = ExperienceStore(args.database)
    try:
        if args.action == "backup":
            result = store.backup(args.output)
        elif args.action == "export":
            result = store.export(args.owner)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            result = {"exported": str(args.output), "records": len(result["records"])}
        else:
            result = store.forget(args.record_id, args.owner)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        store.close()


if __name__ == "__main__":
    main()
