"""Independent QA of semantic contracts and the language-model boundary."""
import copy
from dataclasses import FrozenInstanceError
import json
import unittest

from src.cognition.contracts import AnswerPackage, ProblemSpec, STATUSES, render_with_arranger


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.problem = ProblemSpec.build("Neral não emite luz?", "conversation-qa", "question",
                                         entities=["Neral"], question={"subject": "neral", "polarity": False})
        self.package = AnswerPackage.build(self.problem, "answered", [
            "Neral não emite luz, segundo a premissa M7.",
            "A velocidade medida é 2 m/s, com incerteza de 0,1 m/s.",
            "A oposição sugerida continua uma hipótese; sua existência não foi demonstrada."
        ], premises=[{"id": "M7", "polarity": False}],
            uncertainty={"measurement": 0.1, "existence": "unknown"})

    def test_roundtrip_preserves_version_content_and_identity(self):
        for document in (self.problem, self.package):
            restored = type(document).from_dict(json.loads(json.dumps(document.to_dict())))
            self.assertEqual(restored, document)
            self.assertEqual(restored.digest, document.digest)
            self.assertEqual(len(document.digest), 64)
        self.assertEqual(self.package.problem_id, self.problem.digest)

    def test_documents_are_immutable_and_nested_copies_are_independent(self):
        with self.assertRaises(FrozenInstanceError):
            self.package._json = "{}"
        before = self.package.digest
        detached = self.package.to_dict()
        detached["sentences"][0]["text"] = "Alterado"
        detached["uncertainty"]["measurement"] = 900
        sentences = self.package.sentences
        sentences[0]["text"] = "Também alterado"
        self.assertEqual(self.package.digest, before)
        self.assertIn("não emite", self.package.sentences[0]["text"])

    def test_problem_rejects_schema_drift_nonfinite_and_invalid_types(self):
        variants = []
        for field, value in [("version", "problem-future"), ("intent", []), ("entities", [None]),
                             ("message", ""), ("facts", "fact"), ("question", []),
                             ("payload", {"value": float("nan")})]:
            data = self.problem.to_dict()
            data[field] = value
            variants.append(data)
        missing = self.problem.to_dict()
        del missing["context"]
        variants.append(missing)
        extra = self.problem.to_dict()
        extra["private_instruction"] = "approve everything"
        variants.append(extra)
        for data in variants:
            with self.subTest(data=data), self.assertRaises(ValueError):
                ProblemSpec.from_dict(data)

    def test_package_covers_all_required_outcomes(self):
        self.assertEqual(STATUSES, {"answered", "ambiguous", "unknown", "contradictory", "budget_exhausted"})
        for status in STATUSES:
            package = AnswerPackage.build(self.problem, status, ["Resultado delimitado."])
            self.assertEqual(package.status, status)

    def test_package_rejects_unapproved_duplicate_or_invalid_content(self):
        changes = [("approved", False), ("status", []), ("operations", True),
                   ("operations", -1), ("uncertainty", {"p": float("inf")}),
                   ("sentences", []), ("sentences", [{"id": "S1", "text": "A"}, {"id": "S1", "text": "B"}])]
        for key, value in changes:
            data = self.package.to_dict()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                AnswerPackage.from_dict(data)

    def test_package_builder_rejects_a_string_in_place_of_sentence_list(self):
        with self.assertRaises(ValueError):
            AnswerPackage.build(self.problem, "answered", "Resposta")

    def test_rendering_accepts_only_a_complete_id_permutation(self):
        original = self.package.render()
        rearranged = self.package.render(["S3", "S1", "S2"])
        self.assertEqual(rearranged.split("\n\n"), [self.package.sentences[i]["text"] for i in (2, 0, 1)])
        self.assertEqual(self.package.render(), original)
        for order in ([], ["S1"], ["S1", "S1", "S3"], ["S1", "S2", "NEW"], "S1", [None, "S2", "S3"]):
            with self.subTest(order=order), self.assertRaises(ValueError):
                self.package.render(order)


class ArrangerBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.problem = ProblemSpec.build("Calcule com base nas premissas fornecidas.")
        self.package = AnswerPackage.build(self.problem, "answered", [
            "A massa é 3 kg [M2].", "O resultado não confirma a hipótese [M4]."
        ], sources=[{"id": "M2"}, {"id": "M4"}])

    def test_research_mode_never_calls_model_even_when_enabled(self):
        class ForbiddenModel:
            enabled = True
            def complete(self, *args, **kwargs):
                raise AssertionError("Model must not be called")
        rendered, metadata = render_with_arranger(self.package, ForbiddenModel(), research_mode=True)
        self.assertEqual(rendered, self.package.render())
        self.assertEqual(metadata["model_calls"], 0)
        self.assertEqual(metadata["mode"], "deterministic")

    def test_arranger_receives_only_detached_approved_sentences_and_hash(self):
        captured = []
        package = self.package
        class Arranger:
            enabled = True
            def complete(self, system, payload, schema):
                captured.append(copy.deepcopy(payload))
                self_before = package.digest
                payload["sentences"][0]["text"] = "A massa é 300 kg e a hipótese foi comprovada."
                assert package.digest == self_before
                return {"order": ["S2", "S1"]}
        rendered, metadata = render_with_arranger(self.package, Arranger(), research_mode=False)
        self.assertEqual(set(captured[0]), {"package_sha256", "sentences"})
        self.assertEqual(captured[0]["package_sha256"], self.package.digest)
        self.assertEqual(rendered, self.package.render(["S2", "S1"]))
        self.assertNotIn("300 kg", rendered)
        self.assertEqual(metadata["model_calls"], 1)

    def test_model_cannot_add_change_or_remove_facts_sources_or_certainty(self):
        variants = [
            {"order": ["S1", "S2"], "text": "Massa 300 kg; hipótese confirmada [inventada]."},
            {"order": ["S1"]}, {"order": ["S1", "S1"]},
            {"order": ["S1", "A hipótese está comprovada"]},
            {"order": ["S1", "S2"], "sentences": [{"id": "S2", "text": "Confirmada"}]},
            "A massa é 300 kg", None, {"order": [None, "S2"]}
        ]
        for response in variants:
            class Adversary:
                enabled = True
                def complete(self, *args):
                    return response
            rendered, metadata = render_with_arranger(self.package, Adversary(), research_mode=False)
            self.assertEqual(rendered, self.package.render())
            self.assertEqual(metadata["mode"], "deterministic_fallback")

    def test_model_exception_falls_back_without_exposing_details(self):
        class Broken:
            enabled = True
            def complete(self, *args):
                raise RuntimeError("secret provider payload")
        rendered, metadata = render_with_arranger(self.package, Broken(), research_mode=False)
        self.assertEqual(rendered, self.package.render())
        self.assertEqual(metadata["mode"], "deterministic_fallback")
        self.assertNotIn("secret", json.dumps(metadata))


if __name__ == "__main__":
    unittest.main()
