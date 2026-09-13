"""Local single-user HTTP application, implemented with the Python standard library."""
import argparse
import json
import logging
import secrets
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from .engine import ChatEngine
from .memory import Memory
from .provider import LanguageModel, ProviderError, Settings
from .runtime import start_local_runtime, stop_local_runtime
from src.cognition.contracts import AnswerPackage, ProblemSpec, render_with_arranger


ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "web"


def make_server(engine, port=8765, settings_path=None):
    token = secrets.token_urlsafe(32)
    settings_path = settings_path or ROOT / "data/chat/settings.json"
    requests_lock = threading.Lock()
    active_requests = {}

    def run_turn(data, **callbacks):
        request_id = data.get("request_id") or uuid.uuid4().hex
        if not isinstance(request_id, str) or not 1 <= len(request_id) <= 100:
            raise ValueError("Identificador de envio inválido.")
        with requests_lock:
            if sum(entry["waiters"] for entry in active_requests.values()) >= 8:
                raise ValueError("A fila local está cheia. Aguarde a conclusão de um envio.")
            entry = active_requests.get(request_id)
            identity = (data.get("conversation_id"), data.get("message"))
            if entry is None:
                entry = {"identity": identity, "event": threading.Event(), "waiters": 0}
                active_requests[request_id] = entry
            elif entry["identity"] != identity:
                raise ValueError("Identificador de envio já utilizado para outra mensagem.")
            # Concurrent retries share cancellation but still reach the engine's
            # serialization/cache, returning the same durable response to all.
            entry["waiters"] += 1
            cancellation = entry["event"]
        try:
            return engine.reply(data.get("conversation_id"), data.get("message"), request_id,
                                cancel_event=cancellation, **callbacks)
        finally:
            with requests_lock:
                entry["waiters"] -= 1
                if not entry["waiters"]:
                    active_requests.pop(request_id, None)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # Conversation contents and credentials never go to access logs.

        def send(self, status, data, content_type="application/json; charset=utf-8"):
            encoded = json.dumps(data, ensure_ascii=False).encode() if not isinstance(data, bytes) else data
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
            self.end_headers()
            self.wfile.write(encoded)

        def allowed(self, mutation=False):
            port = self.server.server_address[1]
            hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
            if self.headers.get("Host") not in hosts:
                self.send(403, {"error": "Host não permitido. Use localhost."})
                return False
            if mutation:
                origin = self.headers.get("Origin")
                if origin and origin not in {"http://" + h for h in hosts}:
                    self.send(403, {"error": "Origem não permitida."})
                    return False
                if not secrets.compare_digest(self.headers.get("X-Workspace-Token", ""), token):
                    self.send(403, {"error": "Recarregue a página para renovar a sessão local."})
                    return False
            return True

        def do_GET(self):
            if not self.allowed():
                return
            path = urlsplit(self.path).path
            assets = {"/": ("index.html", "text/html"), "/app.js": ("app.js", "text/javascript"), "/style.css": ("style.css", "text/css")}
            if path in assets:
                filename, mime = assets[path]
                self.send(200, (STATIC / filename).read_bytes(), mime + "; charset=utf-8")
                return
            try:
                with engine.memory.lock:
                    if path == "/api/state":
                        self.send(200, {"conversations": engine.memory.conversations(), "stats": engine.memory.stats(),
                                        "knowledge": engine.memory.claims(), "settings": engine.settings.public(), "token": token})
                    elif path.startswith("/api/conversations/"):
                        cid = path.rsplit("/", 1)[-1]
                        self.send(200, {"conversation": engine.memory.conversation(cid), "messages": engine.memory.messages(cid)})
                    elif path == "/api/health":
                        self.send(200, {"status": "ok", "provider": engine.settings.provider,
                                        "research_mode": engine.settings.research_mode})
                    elif path == "/api/experiences":
                        query = parse_qs(urlsplit(self.path).query)
                        cid = query.get("conversation_id", [""])[0]
                        engine.memory.conversation(cid)
                        self.send(200, {"experiences": engine.experience_store.retrieve(cid, {}, limit=100)})
                    else:
                        self.send(404, {"error": "Recurso não encontrado."})
            except ValueError as exc:
                self.send(404, {"error": str(exc)})

        def do_POST(self):
            if not self.allowed(mutation=True):
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 65536:
                    self.send(413, {"error": "Tamanho de requisição inválido."})
                    return
                if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
                    self.send(415, {"error": "Envie JSON."})
                    return
                data = json.loads(self.rfile.read(size))
                if not isinstance(data, dict):
                    raise ValueError("Objeto JSON esperado.")
                path = urlsplit(self.path).path
                if path == "/api/conversations":
                    result = engine.memory.create_conversation()
                elif path == "/api/chat":
                    result = run_turn(data)
                elif path == "/api/chat/cancel":
                    request_id = data.get("request_id")
                    if not isinstance(request_id, str):
                        raise ValueError("Informe o identificador do envio a cancelar.")
                    with requests_lock:
                        entry = active_requests.get(request_id)
                        cancellation = entry["event"] if entry else None
                        if cancellation:
                            cancellation.set()
                    result = {"requested": cancellation is not None,
                              "message": "Cancelamento solicitado. O núcleo encerrará no próximo ponto de controle." if cancellation else "O envio já terminou ou não está na fila."}
                elif path == "/api/chat/stream":
                    self.stream_chat(data)
                    return
                elif path == "/api/settings":
                    settings = Settings(**{k: v for k, v in data.items() if k in Settings.__dataclass_fields__}).validate()
                    with engine.memory.lock:
                        settings.save(settings_path)
                        engine.settings = settings
                        engine.language_model = LanguageModel(settings)
                    result = settings.public()
                elif path == "/api/connection":
                    problem = ProblemSpec.build("Teste local de redação.", intent="greeting")
                    package = AnswerPackage.build(problem, "answered", ["Núcleo disponível."])
                    _, rendering = render_with_arranger(package, engine.language_model, engine.settings.research_mode)
                    ok = rendering["mode"] != "deterministic_fallback"
                    result = {"ok": ok, "rendering": rendering,
                              "message": "Organizador disponível e fiel ao pacote." if rendering["mode"] == "approved_sentence_order"
                              else "Núcleo próprio disponível; nenhuma chamada a modelos gerais." if ok
                              else "Organizador indisponível ou fora do contrato. O núcleo continua funcionando."}
                elif path == "/api/memory/export":
                    with engine.memory.lock:
                        conversations = engine.memory.conversations()
                        chat = [{"conversation": c, "messages": engine.memory.messages(c["id"])} for c in conversations]
                        knowledge = engine.memory.claims()
                    result = {"version": 1, "scope": "local personal laboratory", "conversations": chat,
                              "knowledge": knowledge, "experiences": engine.experience_store.export(),
                              "training_policy": "Conversation text does not authorize weight training."}
                elif path == "/api/memory/backup":
                    # Caller chooses the action, never an arbitrary filesystem path.
                    directory = Path(settings_path).parent / "backups" / uuid.uuid4().hex
                    result = engine.experience_store.backup(directory / "cognition.sqlite3")
                    result["scope"] = "Memória tipada e modelos; exporte também o histórico de conversas."
                elif path.startswith("/api/claims/") and path.endswith("/retract"):
                    claim_id = int(path.split("/")[3])
                    with engine.memory.transaction():
                        invalidated = engine.memory.retract(claim_id)
                    typed = engine.experience_store.invalidate_sources(["M" + str(cid) for cid in [claim_id] + invalidated])
                    result = {"retracted": claim_id, "invalidated": invalidated, "invalidated_experiences": typed}
                else:
                    self.send(404, {"error": "Recurso não encontrado."})
                    return
                self.send(200, result)
            except (ValueError, TypeError, KeyError) as exc:
                self.send(400, {"error": str(exc) if isinstance(exc, ValueError) else "Dados de requisição inválidos."})
            except ProviderError as exc:
                self.send(502, {"error": str(exc)})
            except Exception:
                logging.exception("Falha interna no chatbot")
                self.send(500, {"error": "Não foi possível concluir. Tente enviar novamente."})

        def stream_chat(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True
            connected = True

            def emit(event):
                nonlocal connected
                if connected:
                    try:
                        self.wfile.write((json.dumps(event, ensure_ascii=False) + "\n").encode())
                        self.wfile.flush()
                    except (BrokenPipeError, ConnectionResetError):
                        # Finish and persist an already-started turn, even if the
                        # browser disconnects. Retrying its ID retrieves the result.
                        connected = False

            try:
                result = run_turn(data, on_token=lambda content: emit({"type": "delta", "content": content}),
                                  on_progress=lambda stage: emit({"type": "progress", "stage": stage}))
                emit({"type": "done", "result": result})
            except (ProviderError, ValueError) as exc:
                emit({"type": "error", "error": str(exc)})
            except Exception:
                logging.exception("Falha interna no chatbot")
                emit({"type": "error", "error": "Não foi possível concluir. Tente enviar novamente."})

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.daemon_threads = True
    return server


def main():
    parser = argparse.ArgumentParser(description="Raciocínio Artificial — chatbot com memória e hipóteses")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data/chat")
    parser.add_argument("--cli", action="store_true", help="Conversar no terminal")
    args = parser.parse_args()
    try:
        settings = Settings.load(args.data_dir / "settings.json")
    except ValueError as exc:
        parser.error(str(exc))
    memory = Memory(args.data_dir / "memory.sqlite3")
    engine = ChatEngine(memory, settings)
    local_runtime = start_local_runtime(settings)
    if args.cli:
        cid = memory.create_conversation()["id"]
        print("Raciocínio Artificial. Digite /sair para encerrar. Memória persistente entre sessões.")
        try:
            while True:
                message = input("\nVocê: ")
                if message.strip() == "/sair":
                    break
                try:
                    result = engine.reply(cid, message)
                    print("\nRA: " + result["content"])
                    for warning in result["warnings"]:
                        print("Aviso: " + warning)
                except (ValueError, ProviderError) as exc:
                    print(str(exc))
        except (KeyboardInterrupt, EOFError):
            pass
        finally:
            engine.close()
            memory.close()
            stop_local_runtime(local_runtime)
        return
    server = make_server(engine, args.port, args.data_dir / "settings.json")
    print(f"Raciocínio Artificial: http://127.0.0.1:{server.server_address[1]}", flush=True)
    print(f"Linguagem: {settings.provider}. Memória: {args.data_dir.resolve()}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        engine.close()
        memory.close()
        stop_local_runtime(local_runtime)


if __name__ == "__main__":
    main()
