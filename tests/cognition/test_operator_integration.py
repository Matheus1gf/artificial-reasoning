"""Learn, reuse, refute and withdraw conditional operators through real chat turns."""
import json
import threading
import unittest
from unittest.mock import patch

from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.cognition.store import ExperienceStore


class OperatorIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.memory=Memory(':memory:');self.engine=ChatEngine(self.memory)
        self.cid=self.memory.create_conversation()['id']
        self.addCleanup(self.memory.close);self.addCleanup(self.engine.close)

    def ask(self,task,cid=None,**kwargs):
        return self.engine.reply(cid or self.cid,json.dumps(dict(task=task,**kwargs)))

    def learn(self,name,a,b,cid=None):
        return self.ask('learn_operator',cid=cid,name=name,examples=[{'x':0,'y':b},{'x':2,'y':2*a+b}],use_neural=False)

    def records(self,kind):return [r for r in self.engine.experience_store.export()['records'] if r['kind']==kind]

    def test_observations_learn_reusable_conditional_models_and_execute_unseen_composition(self):
        learned=self.learn('inc',1,1);self.learn('double',2,0)
        self.assertEqual(learned['answer_package']['status'],'answered')
        for row in self.records('model'):
            self.assertEqual(row['scope'],'conversation');self.assertEqual(row['status'],'asserted')
            self.assertEqual(row['evidence'],'deduction');self.assertTrue(row['source_ids'])
            self.assertIn('conditional',row['payload']['epistemic_status'])
        self.assertEqual(self.engine.experience_store.db.execute('SELECT count(*) FROM models').fetchone()[0],0)
        predicted=self.ask('apply_operator',name='inc',x=5)
        self.assertEqual(predicted['answer_package']['conclusions'][0]['predictions'],[6])
        invented=self.ask('invent',initial=1,target=6,operators=['inc','double'],max_steps=3)
        self.assertEqual(invented['answer_package']['status'],'answered')
        self.assertEqual(invented['answer_package']['domain'],'learned_invention')
        artifact=invented['answer_package']['calculations'][0]
        self.assertEqual(artifact['execution']['values']['x'],6)
        self.assertTrue(all(v['passed'] for v in invented['answer_package']['verification']))
        self.assertEqual(invented['reasoning']['model_calls'],0)
        procedure=self.records('procedure')[0]
        self.assertTrue({r['id'] for r in self.records('model')} <= set(procedure['source_ids']))
        repeated=self.ask('invent',initial=1,target=6,operators=['inc','double'],max_steps=3)
        self.assertFalse(repeated['answer_package']['calculations'][0]['metrics']['novel_to_memory'])
        self.assertEqual(self.memory.stats()['assertions'],0)

    def test_counterexample_retracts_models_and_programs_and_replay_prevents_relearning_failure(self):
        learned=self.learn('inc',1,1)
        model_id=learned['answer_package']['calculations'][0]['record_id']
        invented=self.ask('invent',initial=0,target=2,operators=['inc'])
        procedure_id=invented['answer_package']['conclusions'][0]['procedure_id']
        result=self.ask('test_operator',name='inc',examples=[{'x':1,'y':8}])
        self.assertEqual(result['answer_package']['status'],'unknown')
        self.assertEqual(self.engine.experience_store.get(model_id)['status'],'retracted')
        self.assertEqual(self.engine.experience_store.get(procedure_id)['status'],'retracted')
        failures=[r for r in self.records('experiment') if r['payload'].get('type')=='operator_counterexample']
        self.assertEqual(len(failures),1)
        self.assertEqual(failures[0]['status'],'asserted')
        self.assertNotIn(model_id,failures[0]['source_ids'])
        repeated=self.learn('inc',1,1)
        self.assertEqual(repeated['answer_package']['status'],'unknown')
        self.assertGreater(repeated['answer_package']['calculations'][0]['replayed_failure_count'],0)
        self.assertEqual(self.ask('apply_operator',name='inc',x=3)['answer_package']['status'],'unknown')
        failed_invention=self.ask('invent',initial=0,target=2,operators=['inc'])
        self.assertEqual(failed_invention['answer_package']['status'],'unknown')
        self.assertEqual(failed_invention['answer_package']['conclusions'],[])
        self.assertIn('refutad',failed_invention['content'].lower())
        self.assertNotIn('possui alternativas',failed_invention['content'].lower())

    def test_operator_evidence_and_failures_are_isolated_by_conversation(self):
        self.learn('inc',1,1)
        other=self.memory.create_conversation()['id']
        missing=self.ask('apply_operator',cid=other,name='inc',x=3)
        self.assertNotEqual(missing['answer_package']['status'],'answered')
        own=self.learn('inc',1,5,cid=other)
        self.assertEqual(own['answer_package']['status'],'answered')
        self.ask('test_operator',name='inc',examples=[{'x':1,'y':8}])
        unaffected=self.ask('apply_operator',cid=other,name='inc',x=3)
        self.assertEqual(unaffected['answer_package']['conclusions'][0]['predictions'],[8])

    def test_failed_budget_after_counterexample_withdraws_obsolete_model(self):
        learned=self.learn('inc',1,1)
        model_id=learned['answer_package']['calculations'][0]['record_id']
        result=self.ask('test_operator',name='inc',examples=[{'x':1,'y':8}],max_operations=1)
        self.assertEqual(result['answer_package']['status'],'budget_exhausted')
        self.assertEqual(self.engine.experience_store.get(model_id)['status'],'retracted')
        retry=self.learn('inc',1,1)
        self.assertEqual(retry['answer_package']['status'],'unknown')

    def test_retry_after_core_cancellation_preserves_exact_learned_version(self):
        flag=threading.Event();original=self.engine.core.solve
        request=json.dumps({'task':'learn_operator','name':'inc','examples':[{'x':0,'y':1},{'x':2,'y':3}],'use_neural':False})
        def finish_then_cancel(*args):
            package=original(*args);flag.set();return package
        with patch.object(self.engine.core,'solve',side_effect=finish_then_cancel):
            with self.assertRaises(ValueError):self.engine.reply(self.cid,request,'same-learning-turn',cancel_event=flag)
        versions=self.records('model')
        self.assertEqual(len(versions),1)
        flag.clear()
        self.engine.reply(self.cid,request,'same-learning-turn',cancel_event=flag)
        self.assertEqual(self.records('model'),versions)

    def test_failure_saving_approved_package_does_not_repeat_sidecar_effects_on_retry(self):
        original=self.memory.transaction;calls=[]
        request=json.dumps({'task':'learn_operator','name':'inc','examples':[{'x':0,'y':1},{'x':2,'y':3}],'use_neural':False})
        def transaction():
            calls.append(True)
            if len(calls)==2:raise RuntimeError('simulated write failure after sidecar effect')
            return original()
        with patch.object(self.memory,'transaction',side_effect=transaction):
            with self.assertRaises(RuntimeError):self.engine.reply(self.cid,request,'save-failure')
        versions=self.records('model')
        self.assertEqual(len(versions),1)
        self.engine.reply(self.cid,request,'save-failure')
        self.assertEqual(self.records('model'),versions)

    def test_resumed_package_cannot_assert_model_withdrawn_during_interruption(self):
        self.learn('inc',1,1)
        flag=threading.Event();original=self.engine.core.solve
        request=json.dumps({'task':'invent','initial':0,'target':2,'operators':['inc']})
        def finish_then_cancel(*args):
            package=original(*args);flag.set();return package
        with patch.object(self.engine.core,'solve',side_effect=finish_then_cancel):
            with self.assertRaises(ValueError):self.engine.reply(self.cid,request,'withdraw-pending',cancel_event=flag)
        flag.clear()
        self.ask('test_operator',name='inc',examples=[{'x':1,'y':8}])
        result=self.engine.reply(self.cid,request,'withdraw-pending',cancel_event=flag)
        self.assertNotEqual(result['answer_package']['status'],'answered')
        self.assertEqual(result['answer_package']['conclusions'],[])

    def test_learning_and_synthesis_run_outside_sidecar_transaction(self):
        from src.cognition import operator_runtime
        actual_fit=operator_runtime.fit_operator;actual_synthesize=operator_runtime.synthesize
        calls=[]
        def fit(*args,**kwargs):
            self.assertFalse(self.engine.experience_store.db.in_transaction)
            calls.append('fit');return actual_fit(*args,**kwargs)
        def synthesize(*args,**kwargs):
            self.assertFalse(self.engine.experience_store.db.in_transaction)
            calls.append('synthesize');return actual_synthesize(*args,**kwargs)
        with patch.object(operator_runtime,'fit_operator',side_effect=fit),patch.object(operator_runtime,'synthesize',side_effect=synthesize):
            self.learn('inc',1,1)
            result=self.ask('invent',initial=0,target=2,operators=['inc'])
        self.assertEqual(calls,['fit','synthesize'])
        self.assertEqual(result['answer_package']['status'],'answered')

    def test_sidecar_cache_write_failure_rolls_back_model_and_retry_creates_one_version(self):
        original=self.engine.experience_store.record
        request=json.dumps({'task':'learn_operator','name':'inc','examples':[{'x':0,'y':1},{'x':2,'y':3}],'use_neural':False})
        def record(cid,kind,payload,*args,**kwargs):
            if payload.get('type')=='operator_answer':raise RuntimeError('simulated cache write failure')
            return original(cid,kind,payload,*args,**kwargs)
        with patch.object(self.engine.experience_store,'record',side_effect=record):
            with self.assertRaises(RuntimeError):self.engine.reply(self.cid,request,'cache-write')
        self.assertEqual(self.records('model'),[])
        self.engine.reply(self.cid,request,'cache-write')
        self.assertEqual(len(self.records('model')),1)
        self.assertEqual(self.records('model')[0]['version'],1)


if __name__=='__main__':unittest.main()
