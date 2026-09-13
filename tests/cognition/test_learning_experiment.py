"""Reproduce registered learning-control study through CLI in temporary storage."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

try:
    import resource
except ImportError:
    resource = None


class LearningExperimentTests(unittest.TestCase):
    def test_registered_cli_reports_all_conditions_and_measured_retention(self):
        root=Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory(prefix='ar-learning-qa-') as folder:
            output=Path(folder)/'new';command=[sys.executable,str(root/'scripts/evaluate_learning.py'),'--output',str(output)]
            process=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=30)
            self.assertEqual(process.returncode,0,process.stderr)
            report=json.loads((output/'report.json').read_text()); registration=json.loads((output/'registration.json').read_text())
            if resource is None:
                self.assertIsNone(report['peak_rss_native'])
                self.assertIsNone(report['rss_unit'])
            else:
                self.assertGreater(report['peak_rss_native'],0)
                self.assertEqual(report['rss_unit'],'bytes' if sys.platform=='darwin' else 'KiB')
            self.assertTrue(all(report['decisions'].values()))
            self.assertEqual(len(report['results']),15)
            for path,digest in registration['sha256'].items():self.assertEqual(hashlib.sha256((root/path).read_bytes()).hexdigest(),digest)
            for row in report['results']:
                self.assertEqual(row['dependent_weight_versions_remaining'],0)
                self.assertTrue(row['rollback_exact']);self.assertTrue(row['backup_restore_equal'])
                self.assertTrue(row['withdrawal_disabled_active'])
                self.assertEqual(row['adopted_old_task_mse'],0)
                if row['condition']=='new-task-only':
                    self.assertNotEqual(row['second_task']['status'],'adopted')
                else:
                    self.assertEqual(row['second_task']['status'],'adopted')
                    self.assertEqual(row['adopted_new_task_mse'],0)
            old=(output/'report.json').read_bytes()
            repeat=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=5)
            self.assertNotEqual(repeat.returncode,0)
            self.assertEqual((output/'report.json').read_bytes(),old)


if __name__=='__main__':unittest.main()
