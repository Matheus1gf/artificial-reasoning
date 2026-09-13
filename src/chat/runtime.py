"""Start only the project-local model runtime; never replace a user's service."""
import json
import os
import subprocess
import time
from pathlib import Path
from urllib import request

ROOT = Path(__file__).resolve().parents[2]
LOCAL_MODEL = "qwen3.5:9b"


def runtime_available():
    try:
        with request.urlopen("http://127.0.0.1:11434/api/version", timeout=1) as response:
            return bool(json.load(response).get("version"))
    except (OSError, ValueError):
        return False


def start_local_runtime(settings):
    """Return an owned child process, or None for an existing/external provider."""
    if getattr(settings, "research_mode", True):
        return None
    executable = ROOT / ".runtime/ollama/ollama"
    if (settings.provider != "ollama" or settings.base_url.rstrip("/") not in
            {"http://127.0.0.1:11434", "http://localhost:11434"} or not executable.is_file()):
        return None
    if runtime_available():
        return None
    folder = ROOT / "data/chat-runtime"
    folder.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, OLLAMA_HOST="127.0.0.1:11434", OLLAMA_MODELS=str(folder / "models"),
               OLLAMA_NO_CLOUD="1", OLLAMA_NUM_PARALLEL="1", OLLAMA_MAX_LOADED_MODELS="1",
               OLLAMA_DEBUG_LOG_REQUESTS="false")
    with (folder / "ollama.log").open("ab") as log:
        process = subprocess.Popen([str(executable), "serve"], env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT)
    for _ in range(100):
        if runtime_available():
            return process
        if process.poll() is not None:
            raise RuntimeError("O modelo local não iniciou. Consulte data/chat-runtime/ollama.log.")
        time.sleep(0.1)
    stop_local_runtime(process)
    raise RuntimeError("O modelo local demorou para iniciar. Consulte data/chat-runtime/ollama.log.")


def stop_local_runtime(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
