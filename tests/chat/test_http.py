import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib import error, request
from unittest.mock import patch

from src.cognition.store import ExperienceStore

from src.chat.engine import ChatEngine
from src.chat.domain import normalize
from src.chat.memory import Memory
from src.chat.server import make_server


class HttpTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.memory = Memory(Path(cls.temp.name) / "test.sqlite3")
        cls.engine = ChatEngine(cls.memory)
        cls.server = make_server(cls.engine, 0, Path(cls.temp.name) / "settings.json")
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:" + str(cls.server.server_address[1])
        cls.token = cls.get("/api/state")["token"]

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown(); cls.server.server_close(); cls.thread.join()
        cls.engine.close(); cls.memory.close(); cls.temp.cleanup()

    @classmethod
    def get(cls, path):
        with request.urlopen(cls.base + path, timeout=5) as r: return json.load(r)

    def post(self, path, data, headers=None):
        req = request.Request(self.base + path, data=json.dumps(data).encode(), headers=headers or {"Content-Type":"application/json", "X-Workspace-Token":self.token}, method="POST")
        with request.urlopen(req, timeout=5) as r: return json.load(r)

    def test_research_connection_is_offline_and_package_metadata_survives_http(self):
        with patch.object(self.engine.language_model,"complete",side_effect=AssertionError("model call")):
            health=self.get("/api/health")
            connection=self.post("/api/connection",{})
            cid=self.post("/api/conversations",{})["id"]
            result=self.post("/api/chat",{"conversation_id":cid,"message":"Calcule 9*8."})
        self.assertTrue(health["research_mode"])
        self.assertEqual(connection["rendering"]["model_calls"],0)
        self.assertEqual(result["answer_package"]["conclusions"][0]["value"],72)
        self.assertTrue(result["reasoning"]["package_ready_before_model"])
        self.assertEqual(set(result["reasoning"]["timings"]),{"comprehension","memory","reasoning_verification","rendering"})

    def test_natural_conversation_target_hypotheses_survive_stream_reload_and_retraction(self):
        cid=self.post('/api/conversations',{})['id']
        with patch.object(self.engine.language_model,'complete',side_effect=AssertionError('Qwen is forbidden')):
            learned=self.post('/api/chat',{'conversation_id':cid,'message':'Quelor é um dispositivo que armazena energia e recebe luz por causa da sua estrutura.'})
            before={c['id'] for c in self.memory.claims() if c['origin']=='user'}
            conditional=self.post('/api/chat',{'conversation_id':cid,'message':'Considerando que Sivor é o inverso de Quelor, o que seria Sivor?'})
            self.assertEqual(before,{c['id'] for c in self.memory.claims() if c['origin']=='user'})
            self.assertTrue(any(h.get('subject')=='sivor' and h.get('predicate')=='libera' for h in conditional['answer_package']['hypotheses']))
            self.post('/api/chat',{'conversation_id':cid,'message':'Sivor é o inverso de Quelor.'})
            body={'conversation_id':cid,'message':'O que é Sivor?','request_id':'qa-natural-stream'}
            req=request.Request(self.base+'/api/chat/stream',data=json.dumps(body).encode(),
                                headers={'Content-Type':'application/json','X-Workspace-Token':self.token})
            with request.urlopen(req,timeout=5) as response: events=[json.loads(line) for line in response]
        self.assertEqual(events[-1]['type'],'done')
        self.assertLess(next(i for i,e in enumerate(events) if e.get('stage')=='verified'),
                        next(i for i,e in enumerate(events) if e['type']=='delta'))
        result=events[-1]['result']
        self.assertEqual(result['focus'],'sivor')
        self.assertEqual(result['reasoning']['model_calls'],0)
        expected={('sivor','libera','energia'),('sivor','emite','luz')}
        self.assertTrue(expected <= {(h.get('subject'),h.get('predicate'),h.get('object')) for h in result['answer_package']['hypotheses']})
        self.assertNotIn('sivor tem estrutura',normalize(result['content']))
        loaded=self.get('/api/conversations/'+cid)['messages'][-1]
        self.assertEqual(loaded['content'],result['content'])
        self.assertEqual(self.post('/api/chat',body),result)
        premise=next(c for c in learned['learned'] if c['predicate']=='armazena')
        self.post('/api/claims/'+str(premise['id'])+'/retract',{})
        withdrawn=self.post('/api/chat',{'conversation_id':cid,'message':'O que é Sivor?'})
        self.assertFalse(any(h.get('subject')=='sivor' and h.get('predicate')=='libera' for h in withdrawn['answer_package']['hypotheses']))

    def test_typed_experiences_export_backup_and_retraction_are_integrated(self):
        cid=self.post("/api/conversations",{})["id"]
        result=self.post("/api/chat",{"conversation_id":cid,"message":"QAobj armazena calor."})
        ids=set(result["experience_ids"])
        typed=self.get("/api/experiences?conversation_id="+cid)["experiences"]
        self.assertTrue(ids <= {item["id"] for item in typed})
        exported=self.post("/api/memory/export",{})
        self.assertTrue(any(c["conversation"]["id"]==cid for c in exported["conversations"]))
        self.assertTrue(ids <= {item["id"] for item in exported["experiences"]["records"]})
        backup=self.post("/api/memory/backup",{})
        self.assertTrue(Path(backup["path"]).is_relative_to(Path(self.temp.name)/"backups"))
        restored=ExperienceStore.restore(backup["path"],Path(self.temp.name)/"http-restored.db")
        try: self.assertTrue(ids <= {item["id"] for item in restored.export()["records"]})
        finally: restored.close()
        claim=result["learned"][0]["id"]
        retracted=self.post("/api/claims/"+str(claim)+"/retract",{})
        self.assertTrue(retracted["invalidated_experiences"])
        remaining={item["id"] for item in self.get("/api/experiences?conversation_id="+cid)["experiences"]}
        self.assertFalse(set(retracted["invalidated_experiences"]) & remaining)

    def test_http_cancellation_reaches_running_turn_and_retry_resumes_once(self):
        cid=self.post("/api/conversations",{})["id"]
        entered=threading.Event(); release=threading.Event(); actual=self.engine.core.solve
        def controlled(problem,context):
            entered.set(); release.wait(timeout=3)
            return actual(problem,context)
        body={"conversation_id":cid,"message":"Cancelobj emite luz.","request_id":"qa-http-cancel"}
        with patch.object(self.engine.core,"solve",side_effect=controlled):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending=pool.submit(self.post,"/api/chat",body)
                self.assertTrue(entered.wait(timeout=1))
                result=self.post("/api/chat/cancel",{"request_id":body["request_id"]})
                self.assertTrue(result["requested"])
                release.set()
                with self.assertRaises(error.HTTPError) as exc: pending.result(timeout=3)
                self.assertEqual(exc.exception.code,400)
        self.assertEqual(len(self.get("/api/conversations/"+cid)["messages"]),1)
        result=self.post("/api/chat",body)
        self.assertEqual(result["answer_package"]["status"],"answered")
        self.assertEqual(len(self.get("/api/conversations/"+cid)["messages"]),2)
        self.assertFalse(self.post("/api/chat/cancel",{"request_id":body["request_id"]})["requested"])

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
            if not results:
                self.assertEqual([e["stage"] for e in events if e["type"]=="progress"],["processing","verified"])
                self.assertLess(next(i for i,e in enumerate(events) if e.get("stage")=="verified"),next(i for i,e in enumerate(events) if e["type"]=="delta"))
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
