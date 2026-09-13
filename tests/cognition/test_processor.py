"""Question-sensitive own parsing, source spans and conversation isolation."""
import json
import unittest

from src.cognition.processor import process_message
from src.chat.domain import normalize


class ProcessorTests(unittest.TestCase):
    def test_intentions_and_polarity_are_distinguished(self):
        examples = [("Neral emite luz.", "statement"), ("Neral emite luz?", "question"),
                    ("Corrigindo: Neral não emite luz.", "correction"), ("Talvez Neral emite luz.", "hypothesis"),
                    ("Crie uma solução para luz.", "creation"), ("Prefiro respostas curtas.", "preference")]
        for text, expected in examples:
            with self.subTest(text=text):
                self.assertEqual(process_message(text).intent, expected)
        negative = process_message("Todo cristal não emite luz.")
        self.assertEqual(negative.facts[0]["scope"], "universal")
        self.assertFalse(negative.facts[0]["polarity"])
        self.assertTrue(process_message("Talvez Neral emite luz.").facts[0]["tentative"])
        self.assertEqual(process_message("Se Neral emite luz, ele aquece água.").facts, [])

    def test_references_are_resolved_only_with_unambiguous_local_context(self):
        history = [{"role": "assistant", "id": 5, "metadata": {"focus": "neral", "problem": {"entities": ["neral"]}}}]
        self.assertEqual(process_message("Ele emite luz.", history).facts[0]["subject"], "neral")
        self.assertTrue(process_message("Ele emite luz.", []).ambiguities)
        ambiguous = [{"role": "assistant", "metadata": {"problem": {"entities": ["neral", "vetra"]}}}]
        problem = process_message("Ele emite luz.", ambiguous)
        self.assertEqual(problem.facts, [])
        self.assertEqual(problem.ambiguities[0]["candidates"], ["neral", "vetra"])

    def test_new_compound_subject_does_not_inherit_old_topic(self):
        history = [{"role": "assistant", "metadata": {"focus": "banco de dados", "problem": {"entities": ["banco de dados"]}}}]
        problem = process_message("O que é um banco de sangue?", history)
        self.assertEqual(problem.question["subject"], "banco de sangue")
        self.assertEqual(problem.entities, ["banco de sangue"])

    def test_quantities_units_intervals_and_format_are_preserved(self):
        problem = process_message("Calcule 2 km/h * 3 s em exatamente 5 palavras.")
        quantities = problem.payload["quantities"]
        self.assertAlmostEqual(quantities[0]["si_value"], 2 / 3.6)
        self.assertEqual(quantities[0]["dimensions"], [1, -1, 0])
        self.assertEqual(quantities[1]["dimensions"], [0, 1, 0])
        for quantity in quantities:
            self.assertEqual(problem.message[slice(*quantity["span"])], quantity["quote"])
        self.assertEqual(problem.constraints["words"], {"value": 5, "exact": True})
        inverted = process_message("A posição está entre 5 e 2 m.")
        self.assertTrue(any(a["kind"] == "interval" for a in inverted.ambiguities))

    def test_temporal_spans_point_to_original_message_even_with_extra_spaces(self):
        problem = process_message("Neral  emite luz antes de Vetra.")
        for item in problem.payload["temporal"]:
            self.assertEqual(normalize(problem.message[slice(*item["span"])]), item["relation"])

    def test_structured_requests_and_domain_payloads_are_not_reinterpreted_by_a_model(self):
        request = {"task": "induce", "examples": [{"x": 0, "y": 1}], "query": 2}
        problem = process_message(json.dumps(request))
        self.assertEqual(problem.intent, "induction")
        self.assertEqual(problem.payload["structured"], request)
        domain = {"domain": "physics", "operation": "simulate", "parameters": {"x": 0, "v": 1, "dt": 1}}
        self.assertEqual(process_message(json.dumps(domain)).payload["request"], domain)
        for invalid in ("[]", '{"task":"unknown"}', '{"task":"calculate","value":NaN}'):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                process_message(invalid)


if __name__ == "__main__":
    unittest.main()
