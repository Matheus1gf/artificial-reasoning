"""Independent numeric evidence, proposal rejection and executable composition tests."""
import copy
import math
import threading
import unittest
from unittest.mock import patch

from src.cognition.operators import TransitionNetwork, fit_operator, predict_operator, select_example, synthesize
from src.cognition.sandbox import execute_program


def examples(a,b,xs=(-2,0,2)):
    return [{'x':x,'y':a*x+b,'id':'qa-'+str(x)} for x in xs]


class OperatorTests(unittest.TestCase):
    def test_own_gradient_training_changes_weights_and_predicts_new_inputs(self):
        network=TransitionNetwork(seed=41)
        before=network.artifact()
        trained=network.fit(examples(-2,3),epochs=300)
        self.assertNotEqual(trained['weights'],before['weights'])
        self.assertLess(trained['loss_curve'][-1],trained['loss_curve'][0]*1e-6)
        self.assertEqual(trained['training_ids'],['qa--2','qa-0','qa-2'])
        for x in (-3,-1,1,3):self.assertAlmostEqual(network.predict(x),-2*x+3,places=6)
        self.assertEqual(trained,TransitionNetwork(seed=41).fit(examples(-2,3),epochs=300))
        trained['weights'][0]=99
        self.assertNotEqual(network.artifact()['weights'][0],99)

    def test_version_space_keeps_ambiguity_and_active_observation_identifies_rule(self):
        observed=[{'x':0,'y':2}]
        result=fit_operator(observed,use_neural=False)
        self.assertEqual(result['status'],'ambiguous')
        self.assertEqual(len(result['candidates']),7)
        query=result['next_query'];self.assertNotEqual(query,0)
        self.assertGreater(len({c['a']*query+c['b'] for c in result['candidates']}),1)
        observed.append({'x':query,'y':-2*query+2})
        identified=fit_operator(observed,use_neural=False)
        self.assertEqual(identified['status'],'answered')
        self.assertEqual(predict_operator(identified,3)['predictions'],[-4])
        self.assertTrue(predict_operator(identified,3)['conditional'])
        self.assertEqual(predict_operator(result,0)['predictions'],[2])
        self.assertEqual(predict_operator(result,3)['status'],'ambiguous')

    def test_false_neural_proposal_is_rejected_by_evidence_without_disabling_true_candidate(self):
        def lie(network,*args,**kwargs):
            network.weights=[5,3];network.scale=1
            return network.artifact()
        with patch.object(TransitionNetwork,'fit',lie):
            result=fit_operator(examples(-1,-2))
        self.assertEqual(result['neural_proposal'],{'a':3,'b':5})
        self.assertFalse(result['neural_proposal_verified'])
        self.assertEqual([(c['a'],c['b']) for c in result['candidates']],[(-1,-2)])
        self.assertEqual(result['status'],'answered')

    def test_counterexample_noise_and_budget_do_not_manufacture_identified_operator(self):
        contradictory=[{'x':0,'y':0},{'x':0,'y':1}]
        self.assertEqual(fit_operator(contradictory,use_neural=False)['status'],'unknown')
        noisy=[{'x':0,'y':1.1},{'x':2,'y':5.1}]
        self.assertEqual(fit_operator(noisy,use_neural=False)['status'],'unknown')
        self.assertEqual(fit_operator(noisy,tolerance=.2,use_neural=False)['status'],'answered')
        truncated=fit_operator(examples(2,1),use_neural=False,max_operations=1)
        self.assertEqual(truncated['status'],'budget_exhausted')
        self.assertEqual(truncated['candidates'],[])
        for bad in ([{'x':True,'y':1}],[{'x':21,'y':1}],[{'x':1,'y':math.nan}],[{'x':0,'y':0,'id':'same'},{'x':1,'y':1,'id':'same'}]):
            with self.subTest(bad=bad),self.assertRaises(ValueError):fit_operator(bad)

    def test_new_composition_produces_program_checked_by_isolated_interpreter(self):
        models={'inc':fit_operator(examples(1,1),use_neural=False),'double':fit_operator(examples(2,0),use_neural=False)}
        result=synthesize(1,6,models,max_steps=3)
        self.assertEqual(result['status'],'answered')
        self.assertTrue(result['verification']['passed'])
        self.assertEqual(len(result['plan']),3)
        executed=execute_program(result['program'],{'x':1})
        self.assertEqual(executed['status'],'completed')
        self.assertEqual(executed['values']['x'],6)
        current=1
        for name in result['plan']:current=current+1 if name=='inc' else current*2
        self.assertEqual(current,6)
        self.assertEqual(result['metrics']['cost_actions'],3)
        self.assertTrue(all(row['passed'] for row in result['probes']))

    def test_bad_replay_and_unidentified_operator_never_produce_verified_invention(self):
        models={'inc':fit_operator(examples(1,1),use_neural=False)}
        with patch('src.cognition.operators.execute_program',return_value={'status':'completed','values':{'x':999}}):
            result=synthesize(0,2,models)
        self.assertEqual(result['status'],'unknown')
        self.assertFalse(result['verification']['passed'])
        ambiguous={'inc':fit_operator([{'x':0,'y':1}],use_neural=False)}
        self.assertEqual(synthesize(0,2,ambiguous)['status'],'ambiguous')
        cancelled=threading.Event();cancelled.set()
        self.assertEqual(synthesize(0,2,models,cancel_event=cancelled)['status'],'budget_exhausted')
        self.assertEqual(synthesize(0,2,models,max_operations=1)['status'],'budget_exhausted')

    def test_equivalent_programs_have_same_mechanism_signature_and_limited_scope(self):
        first=synthesize(0,2,{'inc':fit_operator(examples(1,1),use_neural=False)})
        second=synthesize(0,2,{'inc2':fit_operator(examples(1,2),use_neural=False)},known_signatures=[first['signature']])
        self.assertNotEqual(first['plan'],second['plan'])
        self.assertEqual(first['signature'],second['signature'])
        self.assertFalse(second['metrics']['novel_to_memory'])
        self.assertIn('not scientific novelty',second['metrics']['novelty_scope'])
        self.assertTrue(any('conditional' in limit for limit in second['limitations']))

    def test_abstraction_transfer_and_premise_variation_keep_distinct_validity(self):
        models={'inc':fit_operator(examples(1,1),use_neural=False),'double':fit_operator(examples(2,0),use_neural=False)}
        prior=synthesize(1,6,models,max_steps=3)
        transfer=synthesize(2,10,models,max_steps=3,templates=[prior['plan']],alternative_initials=[0,3])
        self.assertEqual(transfer['status'],'answered')
        by_type={row['transformation']:row for row in transfer['candidates']}
        abstract=by_type['symbolic_abstraction']
        result=execute_program(abstract['program'],{'x':2})
        self.assertEqual(result['values']['x'],10)
        self.assertEqual(abstract['same_mechanism_signature'],transfer['signature'])
        self.assertTrue(by_type['structural_analogy_of_stored_program']['meets_original_goal'])
        variations=[row for row in transfer['candidates'] if row['transformation']=='explicit_initial_premise_variation']
        self.assertEqual(len(variations),2)
        self.assertTrue(all(row['hypothesis_only'] and not row['meets_original_goal'] for row in variations))
        self.assertTrue(all(row['original_initial']==2 for row in variations))
        # Canonical mechanism does not change when coefficients come from template ints.
        repeated=synthesize(1,6,models,max_steps=3,templates=[prior['plan']],known_signatures=[prior['signature']])
        self.assertEqual(repeated['signature'],prior['signature'])
        self.assertFalse(repeated['metrics']['novel_to_memory'])

    def test_tampered_stored_coefficients_are_rechecked_against_observations(self):
        model=fit_operator(examples(1,1),use_neural=False)
        model['candidates'][0]['a']=3
        with self.assertRaises(ValueError):predict_operator(model,2)
        with self.assertRaises(ValueError):synthesize(1,4,{'inc':model})


if __name__=='__main__':unittest.main()
