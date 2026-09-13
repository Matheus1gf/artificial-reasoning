"""Measured trajectory transfer: chronological evidence, controls and rejection gates."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.science import motion_transfer as motion, resolve


class MotionTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.protocol=json.loads(motion.PROTOCOL.read_text())
        cls.rows,cls.metadata=motion.load_trajectory()

    def test_primary_measured_bytes_units_and_source_uncertainty_are_explicit(self):
        raw=motion.METADATA.parent/self.metadata['raw_filename']
        self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(),self.metadata['sha256'])
        self.assertEqual(len(raw.read_bytes()),self.metadata['upstream_bytes'])
        self.assertEqual(self.metadata['dataset_kind'],'measured')
        self.assertEqual(self.metadata['license'],'CC BY 4.0')
        self.assertIn('cvg.cit.tum.de',self.metadata['source_url'])
        self.assertEqual(self.metadata['units']['x'],'m')
        self.assertTrue(all(b['timestamp']>a['timestamp'] for a,b in zip(self.rows,self.rows[1:])))
        self.assertIsNone(self.metadata['uncertainty']['per_sample_covariance'])
        self.assertIsNone(self.metadata['uncertainty']['time_uncertainty_s'])
        with tempfile.TemporaryDirectory() as folder:
            copied=Path(folder)/'metadata.json';copied.write_text(json.dumps(self.metadata))
            (Path(folder)/self.metadata['raw_filename']).write_bytes(raw.read_bytes()+b'\n')
            with patch.object(motion,'METADATA',copied),self.assertRaisesRegex(ValueError,'checksum'):
                motion.load_trajectory()

    def test_future_measurements_never_change_training_or_predictions(self):
        window=motion.sample_window(self.rows,0,self.protocol)
        training=[{'t':r['t'],'x':r['x']} for r in window[:10]]
        future=[{'t':r['t'],'x':r['x']} for r in window[10:]]
        first=motion.compare_segment(training,future,self.protocol)
        changed=[dict(r,x=r['x']+3) for r in future]
        second=motion.compare_segment(training,changed,self.protocol)
        for name in self.protocol['models']:
            self.assertEqual(first['models'][name]['predictions'],second['models'][name]['predictions'])
            self.assertNotEqual(first['models'][name]['rmse_m'],second['models'][name]['rmse_m'])
            if 'parameters' in first['models'][name]:
                self.assertEqual(first['models'][name]['parameters'],second['models'][name]['parameters'])
        self.assertLess(training[-1]['t'],future[0]['t'])
        modified=copy.deepcopy(self.rows)
        for row in modified:row['x']+=1000
        selected=motion.sample_window(modified,0,self.protocol)
        self.assertEqual([r['source_line'] for r in selected],[r['source_line'] for r in window])

    def test_influence_weights_reproduce_polynomials_but_do_not_claim_full_uncertainty(self):
        times=[i/10 for i in range(10)];target=1.7
        for degree in (1,2):
            weights=motion.prediction_weights(times,target,degree)
            self.assertAlmostEqual(sum(weights),1,places=10)
            for power in range(degree+1):
                self.assertAlmostEqual(sum(w*t**power for w,t in zip(weights,times)),target**power,places=10)
        self.assertIn('conditional',self.protocol['uncertainty_sensitivity'])
        self.assertIn('time jitter',self.protocol['uncertainty_sensitivity'])

    def test_outside_domain_is_reported_without_clipping_or_dropping_baseline(self):
        training=[{'t':i/10,'x':100+i/10} for i in range(10)]
        future=[{'t':i/10,'x':100+i/10} for i in range(10,20)]
        result=motion.compare_segment(training,future,self.protocol)
        for name in ('constant_acceleration_midpoint','constant_velocity_midpoint'):
            self.assertEqual(result['models'][name]['status'],'outside_simulator_domain')
            self.assertEqual(result['models'][name]['predictions'],[])
            self.assertGreater(result['models'][name]['parameters']['x0'],99)
        self.assertEqual(result['models']['last_observation']['status'],'evaluated')
        with self.assertRaises(ValueError):motion.compare_segment(training,list(reversed(future)),self.protocol)

    def test_registered_transfer_preserves_negative_outcome_and_independent_controls(self):
        with patch('socket.create_connection',side_effect=AssertionError('network')):
            report=motion.evaluate()
        self.assertEqual(len(report['segments']),24)
        self.assertEqual(report['expected_segments'],24)
        self.assertEqual(report['sampling_failures'],[])
        self.assertFalse(report['transfer_promoted'])
        self.assertFalse(report['larger_problem_transfer_authorized'])
        self.assertFalse(report['new_physical_law'])
        self.assertEqual(report['language_model_calls'],0)
        self.assertTrue(report['negative_results'])
        self.assertIn('correlated',' '.join(report['limitations']))
        primary=report['summary']['constant_acceleration_midpoint']
        self.assertEqual(primary['evaluated_future_positions'],240)
        self.assertGreater(primary['pooled_rmse_m'],report['summary']['last_observation']['pooled_rmse_m'])
        for segment in report['segments']:
            result=segment['models']['constant_acceleration_midpoint']
            self.assertLess(result['synthetic_control_max_integrator_error_m'],1e-10)
            self.assertEqual(len(result['conditional_position_error_budget_m']),10)

    def test_real_chat_reports_failed_transfer_as_result_not_a_new_physical_law(self):
        memory=Memory(':memory:');engine=ChatEngine(memory)
        try:
            cid=memory.create_conversation()['id']
            result=engine.reply(cid,json.dumps({'domain':'physics','operation':'measured_transfer'}))
            package=result['answer_package']
            self.assertEqual(package['status'],'answered')
            raw=package['calculations'][0]['result']
            self.assertIn('constant_acceleration_transfer_rejected',json.dumps(raw))
            self.assertIn('cvg.cit.tum.de',json.dumps(package['sources']))
            self.assertEqual(result['reasoning']['model_calls'],0)
            self.assertEqual(memory.messages(cid)[-1]['metadata']['answer_package'],package)
        finally:engine.close();memory.close()
        rejected=resolve({'domain':'physics','operation':'measured_transfer','parameters':{'threshold':999}})
        self.assertEqual(rejected['status'],'invalid')


if __name__=='__main__':unittest.main()
