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
        self.extractions = 0
        self.extraction_error = False

    def complete(self, *args, **kwargs):
        self.extractions += 1
        if self.extraction_error:
            raise ProviderError("Extração indisponível")
        return {"assertions": []}

    def chat(self, message, history, context, on_token=None):
        self.calls.append({"message": message, "history": history, "context": context})
        if on_token:
            on_token("Resposta ")
            on_token("neural")
        return "Resposta neural"


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory(":memory:")
        self.cid = self.memory.create_conversation()["id"]
        self.model = RecordingModel()
        self.engine = ChatEngine(self.memory, Settings(provider="ollama", model="test"), self.model)

    def tearDown(self):
        self.memory.close()

    def test_new_named_topic_does_not_retrieve_old_compound_concept(self):
        self.engine.reply(self.cid, "Um buraco negro absorve matéria.")
        self.engine.reply(self.cid, "Qual seria o oposto de um buraco negro?")
        r = self.engine.reply(self.cid, "O que é um buraco de minhoca?")
        self.assertEqual(r["retrieved"], [])
        self.assertEqual(r["inferences"], [])
        self.assertEqual(r["focus"], "buraco de minhoca")
        self.assertEqual(r["provider"], "ollama")

    def test_compound_topic_filter_is_not_specific_to_astronomy(self):
        self.engine.reply(self.cid, "Um banco de dados armazena informação.")
        r = self.engine.reply(self.cid, "O que é um banco de sangue?")
        self.assertEqual(r["retrieved"], [])

    def test_neural_reply_receives_current_message_and_same_conversation_history(self):
        self.engine.reply(self.cid, "O que é fotossíntese?")
        self.engine.reply(self.cid, "Explique isso em termos mais simples.")
        call = self.model.calls[-1]
        self.assertEqual(call["message"], "Explique isso em termos mais simples.")
        self.assertEqual([m["role"] for m in call["history"]], ["user", "assistant"])
        self.assertEqual(call["history"][0]["content"], "O que é fotossíntese?")

    def test_new_conversation_does_not_receive_another_transcript(self):
        self.engine.reply(self.cid, "Explique como escrever um poema.")
        second = self.memory.create_conversation()["id"]
        self.engine.reply(second, "Sobre o que estamos conversando?")
        self.assertEqual(self.model.calls[-1]["history"], [])

    def test_general_question_works_with_no_learned_memory(self):
        r = self.engine.reply(self.cid, "O que é uma célula?")
        self.assertEqual(r["content"], "Resposta neural")
        self.assertEqual(r["learned"], [])
        self.assertEqual(self.model.extractions, 0)

    def test_failed_extraction_does_not_disable_neural_response(self):
        self.model.extraction_error = True
        r = self.engine.reply(self.cid, "Neral armazena energia.")
        self.assertEqual(r["provider"], "ollama")
        self.assertEqual(len(r["learned"]), 1)
        self.assertEqual(r["content"], "Resposta neural")
        self.assertTrue(r["warnings"])

    def test_new_unknown_topic_does_not_inherit_old_subject(self):
        self.engine.reply(self.cid, "Neral armazena energia.")
        self.engine.reply(self.cid, "Qual seria o oposto de Vetra?")
        self.assertEqual(self.model.calls[-1]["context"]["memories"], [])

    def test_tokens_and_persisted_response_belong_to_same_turn(self):
        chunks = []
        r = self.engine.reply(self.cid, "Explique a gravidade.", "stream-id", on_token=chunks.append)
        self.assertEqual("".join(chunks), r["content"])
        self.assertEqual(self.memory.messages(self.cid)[-1]["content"], r["content"])
        retry_chunks = []
        self.assertEqual(self.engine.reply(self.cid, "Explique a gravidade.", "stream-id", on_token=retry_chunks.append), r)
        self.assertEqual(retry_chunks, [])


class NativeMessageTests(unittest.TestCase):
    def test_ollama_preserves_answered_turns_and_puts_current_message_last(self):
        lm = LanguageModel(Settings(provider="ollama", model="test"))
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
        lm = LanguageModel(Settings(provider="ollama", model="test"))
        response = io.BytesIO(b'{"message":{"thinking":"private","content":"Ola "},"done":false}\n{"message":{"content":"mundo"},"done":true}\n')
        chunks = []
        with patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = response
            self.assertEqual(lm.chat("Oi", [], {}, on_token=chunks.append), "Ola mundo")
        self.assertEqual(chunks, ["Ola ", "mundo"])

    def test_incomplete_stream_is_not_reported_as_success(self):
        lm = LanguageModel(Settings(provider="ollama", model="test"))
        with patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = io.BytesIO(b'{"message":{"content":"Parcial"},"done":false}\n')
            with self.assertRaises(ProviderError):
                lm.chat("Oi", [], {}, on_token=lambda _: None)

    def test_web_defaults_to_general_conversation(self):
        with tempfile.TemporaryDirectory() as folder:
            settings = Settings.load(Path(folder) / "settings.json")
        self.assertEqual(settings.provider, "ollama")
        self.assertTrue(settings.model)


if __name__ == "__main__":
    unittest.main()
