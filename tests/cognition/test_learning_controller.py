"""Measured learning gates, held-out isolation, retention and withdrawal."""
import copy
import tempfile
import unittest
from pathlib import Path

from src.cognition.learning import consolidate_model
from src.cognition.store import ExperienceStore


class LearningControllerTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ar-learning-qa-")
        self.addCleanup(self.temporary.cleanup)
        self.store = ExperienceStore(Path(self.temporary.name) / "store.sqlite3")
        self.addCleanup(self.store.close)
        self.training_ids = []
        for value in (1, 2):
            self.training_ids.append(self.store.record("c1", "experiment", {
                "inputs": [value], "target": 2 * value, "sample_ids": ["train-" + str(value)]
            }, ["dataset:qa-train:" + str(value)], status="verified", evidence="experiment"))
        self.validation = [{"id": "validate-3", "inputs": [3], "target": 6},
                           {"id": "validate-4", "inputs": [4], "target": 8}]
        self.retention = [{"id": "retain-minus1", "inputs": [-1], "target": -2},
                          {"id": "retain-minus2", "inputs": [-2], "target": -4}]
        self.policy = {"training_consent": True, "min_gain": .01, "max_validation_error": .001,
                       "max_forgetting": .001, "protocol_id": "qa-controller-v1"}

    @staticmethod
    def trainer(rows):
        return {"weight": sum(r["inputs"][0] * r["target"] for r in rows) /
                sum(r["inputs"][0] ** 2 for r in rows)}

    @staticmethod
    def predictor(artifact, inputs):
        return artifact["weight"] * inputs[0]

    def run_learning(self, **kwargs):
        arguments = dict(store=self.store, conversation_id="c1", name="learned-qa",
                         trainer=self.trainer, predictor=self.predictor,
                         validation=self.validation, retention=self.retention,
                         policy=self.policy, initial_artifact={"weight": 0})
        arguments.update(kwargs)
        return consolidate_model(**arguments)

    def test_adoption_requires_measured_gain_and_preserves_provenance(self):
        result = self.run_learning()
        self.assertEqual(result["status"], "adopted")
        self.assertTrue(result["weights_updated"])
        self.assertEqual(result["metrics"]["validation_mse"], 0)
        self.assertGreater(result["metrics"]["previous_validation_mse"], 0)
        self.assertEqual(result["metrics"]["retention_mse"], 0)
        model = self.store.model("learned-qa")
        self.assertEqual(model["artifact"]["weight"], 2)
        self.assertEqual(set(model["training_ids"]), set(self.training_ids))
        validation_record = self.store.get(model["metrics"]["validation_id"])
        self.assertEqual(validation_record["status"], "verified")
        self.assertEqual(set(validation_record["payload"]["sample_ids"]),
                         {r["id"] for r in self.validation + self.retention})

    def test_trainer_receives_detached_training_only(self):
        calls = []
        original_records = copy.deepcopy(self.store.export()["records"])
        def spy(rows):
            calls.append(copy.deepcopy(rows))
            learned = self.trainer(rows)
            rows[0]["target"] = 999
            rows[0]["inputs"][0] = 999
            return learned
        self.run_learning(trainer=spy)
        self.assertEqual(len(calls), 1)
        self.assertEqual({r["id"] for r in calls[0]}, {"train-1", "train-2"})
        self.assertTrue(all(r["id"] not in {s["id"] for s in self.validation + self.retention} for r in calls[0]))
        self.assertEqual([self.store.get(r["id"])["payload"] for r in original_records], [r["payload"] for r in original_records])

    def test_without_consent_trainer_is_not_called_and_weights_are_not_updated(self):
        policy = dict(self.policy, training_consent=False)
        def forbidden(rows):
            raise AssertionError("Trainer must not run without consent")
        result = self.run_learning(policy=policy, trainer=forbidden)
        self.assertFalse(result["weights_updated"])
        self.assertIsNone(self.store.model("learned-qa"))

    def test_new_task_gain_cannot_override_unacceptable_forgetting(self):
        first = self.run_learning()
        validation = [{"id": "new-validate3", "inputs": [3], "target": 0},
                      {"id": "new-validate4", "inputs": [4], "target": 0}]
        result = self.run_learning(validation=validation, trainer=lambda rows: {"weight": 0})
        self.assertEqual(result["status"], "rejected")
        self.assertTrue(result["metrics"]["passed"])
        self.assertFalse(result["metrics"]["retention_passed"])
        self.assertEqual(self.store.model("learned-qa")["id"], first["model_version"])
        with self.assertRaises(ValueError):
            self.store.rollback_model(result["model_version"])

    def test_memorizing_training_does_not_pass_held_out_performance_gate(self):
        def memorize(rows):
            return {"memorized": {str(r["inputs"][0]): r["target"] for r in rows}}
        def predict(artifact, inputs):
            return artifact.get("memorized", {}).get(str(inputs[0]), 0)
        result = self.run_learning(trainer=memorize, predictor=predict, initial_artifact={"memorized": {}})
        self.assertEqual(result["status"], "rejected")
        self.assertFalse(result["weights_updated"])

    def test_duplicate_ids_and_numerically_equivalent_renamed_samples_are_rejected(self):
        invalid_sets = [
            [{"id": "train-1", "inputs": [3], "target": 6}],
            [{"id": "renamed", "inputs": [1], "target": 2}],
            [{"id": "renamed-floats", "inputs": [1.0], "target": 2.0}],
            [{"id": "same", "inputs": [3], "target": 6}, {"id": "same", "inputs": [4], "target": 8}]
        ]
        for validation in invalid_sets:
            with self.subTest(validation=validation), self.assertRaises(ValueError):
                self.run_learning(validation=validation)

    def test_invalid_candidate_never_activates_or_records_false_success(self):
        before = len(self.store.export()["records"])
        with self.assertRaises(ValueError):
            self.run_learning(trainer=lambda rows: {"weight": float("nan")})
        self.assertIsNone(self.store.model("learned-qa"))
        self.assertEqual(len(self.store.export()["records"]), before)

    def test_withdrawal_disables_then_forget_removes_learned_weights(self):
        result = self.run_learning()
        self.store.retract(self.training_ids[0])
        self.assertIsNone(self.store.model("learned-qa"))
        with self.assertRaises(ValueError):
            self.store.rollback_model(result["model_version"])
        self.store.forget(self.training_ids[0])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM models").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
