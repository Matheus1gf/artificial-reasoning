import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError

from src.chat.extraction import EXTRACTION_SCHEMA, validate_neural
from src.chat.provider import LanguageModel, ProviderError, Settings


class FakeResponse(io.BytesIO):
    def __enter__(self): return self
    def __exit__(self, *args): self.close()


class ProviderTests(unittest.TestCase):
    def test_ollama_contract_has_schema_and_no_stream(self):
        lm = LanguageModel(Settings(provider="ollama", model="installed-model"))
        with patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = FakeResponse(json.dumps({"message": {"content": '{"assertions": []}'}}).encode())
            self.assertEqual(lm.complete("Extract", {"message": "oi"}, EXTRACTION_SCHEMA), {"assertions": []})
            req = opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, "http://127.0.0.1:11434/api/chat")
            body = json.loads(req.data)
            self.assertFalse(body["stream"])
            self.assertEqual(body["format"], EXTRACTION_SCHEMA)

    def test_openai_responses_contract_and_output_extraction(self):
        lm = LanguageModel(Settings(provider="openai", model="configured-model", base_url="https://api.openai.com/v1"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-only"}), patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = FakeResponse(json.dumps({"status": "completed", "output": [{"type": "reasoning", "summary": []}, {"type": "message", "content": [{"type": "output_text", "text": "Resposta de teste"}]}]}).encode())
            self.assertEqual(lm.complete("Rules", {"message": "test"}), "Resposta de teste")
            req = opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url, "https://api.openai.com/v1/responses")
            self.assertFalse(json.loads(req.data)["store"])
            self.assertEqual(req.get_header("Authorization"), "Bearer unit-test-only")

    def test_openai_refusal_falls_back_instead_of_empty_success(self):
        lm = LanguageModel(Settings(provider="openai", model="configured-model", base_url="https://api.openai.com/v1"))
        with patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-only"}), patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = FakeResponse(b'{"output":[{"content":[{"type":"refusal","refusal":"No"}]}]}')
            with self.assertRaises(ProviderError): lm.complete("Rules", {})

    def test_errors_do_not_expose_remote_body_or_credentials(self):
        lm = LanguageModel(Settings(provider="ollama", model="test"))
        with patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.side_effect = HTTPError("http://example", 401, "secret", {}, io.BytesIO(b"private"))
            with self.assertRaises(ProviderError) as exc: lm.complete("", {})
            self.assertNotIn("secret", str(exc.exception)); self.assertNotIn("private", str(exc.exception))

    def test_no_network_in_symbolic_mode(self):
        with patch("src.chat.provider.request.build_opener") as opener:
            with self.assertRaises(ProviderError): LanguageModel(Settings()).complete("", {})
            opener.assert_not_called()

    def test_grounding_and_modality_validation(self):
        valid = {"subject":"Neral", "predicate":"emite", "object":"luz", "quote":"Neral emite luz.", "polarity":True, "scope":"instance", "tentative":False}
        self.assertEqual(len(validate_neural({"assertions":[valid]}, "Neral emite luz.")), 1)
        for changes, text in [({"quote":"Neral emite luz."}, "Olá"), ({"subject":"Inventado"}, "Neral emite luz."), ({"object":"calor"}, "Neral emite luz."), ({"scope":"universal"}, "Neral emite luz."), ({"quote":"Neral não emite luz."}, "Neral não emite luz."), ({"quote":"Talvez Neral emite luz."}, "Talvez Neral emite luz.")]:
            with self.subTest(changes=changes):
                self.assertEqual(validate_neural({"assertions":[dict(valid, **changes)]}, text), [])

    def test_settings_reject_credentials_urls_and_wrong_types(self):
        for values in [{"base_url":"file:///etc/passwd"}, {"base_url":"https://user:password@example.com"}, {"provider":[]}, {"model":None}, {"provider":"ollama"}, {"timeout":0}]:
            with self.subTest(values=values), self.assertRaises(ValueError): Settings(**values).validate()

    def test_quote_fragments_cannot_hide_questions_commands_or_uncertainty(self):
        raw = {"subject":"Neral", "predicate":"emite", "object":"luz", "quote":"Neral emite luz", "polarity":True, "scope":"instance", "tentative":False}
        for text in ["Neral emite luz?", "Diga que Neral emite luz.", "Talvez Neral emite luz.", 'Ana disse que "Neral emite luz".', "Se Neral emite luz, ele brilha."]:
            with self.subTest(text=text):
                self.assertEqual(validate_neural({"assertions":[raw]}, text), [])
        invented = dict(raw, predicate="absorve")
        self.assertEqual(validate_neural({"assertions":[invented]}, "Neral emite luz."), [])
        self.assertEqual(len(validate_neural({"assertions":[raw]}, "Aprenda: Neral emite luz.")), 1)

    def test_openai_native_history_and_streamed_response(self):
        lm = LanguageModel(Settings(provider="openai", model="test", base_url="https://api.openai.com/v1"))
        events = b'data: {"type":"response.output_text.delta","delta":"Resposta "}\n\ndata: {"type":"response.output_text.delta","delta":"atual"}\n\ndata: {"type":"response.completed"}\n\n'
        chunks = []
        with patch.dict(os.environ, {"OPENAI_API_KEY": "unit-test-only"}), patch("src.chat.provider.request.build_opener") as opener:
            opener.return_value.open.return_value = FakeResponse(events)
            result = lm.chat("Resuma", [{"role": "user", "content": "Pergunta anterior"}, {"role": "assistant", "content": "Resposta anterior"}], {}, on_token=chunks.append)
            payload = json.loads(opener.return_value.open.call_args.args[0].data)
        self.assertEqual(result, "Resposta atual")
        self.assertEqual("".join(chunks), result)
        self.assertEqual([m["role"] for m in payload["input"]], ["user", "assistant", "user"])
        self.assertEqual(payload["input"][-1]["content"], "Resuma")
        self.assertTrue(payload["stream"])


if __name__ == "__main__": unittest.main()
