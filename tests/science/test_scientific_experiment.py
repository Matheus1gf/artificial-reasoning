"""Reproduce public pilots offline and retain negative criteria without using reserved seeds."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from src.science import evaluation


class ScientificExperimentTests(unittest.TestCase):
    def test_public_pilot_is_offline_complete_and_preserves_failed_preregistered_gate(self):
        with patch('socket.create_connection',side_effect=AssertionError('network forbidden')):
            report=evaluation.evaluate()
        self.assertFalse(report['reserved_scored'])
        self.assertEqual(report['language_model_calls'],0)
        self.assertEqual(len(report['physics']['seeds']),5)
        self.assertEqual(len(report['quantum']['seeds']),5)
        discovery=report['discovery']
        self.assertEqual(discovery['train_rows'],24);self.assertEqual(discovery['evaluation_rows'],12)
        self.assertFalse(discovery['physical_interpretation_approved'])
        self.assertTrue(discovery['open_problem_gate'].startswith('closed:'))
        self.assertTrue(any('ordinary least squares' in item['check'] for item in discovery['failures']))
        self.assertGreater(discovery['rmse'],discovery['ordinary_least_squares_rmse']+1e-8)
        root=Path(__file__).resolve().parents[2]
        for name,digest in report['code_hashes'].items():
            self.assertEqual(hashlib.sha256((root/name).read_bytes()).hexdigest(),digest)
        json.dumps(report,allow_nan=False)

    def test_registration_cli_does_not_score_and_existing_file_is_untouched(self):
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix='ar-science-qa-') as folder:
            output=Path(folder)/'registration.json'
            command=[sys.executable,str(root/'scripts/evaluate_science.py'),'--register','--output',str(output)]
            process=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=5)
            self.assertEqual(process.returncode,0,process.stderr)
            registered=json.loads(output.read_text())
            self.assertFalse(registered['scored']);self.assertTrue(registered['code_hashes'])
            self.assertNotIn('physics',registered)
            original=output.read_bytes()
            repeat=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=5)
            self.assertNotEqual(repeat.returncode,0)
            self.assertEqual(output.read_bytes(),original)


if __name__=='__main__':unittest.main()
