"""Run generated finite arithmetic programs in a resource-bounded subprocess."""
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def execute_program(program, inputs=None, *, timeout=1.0, max_steps=10000, memory_mb=128, cancel_event=None):
    if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 10:
        raise ValueError("timeout must be finite in (0,10]")
    if type(max_steps) is not int or not 1 <= max_steps <= 100000:
        raise ValueError("max_steps must be in [1,100000]")
    if type(memory_mb) is not int or not 64 <= memory_mb <= 512:
        raise ValueError("memory_mb must be in [64,512]")
    if not isinstance(program, list) or (inputs is not None and not isinstance(inputs, dict)):
        raise ValueError("Use the numeric instruction DSL and a mapping of inputs")
    payload = json.dumps({"program": program, "inputs": {} if inputs is None else inputs,
                          "max_steps": max_steps, "cpu_seconds": max(1, math.ceil(timeout)),
                          "memory_mb": memory_mb}, allow_nan=False).encode()
    if len(payload) > 131072:
        raise ValueError("Program and inputs exceed 128 KiB")
    started = time.monotonic()
    worker = Path(__file__).with_name("sandbox_worker.py")
    if cancel_event is not None and cancel_event.is_set():
        return {"status": "cancelled", "steps": 0, "stack": [], "values": {}, "seconds": 0.0}
    with tempfile.TemporaryDirectory(prefix="ar-numeric-worker-") as directory:
        process = subprocess.Popen([sys.executable, "-I", "-S", str(worker)], cwd=directory,
                                   env={"PATH": os.defpath, "LANG": "C.UTF-8"},
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sent = False
        try:
            while True:
                elapsed = time.monotonic() - started
                status = ("cancelled" if cancel_event is not None and cancel_event.is_set()
                          else "timeout" if elapsed >= timeout else None)
                if status:
                    process.kill()
                    process.communicate()
                    return {"status": status, "steps": None, "stack": [], "values": {}, "seconds": elapsed}
                try:
                    output, _ = process.communicate(input=payload if not sent else None, timeout=min(0.05, timeout - elapsed))
                    break
                except subprocess.TimeoutExpired:
                    sent = True
            if process.returncode != 0 or len(output) > 131072:
                result = {"status": "worker_failed", "steps": None, "stack": [], "values": {}}
            else:
                result = json.loads(output)
            result["seconds"] = time.monotonic() - started
            result["isolation"] = {"language": "finite_numeric_dsl", "separate_process": True,
                                   "arbitrary_python": False, "memory_rlimit": sys.platform.startswith("linux"),
                                   "input_bytes_limit": 131072, "stack_limit": 1024}
            return result
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
