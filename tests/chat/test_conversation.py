import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.chat.provider import LanguageModel, ProviderError, Settings
from src.chat.reasoner import retrieve


class RecordingModel:
    enabled = True

    def __init__(self):
        self.calls = []
        self.fail = False

    def complete(self, system, payload, schema):
        self.calls.append(payload)
        if self.fail:
            raise ProviderError("Organizador indisponível")
        return {"order": [item["id"] for item in reversed(payload["sentences"])]}

    def chat(self, *args, **kwargs):
        raise AssertionError("Chat geral não pertence ao caminho cognitivo")


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory(":memory:")
        self.cid = self.memory.create_conversation()["id"]
        self.model = RecordingModel()
        self.engine = ChatEngine(self.memory, Settings(provider="ollama", model="test", research_mode=False), self.model)

    def tearDown(self):
        self.engine.close()
        self.memory.close()

    def test_new_named_topic_does_not_retrieve_old_compound_concept(self):
        self.engine.reply(self.cid, "Um buraco negro absorve matéria.")
        self.engine.reply(self.cid, "Qual seria o oposto de um buraco negro?")
        r = self.engine.reply(self.cid, "O que é um buraco de minhoca?")
        self.assertEqual(r["retrieved"], [])
        self.assertEqual(r["inferences"], [])
        self.assertEqual(r["focus"], "buraco de minhoca")
        self.assertEqual(r["answer_package"]["status"], "unknown")
        self.assertNotIn("expulsa", r["content"])

    def test_compound_topic_filter_is_not_specific_to_astronomy(self):
        self.engine.reply(self.cid, "Um banco de dados armazena informação.")
        r = self.engine.reply(self.cid, "O que é um banco de sangue?")
        self.assertEqual(r["retrieved"], [])

    def test_core_resolves_followup_before_arranger_receives_approved_sentences(self):
        first = self.engine.reply(self.cid, "Neral emite luz.")
        second = self.engine.reply(self.cid, "Resuma isso.")
        self.assertEqual(second["problem"]["message"], "Resuma isso.")
        self.assertIn("neral", second["content"])
        self.assertEqual(second["problem"]["context"]["previous_approved"], first["answer_package"])
        self.assertEqual(set(self.model.calls[-1]), {"package_sha256", "sentences"})
        self.assertEqual(self.model.calls[-1]["sentences"], second["answer_package"]["sentences"])

    def test_new_conversation_does_not_receive_another_transcript(self):
        self.engine.reply(self.cid, "Neral emite luz.")
        second = self.memory.create_conversation()["id"]
        r = self.engine.reply(second, "Resuma isso.")
        self.assertNotIn("previous_approved", r["problem"]["context"])
        self.assertNotIn("neral", r["content"])

    def test_general_question_with_no_evidence_remains_unknown_before_arrangement(self):
        r = self.engine.reply(self.cid, "O que é uma célula?")
        self.assertEqual(r["answer_package"]["status"], "unknown")
        self.assertEqual(r["learned"], [])
        self.assertEqual(len(self.model.calls), 1)
        self.assertEqual(r["content"], r["answer_package"]["sentences"][0]["text"])

    def test_failed_arrangement_preserves_local_extraction_and_verified_content(self):
        self.model.fail = True
        r = self.engine.reply(self.cid, "Neral armazena energia.")
        self.assertEqual(r["provider"], "symbolic")
        self.assertEqual(len(r["learned"]), 1)
        self.assertIn("neral armazena energia", r["content"])
        self.assertTrue(r["warnings"])
        self.assertEqual(r["rendering"]["mode"], "deterministic_fallback")

    def test_new_unknown_topic_does_not_inherit_old_subject(self):
        self.engine.reply(self.cid, "Neral armazena energia.")
        r = self.engine.reply(self.cid, "Qual seria o oposto de Vetra?")
        self.assertEqual(r["retrieved"], [])
        self.assertNotIn("neral", r["content"])

    def test_tokens_and_persisted_response_belong_to_same_turn(self):
        chunks = []
        def capture(chunk):
            self.assertEqual(self.memory.messages(self.cid)[-1]["content"], chunk)
            chunks.append(chunk)
        r = self.engine.reply(self.cid, "Explique a gravidade.", "stream-id", on_token=capture)
        self.assertEqual("".join(chunks), r["content"])
        retry_chunks = []
        self.assertEqual(self.engine.reply(self.cid, "Explique a gravidade.", "stream-id", on_token=retry_chunks.append), r)
        self.assertEqual(retry_chunks, [])


class NativeMessageTests(unittest.TestCase):
    def test_ollama_preserves_answered_turns_and_puts_current_message_last(self):
        lm = LanguageModel(Settings(provider="ollama", model="test", research_mode=False))
        history = [{"role": "user", "content": "Primeira pergunta"},
                   {"role": "assistant", "content": "Resposta anterior", "metadata": {"provider": "ollama"}},
                   {"role": "user", "content": "Segunda pergunta"},
                   {"role": "assistant", "content": "Template antigo", "metadata": {"provider": "symbolic"}}]
        with patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"message":{"content":"Resposta nova"}}')
            lm.chat("Pergunta atual", history, {})
            body = json.loads(opener.return_value.open.call_args.args[0].data)
            self.assertEqual(body["messages"][-1], {"role": "user", "content": "Pergunta atual"})
            self.assertEqual([m["role"] for m in body["messages"]], ["system", "user", "assistant", "user", "assistant", "user"])
            self.assertEqual(body["messages"][-2]["content"], "Template antigo")

    def test_streamed_ollama_deltas_are_not_thinking(self):
        lm = LanguageModel(Settings(provider="ollama", model="test", research_mode=False))
        response = io.BytesIO(b'{"message":{"thinking":"private","content":"Ola "},"done":false}\n{"message":{"content":"mundo"},"done":true}\n')
        chunks = []
        with patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(lm.chat("Oi", [], {}, on_token=chunks.append), "Ola mundo")
        self.assertEqual(chunks, ["Ola ", "mundo"])

    def test_incomplete_stream_is_not_reported_as_success(self):
        lm = LanguageModel(Settings(provider="ollama", model="test", research_mode=False))
        with patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"message":{"content":"Parcial"},"done":false}\n')
            with self.assertRaises(ProviderError):
                lm.chat("Oi", [], {}, on_token=lambda _: None)

    def test_web_defaults_to_own_research_core(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings.load(Path(folder) / "settings.json")
        self.assertEqual(settings.provider, "symbolic")
        self.assertTrue(settings.research_mode)


if __name__ == "__main__":
    unittest.main()
