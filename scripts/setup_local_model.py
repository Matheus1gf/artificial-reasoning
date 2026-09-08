#!/usr/bin/env python3
"""Install a pinned local Ollama runtime and download a general conversation model."""
import argparse
import hashlib
import json
import platform
import sys
import tarfile
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.chat.provider import Settings
from src.chat.runtime import LOCAL_MODEL, start_local_runtime, stop_local_runtime

VERSION = "v0.33.3"
ARCHIVE_SHA256 = "342db03df80bb9db84ff64246031bd5f70c09b59ff52fa5cc9aaae3476cc4a9d"


def main():
    parser = argparse.ArgumentParser(description="Preparar conversa neural local (download de cerca de 6,6 GB no modelo padrão).")
    parser.add_argument("--model", default=LOCAL_MODEL)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/chat")
    args = parser.parse_args()
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        parser.error("Este instalador é para macOS Apple Silicon. Em outros sistemas, instale Ollama pelo site oficial, baixe um modelo e configure-o na interface.")
    destination = ROOT / ".runtime/ollama"
    if not (destination / "ollama").exists():
        archive = ROOT / ".runtime/downloads/ollama-darwin.tgz"
        archive.parent.mkdir(parents=True, exist_ok=True)
        print("Baixando Ollama de sua distribuição oficial...", flush=True)
        request.urlretrieve(f"https://github.com/ollama/ollama/releases/download/{VERSION}/ollama-darwin.tgz", archive)
        digest = hashlib.sha256()
        with archive.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != ARCHIVE_SHA256:
            raise RuntimeError("A verificação SHA-256 do Ollama falhou. Instalação interrompida.")
        destination.mkdir(parents=True, exist_ok=True)
        base = str(destination.resolve()) + "/"
        with tarfile.open(archive) as package:
            for member in package.getmembers():
                target = destination / member.name
                if not str(target.resolve()).startswith(base):
                    raise RuntimeError("Caminho inválido no pacote.")
                if member.issym() and not str((target.parent / member.linkname).resolve()).startswith(base):
                    raise RuntimeError("Link inválido no pacote.")
                if member.islnk() and not str((destination / member.linkname).resolve()).startswith(base):
                    raise RuntimeError("Link inválido no pacote.")
            package.extractall(destination)
    settings = Settings(provider="ollama", model=args.model, timeout=120)
    process = start_local_runtime(settings)
    try:
        print(f"Baixando/verificando {args.model}...", flush=True)
        req = request.Request(settings.base_url + "/api/pull", data=json.dumps({"model": args.model, "stream": True}).encode(),
                              headers={"Content-Type": "application/json"})
        last = None
        with request.urlopen(req, timeout=600) as response:
            for line in response:
                event = json.loads(line)
                if event.get("error"):
                    raise RuntimeError(event["error"])
                percentage = int(event.get("completed", 0) * 100 / max(1, event.get("total", 1))) // 10 * 10
                progress = (event.get("status"), percentage)
                if progress != last:
                    print(progress[0], f"{percentage}%" if event.get("total") else "", flush=True)
                    last = progress
        # Only switch modes once the download has succeeded.
        settings.save(args.data_dir / "settings.json")
        print("Pronto. Execute python3 main.py; o modelo local será iniciado junto com o chat.")
    finally:
        stop_local_runtime(process)


if __name__ == "__main__":
    main()
