"""Adversarial QA of measurement contracts; no scientific reserved cases."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from src.research.baselines import BASELINES
from src.research.evaluation import (
    DEFAULT_PROTOCOL, bootstrap_interval, load_protocol, run_evaluation, score_result,
)
from src.research.worlds import generate_case, hidden_success, fingerprint


ROOT = Path(__file__).resolve().parents[2]


class QAProtocolCase(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ar-f00-qa-")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)
        self.path = self.directory / "qa-protocol.json"
        self.protocol = load_protocol(DEFAULT_PROTOCOL)
        self.protocol["protocol_id"] = "qa-fixture-not-scientific-evidence"
        self.protocol["status"] = "qa_fixture_only"
        self.protocol["cases_per_seed"] = 3
        self.protocol["bootstrap_repetitions"] = 100
        self.protocol["splits"]["development"]["seeds"] = [23017, 91307]
        self.protocol["splits"]["validation"]["seeds"] = [401287, 530117]
        self.protocol["splits"]["reserved"]["seeds"] = [700001, 700003]
        self.write_protocol()

    def write_protocol(self, value=None):
        self.path.write_text(json.dumps(self.protocol if value is None else value, indent=2), encoding="utf-8")


class ProtocolValidation(QAProtocolCase):
    def test_protocol_rejects_invalid_bounds_and_nonnumeric_types(self):
        bad_fields = {
            "cases_per_seed": [0, 4, 102, True, 3.0],
            "evidence_budget": [3, 17, True, 8.0],
            "max_plan_steps": [0, 1, 3, True, 2.0],
            "max_operations_per_case": [0, 10001, True, "128"],
            "max_seconds_per_case": [0, -1, 11, float("nan"), float("inf"), True, "1"],
            "bootstrap_repetitions": [0, 99, 10001, True, 100.0],
            "bootstrap_seed": [-1, 2 ** 32, True, "1"],
            "comparators": [[], ["unknown"], ["memory_only", "memory_only"], [[]], None],
        }
        for key, values in bad_fields.items():
            for value in values:
                with self.subTest(key=key, value=value):
                    bad = copy.deepcopy(self.protocol)
                    bad[key] = value
                    self.write_protocol(bad)
                    with self.assertRaises(ValueError):
                        load_protocol(self.path)

    def test_protocol_rejects_split_overlap_mismatched_families_and_schema_drift(self):
        variants = []
        repeated = copy.deepcopy(self.protocol)
        repeated["splits"]["validation"]["seeds"][0] = repeated["splits"]["development"]["seeds"][0]
        variants.append(repeated)
        repeated = copy.deepcopy(self.protocol)
        repeated["splits"]["validation"]["seeds"] = [401287, 401287]
        variants.append(repeated)
        mismatch = copy.deepcopy(self.protocol)
        mismatch["splits"]["validation"]["family"] = "unary_rewrite"
        variants.append(mismatch)
        mismatch = copy.deepcopy(self.protocol)
        mismatch["generator_version"] = "other-version"
        variants.append(mismatch)
        extra = copy.deepcopy(self.protocol)
        extra["undeclared_decision"] = "changed"
        variants.append(extra)
        missing = copy.deepcopy(self.protocol)
        del missing["decision_rule"]
        variants.append(missing)
        for bad in variants:
            self.write_protocol(bad)
            with self.assertRaises(ValueError):
                load_protocol(self.path)

    def test_reserved_is_rejected_before_loading_or_generating(self):
        with mock.patch("src.research.evaluation.generate_case") as generator:
            with self.assertRaisesRegex(ValueError, "reserved"):
                run_evaluation(self.directory / "does-not-exist.json", "reserved")
            generator.assert_not_called()


class ScoringProperties(unittest.TestCase):
    def test_supported_answer_abstention_miss_and_budget_are_distinct(self):
        answerable = generate_case("validation", 23017, 1)
        insufficient = generate_case("validation", 23017, 2)
        correct = score_result(answerable, {"status": "answered", "plan": answerable.oracle["witness"], "operations": 2})
        self.assertTrue(correct["correct"])
        self.assertTrue(correct["answered"])
        self.assertFalse(correct["correct_abstention"])
        abstention = score_result(insufficient, {"status": "insufficient", "plan": [], "operations": 8})
        self.assertTrue(abstention["correct"])
        self.assertTrue(abstention["correct_abstention"])
        self.assertFalse(abstention["answered"])
        missed = score_result(answerable, {"status": "insufficient", "plan": [], "operations": 8})
        self.assertFalse(missed["correct"])
        self.assertTrue(missed["missed_answer"])
        exhausted = score_result(insufficient, {"status": "budget_exhausted", "plan": [], "operations": 1})
        self.assertFalse(exhausted["correct"])
        self.assertFalse(exhausted["correct_abstention"])

    def test_lucky_hidden_solution_is_not_supported_success(self):
        import itertools
        case = generate_case("validation", 23017, 2)
        plan = next(list(p) for p in itertools.product(case.public["actions"], repeat=2)
                    if hidden_success(case, list(p)))
        score = score_result(case, {"status": "answered", "plan": plan, "operations": 1})
        self.assertTrue(score["hidden_plan_success"])
        self.assertTrue(score["unsupported_answer"])
        self.assertFalse(score["correct"])

    def test_malformed_outputs_are_failures_without_crashing(self):
        case = generate_case("validation", 23017, 0)
        invalid = [None, [], "answered", {}, {"status": []},
                   {"status": [], "plan": [], "operations": 0},
                   {"status": {}, "plan": [], "operations": 0},
                   {"status": "unknown", "plan": [], "operations": 0},
                   {"status": "answered", "plan": "action", "operations": 0},
                   {"status": "answered", "plan": [None], "operations": 0},
                   {"status": "answered", "plan": [], "operations": True},
                   {"status": "answered", "plan": [], "operations": -1},
                   {"status": "answered", "plan": [], "operations": float("nan")},
                   {"status": "insufficient", "plan": ["unexpected"], "operations": 0},
                   {"status": "answered", "plan": [], "operations": 0, "extra": True}]
        for result in invalid:
            with self.subTest(result=result):
                score = score_result(case, result)
                self.assertTrue(score["invalid_output"])
                self.assertFalse(score["correct"])
                self.assertFalse(score["correct_abstention"])

    def test_bootstrap_uses_finite_seed_values_and_is_reproducible(self):
        self.assertEqual(bootstrap_interval([0.5, 0.5], 100, 23017), [0.5, 0.5])
        first = bootstrap_interval([0.1, 0.2, 0.7, 0.9], 100, 23017)
        self.assertEqual(first, bootstrap_interval([0.1, 0.2, 0.7, 0.9], 100, 23017))
        self.assertTrue(0.1 <= first[0] <= first[1] <= 0.9)
        for values in ([], [float("nan")], [float("inf")], [True], ["0.5"]):
            with self.assertRaises(ValueError):
                bootstrap_interval(values, 100, 23017)


class EvaluatorProperties(QAProtocolCase):
    def test_offline_run_reports_actual_denominators_provenance_and_pending_comparators(self):
        with mock.patch("socket.socket", side_effect=AssertionError("Network forbidden in QA")):
            report = run_evaluation(self.path)
        self.assertEqual(report["split"], "validation")
        self.assertFalse(report["reserved_evaluated"])
        self.assertEqual(report["network_calls"], 0)
        self.assertEqual(report["qwen_calls"], 0)
        self.assertEqual(report["protocol_sha256"], hashlib.sha256(self.path.read_bytes()).hexdigest())
        for filename, digest in report["source_sha256"].items():
            self.assertEqual(digest, hashlib.sha256((ROOT / filename).read_bytes()).hexdigest())
        self.assertEqual(len(report["rows"]), 18)
        self.assertEqual(set(report["summary"]), set(self.protocol["comparators"]))
        self.assertEqual(len(report["pending_comparators"]), 4)
        for summary in report["summary"].values():
            self.assertEqual(summary["cases"], 6)
            self.assertEqual(len(summary["seed_success_rates"]), 2)
            self.assertEqual(summary["answer_coverage"], summary["answered"] / 6)
            self.assertTrue(all(entry["cases"] == 2 for entry in summary["by_kind"].values()))
            self.assertTrue(all(math.isfinite(number) for number in summary["seed_bootstrap_95_interval"]))
        self.assertEqual(report["summary"]["memory_only"]["correct"], 4)
        self.assertEqual(report["summary"]["symbolic_search"]["correct"], 6)
        json.dumps(report, allow_nan=False)

    def test_all_comparators_receive_identical_public_evidence(self):
        received = []
        wrappers = {}
        for name, baseline in BASELINES.items():
            def spy(public, budget, name=name, baseline=baseline):
                received.append((name, copy.deepcopy(public)))
                return baseline(public, budget)
            wrappers[name] = spy
        with mock.patch.dict(BASELINES, wrappers):
            report = run_evaluation(self.path)
        for offset in range(0, len(received), 3):
            inputs = received[offset:offset + 3]
            self.assertEqual([name for name, _ in inputs], self.protocol["comparators"])
            self.assertEqual(inputs[0][1], inputs[1][1])
            self.assertEqual(inputs[1][1], inputs[2][1])
            expected_hash = fingerprint(inputs[0][1])
            self.assertTrue(all(row["public_sha256"] == expected_hash for row in report["rows"][offset:offset + 3]))

    def test_mutation_of_input_is_detected_instead_of_scored(self):
        def mutator(public, budget):
            public["question"]["goal"].clear()
            return {"status": "insufficient", "plan": [], "operations": 0}
        with mock.patch.dict(BASELINES, {"memory_only": mutator}):
            with self.assertRaisesRegex(RuntimeError, "mutated"):
                run_evaluation(self.path)

    def test_invalid_comparator_results_are_counted_and_remain_json_serializable(self):
        self.protocol["comparators"] = ["memory_only"]
        self.write_protocol()
        for bad in (None, [], {"status": [], "plan": [], "operations": 0},
                    {"status": "answered", "plan": [], "operations": "broken"},
                    {"status": "answered", "plan": [], "operations": float("nan")},
                    {"status": "answered", "plan": [], "operations": -3}):
            with self.subTest(bad=bad):
                with mock.patch.dict(BASELINES, {"memory_only": lambda public, budget: copy.deepcopy(bad)}):
                    report = run_evaluation(self.path)
                summary = report["summary"]["memory_only"]
                self.assertEqual(summary["invalid_outputs"], 6)
                self.assertEqual(summary["correct"], 0)
                self.assertGreaterEqual(summary["operations_total"], 0)
                json.dumps(report, allow_nan=False)

    def test_exceptions_from_comparators_are_recorded_as_failures(self):
        self.protocol["comparators"] = ["memory_only"]
        self.write_protocol()
        def failure(public, budget):
            raise RuntimeError("sensitive arbitrary exception detail")
        with mock.patch.dict(BASELINES, {"memory_only": failure}):
            report = run_evaluation(self.path)
        self.assertEqual(report["summary"]["memory_only"]["invalid_outputs"], 6)
        self.assertEqual(report["summary"]["memory_only"]["correct"], 0)
        self.assertNotIn("sensitive arbitrary exception detail", json.dumps(report))

    def test_runtime_and_operation_overruns_cannot_be_counted_as_success(self):
        self.protocol["comparators"] = ["symbolic_search"]
        self.write_protocol()
        with mock.patch("src.research.evaluation.time.perf_counter", side_effect=[0.0, 2.0] * 6):
            report = run_evaluation(self.path)
        self.assertEqual(report["summary"]["symbolic_search"]["budget_exhaustions"], 6)
        self.assertEqual(report["summary"]["symbolic_search"]["correct"], 0)
        original = BASELINES["symbolic_search"]
        def over_budget(public, budget):
            result = original(public, budget)
            result["operations"] = budget + 1
            return result
        with mock.patch.dict(BASELINES, {"symbolic_search": over_budget}):
            report = run_evaluation(self.path)
        self.assertEqual(report["summary"]["symbolic_search"]["budget_exhaustions"], 6)
        self.assertEqual(report["summary"]["symbolic_search"]["correct"], 0)


class CommandLineProperties(QAProtocolCase):
    def run_cli(self, *arguments):
        return subprocess.run([sys.executable, str(ROOT / "scripts/evaluate_f00.py"), *map(str, arguments)],
                              cwd=self.directory, capture_output=True, text=True, timeout=30)

    def test_cli_runs_from_another_directory_and_produces_parseable_report(self):
        output = self.directory / "reports" / "qa.json"
        result = self.run_cli("--protocol", self.path, "--output", output)
        self.assertEqual(result.returncode, 0, result.stderr)
        receipt = json.loads(result.stdout)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(receipt["report"], str(output.resolve()))
        self.assertEqual(report["protocol_id"], self.protocol["protocol_id"])
        self.assertFalse(report["reserved_evaluated"])

    def test_cli_preserves_existing_evidence_and_rejects_reserved(self):
        output = self.directory / "existing.json"
        output.write_text("existing evidence\n", encoding="utf-8")
        result = self.run_cli("--protocol", self.path, "--output", output)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already exists", result.stderr)
        self.assertEqual(output.read_text(encoding="utf-8"), "existing evidence\n")
        result = self.run_cli("--protocol", self.path, "--split", "reserved")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)


if __name__ == "__main__":
    unittest.main()
