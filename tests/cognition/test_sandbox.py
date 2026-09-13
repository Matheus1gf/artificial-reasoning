"""Subprocess, finite-language and actual resource-stop checks."""
import os
import subprocess
import threading
import unittest
from unittest import mock

from src.cognition.sandbox import execute_program


class SandboxTests(unittest.TestCase):
    def test_numeric_program_runs_in_separate_isolated_process(self):
        original_popen = subprocess.Popen
        launches = []
        def launch(*args, **kwargs):
            launches.append((args, kwargs))
            return original_popen(*args, **kwargs)
        program = [{"op": "load", "name": "speed"}, {"op": "load", "name": "time"},
                   {"op": "mul"}, {"op": "store", "name": "distance"}]
        with mock.patch.dict(os.environ, {"QA_PRIVATE_MARKER": "not-for-worker"}), \
                mock.patch("src.cognition.sandbox.subprocess.Popen", side_effect=launch):
            result = execute_program(program, {"speed": 3, "time": 2})
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["values"]["distance"], 6)
        self.assertEqual(result["steps"], 4)
        self.assertEqual(len(launches), 1)
        command = launches[0][0][0]
        self.assertIn("-I", command)
        self.assertIn("-S", command)
        self.assertNotIn("QA_PRIVATE_MARKER", launches[0][1]["env"])
        self.assertTrue(result["isolation"]["separate_process"])
        self.assertFalse(result["isolation"]["arbitrary_python"])

    def test_arbitrary_code_unknown_instructions_and_non_numeric_values_are_rejected(self):
        invalid = [[{"op": "exec", "code": "open('forbidden','w').write('x')"}],
                   [{"op": "const", "value": True}], [{"op": "const", "value": "text"}],
                   [{"op": "load", "name": "__missing__"}], [{"op": "add"}],
                   [{"op": "const", "value": 1}, {"op": "const", "value": 0}, {"op": "div"}],
                   [{"op": "repeat", "count": True, "body": []}]]
        for program in invalid:
            with self.subTest(program=program):
                result = execute_program(program)
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(result["values"], {})
                self.assertEqual(result["stack"], [])

    def test_step_budget_stops_a_generated_loop_without_returning_partial_values(self):
        result = execute_program([{"op": "repeat", "count": 100000, "body": []}], max_steps=50)
        self.assertEqual(result["status"], "budget_exhausted")
        self.assertEqual(result["steps"], 50)
        self.assertEqual(result["stack"], [])
        self.assertEqual(result["values"], {})

    def test_stack_and_exponent_limits_are_enforced(self):
        stack = execute_program([{"op": "repeat", "count": 1025, "body": [{"op": "const", "value": 1}]}])
        self.assertEqual(stack["status"], "rejected")
        power = execute_program([{"op": "const", "value": 2}, {"op": "const", "value": 1000000}, {"op": "pow"}])
        self.assertEqual(power["status"], "rejected")

    def test_pre_cancelled_program_does_not_start_a_worker(self):
        event = threading.Event()
        event.set()
        with mock.patch("src.cognition.sandbox.subprocess.Popen") as popen:
            result = execute_program([{"op": "const", "value": 1}], cancel_event=event)
        self.assertEqual(result["status"], "cancelled")
        popen.assert_not_called()

    def test_timeout_kills_worker_and_returns_no_result_as_completed(self):
        # The deadline is intentionally shorter than process startup, so the
        # outcome does not depend on CPU throughput of the arithmetic program.
        result = execute_program([{"op": "repeat", "count": 100000, "body": []}], timeout=.000001)
        self.assertEqual(result["status"], "timeout")
        self.assertEqual(result["values"], {})
        self.assertEqual(result["stack"], [])

    def test_invalid_resource_configuration_and_nonfinite_inputs_are_rejected(self):
        for kwargs in ({"timeout": float("nan")}, {"timeout": True}, {"max_steps": 0},
                       {"max_steps": True}, {"memory_mb": 1}, {"memory_mb": True},
                       {"inputs": {"x": float("nan")}}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                execute_program([], **kwargs)


if __name__ == "__main__":
    unittest.main()
