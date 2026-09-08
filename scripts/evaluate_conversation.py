#!/usr/bin/env python3
"""Capture real model replies for manual regression review, using isolated memory."""
import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.chat.provider import Settings
from src.chat.runtime import LOCAL_MODEL


def main():
    parser = argparse.ArgumentParser(description="Avaliar respostas reais, sem alterar as conversas do usuário.")
    parser.add_argument("--model", default=LOCAL_MODEL)
    parser.add_argument("--base-url", default="http://127.0.0.1:11434")
    parser.add_argument("--output", type=Path, default=ROOT / ".runtime/conversation-evaluation.json")
    args = parser.parse_args()
    settings = Settings(provider="ollama", model=args.model, base_url=args.base_url, timeout=120)
    prompts = [
        "O que é um buraco de minhoca? Explique em duas frases.",
        "Explique isso usando uma analogia curta.",
        "Mudando de assunto: o que é fotossíntese? Responda em duas frases.",
        "Resuma sua última resposta em exatamente cinco palavras.",
        "Escreva uma função Python chamada dobro que retorna o dobro de um número.",
        "Qual é a diferença entre uma lista e uma tupla em Python? Responda em duas frases.",
    ]
    report = {"model": args.model, "mode": "real inference; qualitative review, not an accuracy benchmark", "turns": []}
    with tempfile.TemporaryDirectory(prefix="ra-conversation-eval-") as folder:
        memory = Memory(Path(folder) / "memory.sqlite3")
        try:
            cid = memory.create_conversation()["id"]
            seed = ChatEngine(memory)
            seed.reply(cid, "Um buraco negro absorve matéria.")
            seed.reply(cid, "Qual seria o oposto de um buraco negro?")
            engine = ChatEngine(memory, settings)
            for prompt in prompts:
                started, first_token = time.monotonic(), []
                def on_token(chunk):
                    if not first_token:
                        first_token.append(time.monotonic() - started)
                result = engine.reply(cid, prompt, on_token=on_token)
                report["turns"].append({"prompt": prompt, "answer": result["content"],
                                        "seconds": round(time.monotonic() - started, 2),
                                        "first_token_seconds": round(first_token[0], 2) if first_token else None,
                                        "retrieved": [c["text"] for c in result["retrieved"]],
                                        "warnings": result["warnings"]})
                print(json.dumps(report["turns"][-1], ensure_ascii=False), flush=True)
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        finally:
            memory.close()


if __name__ == "__main__":
    main()
