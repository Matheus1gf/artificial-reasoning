import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import error, request

from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.chat.server import make_server


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.memory = Memory(Path(cls.temp.name) / "test.sqlite3")
        cls.server = make_server(ChatEngine(cls.memory), 0, Path(cls.temp.name) / "settings.json")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_address[1])
        cls.token = cls.get("/api/state")["token"]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.memory.close(); cls.temp.cleanup()

    @classmethod
    def get(cls, path):
        with request.urlopen(cls.base + path, timeout=5) as r: return json.load(r)

    def post(self, path, data, headers=None):
        req = request.Request(self.base + path, data=json.dumps(data).encode(), headers=headers or {"Content-Type":"application/json", "X-Workspace-Token":self.token}, method="POST")
        with request.urlopen(req, timeout=5) as r: return json.load(r)

    def test_real_http_roundtrip_and_reload(self):
        cid = self.post("/api/conversations", {})["id"]
        result = self.post("/api/chat", {"conversation_id":cid, "message":"Uma caixa armazena energia.", "request_id":"http-test"})
        self.assertEqual(len(result["learned"]), 1)
        loaded = self.get("/api/conversations/" + cid)
        self.assertEqual(len(loaded["messages"]), 2)
        self.assertEqual(loaded["messages"][1]["content"], result["content"])

    def test_concurrent_retry_creates_one_turn(self):
        cid = self.post("/api/conversations", {})["id"]
        body = {"conversation_id":cid, "message":"Vetra armazena luz.", "request_id":"concurrent-http"}
        with ThreadPoolExecutor(max_workers=4) as pool: results = list(pool.map(lambda _: self.post("/api/chat",body), range(4)))
        self.assertTrue(all(r == results[0] for r in results))
        self.assertEqual(len(self.get("/api/conversations/"+cid)["messages"]),2)

    def test_csrf_token_and_origin_are_required_for_writes(self):
        for headers in [{"Content-Type":"application/json"}, {"Content-Type":"application/json","X-Workspace-Token":self.token,"Origin":"https://evil.example"}]:
            with self.subTest(headers=headers), self.assertRaises(error.HTTPError) as exc:
                self.post("/api/conversations", {}, headers)
            self.assertEqual(exc.exception.code,403)

    def test_rebinding_host_and_traversal_rejected(self):
        with self.assertRaises(error.HTTPError) as exc:
            request.urlopen(request.Request(self.base+"/api/state",headers={"Host":"evil.example"}),timeout=5)
        self.assertEqual(exc.exception.code,403)
        with self.assertRaises(error.HTTPError) as exc: self.get("/../../README.md")
        self.assertEqual(exc.exception.code,404)

    def test_static_assets_have_csp_and_no_inline_scripts(self):
        with request.urlopen(self.base,timeout=5) as response:
            self.assertIn("frame-ancestors 'none'",response.headers["Content-Security-Policy"])
            self.assertIn('lang="pt-BR"',response.read().decode())
        with request.urlopen(self.base+"/app.js",timeout=5) as response:
            self.assertNotIn("innerHTML",response.read().decode())

    def test_api_retraction_invalidates_hypothesis(self):
        cid = self.post("/api/conversations",{})["id"]
        fact = self.post("/api/chat",{"conversation_id":cid,"message":"Neral aquece ar."})["learned"][0]
        hypothesis = self.post("/api/chat",{"conversation_id":cid,"message":"Qual seria o oposto de Neral?"})["inferences"][0]
        result = self.post(f"/api/claims/{fact['id']}/retract",{})
        self.assertIn(hypothesis["id"],result["invalidated"])

    def test_invalid_input_has_no_partial_message(self):
        cid = self.post("/api/conversations",{})["id"]
        with self.assertRaises(error.HTTPError) as exc: self.post("/api/chat",{"conversation_id":cid,"message":123})
        self.assertEqual(exc.exception.code,400)
        self.assertEqual(self.get("/api/conversations/"+cid)["messages"],[])

    def test_stream_endpoint_finishes_and_retry_does_not_duplicate_turn(self):
        cid = self.post("/api/conversations", {})["id"]
        body = {"conversation_id": cid, "message": "Uma bateria armazena energia.", "request_id": "http-stream"}
        results = []
        for _ in range(2):
            req = request.Request(self.base + "/api/chat/stream", data=json.dumps(body).encode(),
                                  headers={"Content-Type": "application/json", "X-Workspace-Token": self.token})
            with request.urlopen(req, timeout=5) as response:
                self.assertIn("application/x-ndjson", response.headers["Content-Type"])
                events = [json.loads(line) for line in response]
            self.assertEqual(events[-1]["type"], "done")
            results.append(events[-1]["result"])
        self.assertEqual(results[0], results[1])
        self.assertEqual(len(self.get("/api/conversations/" + cid)["messages"]), 2)

    def test_stream_validation_error_does_not_persist_a_fake_answer(self):
        cid = self.post("/api/conversations", {})["id"]
        req = request.Request(self.base + "/api/chat/stream", data=json.dumps({"conversation_id": cid, "message": ""}).encode(),
                              headers={"Content-Type": "application/json", "X-Workspace-Token": self.token})
        with request.urlopen(req, timeout=5) as response:
            events = [json.loads(line) for line in response]
        self.assertEqual(events[-1]["type"], "error")
        self.assertEqual(self.get("/api/conversations/" + cid)["messages"], [])


if __name__ == "__main__": unittest.main()
