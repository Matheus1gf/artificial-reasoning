"""Audit committed adaptation, active-query and invention evidence independently."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import unittest


class OperatorExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root=Path(__file__).resolve().parents[2]
        paths=list((cls.root/'experiments/cognition').glob('operators-pilot.v*/results.json'))
        if not paths:raise AssertionError('Operator experiment results are required')
        latest=max(paths,key=lambda p:int(p.parent.name.rsplit('.v',1)[1]))
        cls.directory=latest.parent
        cls.report=json.loads(latest.read_text())
        cls.protocol=json.loads((latest.parent/'protocol.json').read_text())
        cls.registration=json.loads((latest.parent/'registration.json').read_text())

    def test_registered_design_covers_all_conditions_without_hidden_pretraining_or_overlap(self):
        report,protocol=self.report,self.protocol
        self.assertEqual(hashlib.sha256((self.directory/'protocol.json').read_bytes()).hexdigest(),self.registration['protocol_sha256'])
        self.assertIs(self.registration['started_scoring'],False)
        expected={(family,tuple(function),seed,n,sigma) for family,functions in protocol['functions'].items() for function in functions for seed in protocol['seeds'] for n in protocol['examples'] for sigma in protocol['noise_sigma']}
        actual={(row['family'],tuple(row['function']),row['seed'],row['examples'],row['noise_sigma']) for row in report['adaptation']}
        self.assertEqual(actual,expected)
        self.assertEqual(len(report['adaptation']),len(expected))
        for row in report['adaptation']:
            self.assertEqual(len(row['training']),row['examples'])
            self.assertFalse({r['x'] for r in row['training']} & set(row['held_out']['x']))
            for degree in (1,2):
                result=row['comparators']['neuron_degree_'+str(degree)]
                self.assertEqual(result['prior_training_samples'],0)
                self.assertEqual(result['artifact']['training_ids'],[r['id'] for r in row['training']])
                self.assertEqual(len(result['artifact']['loss_curve']),protocol['network']['epochs'])
                self.assertEqual(result['artifact']['seed'],row['seed'])
        self.assertEqual(report['qwen_calls'],0)
        self.assertEqual(report['network_calls'],0)

    def test_saved_weights_and_targets_reproduce_mse_for_every_network_trial(self):
        for row in self.report['adaptation']:
            a,b=row['function'];xs=row['held_out']['x'];ys=row['held_out']['y']
            expected=[a*(x if row['family']=='affine' else x*x if row['family']=='quadratic' else abs(x))+b for x in xs]
            self.assertEqual(ys,expected)
            for degree in (1,2):
                result=row['comparators']['neuron_degree_'+str(degree)];artifact=result['artifact']
                predicted=[sum(w*(x/artifact['scale'])**i for i,w in enumerate(artifact['weights'])) for x in xs]
                mse=sum((y-p)**2 for y,p in zip(ys,predicted))/len(ys)
                self.assertAlmostEqual(result['mse'],mse,places=10)
        # Representation supplied by the developer, not a claimed learned abstraction.
        self.assertIn('supplied degree-2 basis',self.protocol['decision_rules']['representations'])

    def test_active_queries_use_equal_observations_and_keep_tied_negative_result(self):
        grouped={}
        for row in self.report['active_selection']:
            grouped.setdefault((row['seed'],row['a'],row['b']),{})[row['strategy']]=row
        self.assertEqual(len(grouped),3*7*11)
        for rows in grouped.values():
            self.assertEqual(set(rows),{'active','random','smallest'})
            self.assertEqual(len({r['before'] for r in rows.values()}),1)
            self.assertEqual({r['after'] for r in rows.values()},{1})
            self.assertEqual(len({r['reduction'] for r in rows.values()}),1)
        self.assertEqual(self.protocol['active_query']['queries'],1)

    def test_ablation_outcomes_and_chat_workflow_support_only_conditional_local_invention(self):
        by_condition={}
        for row in self.report['invention']['runs']:
            by_condition.setdefault(row['condition'],[]).append(row)
        self.assertEqual(set(by_condition),{'full','without_memory','without_neural','without_search'})
        self.assertTrue(all(len(rows)==6 for rows in by_condition.values()))
        self.assertTrue(all(r['success'] for r in by_condition['full']))
        self.assertTrue(all(r['success'] for r in by_condition['without_neural']))
        self.assertFalse(any(r['success'] for r in by_condition['without_memory']))
        self.assertFalse(any(r['success'] for r in by_condition['without_search']))
        faults=self.report['invention']['verifier_fault_injection']
        self.assertEqual(len(faults),6)
        self.assertTrue(all(r['without_verifier_approved'] and not r['with_verifier_approved'] for r in faults))
        workflow=self.report['chat_workflow']
        self.assertEqual(len(workflow['runs']),9)
        self.assertTrue(all(workflow['checks'].values()))
        self.assertTrue(all(row['model_calls']==0 for row in workflow['runs']))
        self.assertIn('not a measured natural error rate',self.protocol['ablations']['verifier'])


if __name__=='__main__':unittest.main()
