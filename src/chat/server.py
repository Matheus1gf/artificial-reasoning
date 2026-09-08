"""Local single-user HTTP application, implemented with the Python standard library."""
import argparse
import json
import logging
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from .engine import ChatEngine
from .memory import Memory
from .provider import LanguageModel, ProviderError, Settings
from .runtime import start_local_runtime, stop_local_runtime


ROOT = Path(__file__).resolve().parents[2]
STATIC = Path(__file__).parent / "web"


def make_server(engine, port=8765, settings_path=None):
    token = secrets.token_urlsafe(32)
    settings_path = settings_path or ROOT / "data/chat/settings.json"

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
                        self.send(200, {"status": "ok", "provider": engine.settings.provider})
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
                    result = engine.reply(data.get("conversation_id"), data.get("message"), data.get("request_id"))
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
                    with engine.memory.lock:
                        if engine.language_model.enabled:
                            engine.language_model.complete("Responda apenas OK.", {"message": "Teste de conexão"})
                    result = {"ok": True, "message": "Conexão funcionando." if engine.language_model.enabled else "Motor simbólico local disponível."}
                elif path.startswith("/api/claims/") and path.endswith("/retract"):
                    claim_id = int(path.split("/")[3])
                    with engine.memory.transaction():
                        invalidated = engine.memory.retract(claim_id)
                    result = {"retracted": claim_id, "invalidated": invalidated}
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
                result = engine.reply(data.get("conversation_id"), data.get("message"), data.get("request_id"),
                                      on_token=lambda content: emit({"type": "delta", "content": content}))
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
        memory.close()
        stop_local_runtime(local_runtime)


if __name__ == "__main__":
    main()
