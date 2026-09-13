"""Vertical tests: own processing, verified packets, persistent learning and arranger isolation."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.chat.provider import LanguageModel, ProviderError, Settings
from src.chat.runtime import start_local_runtime
from src.cognition.contracts import AnswerPackage
from src.cognition.engine import CognitiveCore
from src.cognition.processor import process_message


class CoreIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.memory = Memory(':memory:')
        self.cid = self.memory.create_conversation()['id']
        self.engine = ChatEngine(self.memory)
        self.addCleanup(self.memory.close)
        self.addCleanup(self.engine.close)

    def test_default_research_path_never_uses_extraction_chat_network_or_runtime(self):
        self.engine.settings = Settings(provider='ollama',model='configured',research_mode=True)
        with patch('src.chat.provider.request.build_opener', side_effect=AssertionError('network')), patch.object(self.engine.language_model,'complete',side_effect=AssertionError('model')), patch.object(self.engine.language_model,'chat',side_effect=AssertionError('general chat')), patch('src.chat.runtime.subprocess.Popen') as spawn:
            result = self.engine.reply(self.cid, 'Neral emite luz.')
            calculated = self.engine.reply(self.cid, 'Calcule 2 m + 30 cm.')
            self.assertIsNone(start_local_runtime(self.engine.settings))
            spawn.assert_not_called()
        self.assertEqual(result['reasoning']['model_calls'],0)
        self.assertEqual(calculated['answer_package']['status'],'answered')
        self.assertEqual(calculated['answer_package']['calculations'][0]['value'],2.3)

    def test_legacy_settings_default_to_research_and_disable_all_provider_entrypoints(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/'settings.json'; path.write_text(json.dumps({'provider':'ollama','model':'legacy-model'}))
            settings = Settings.load(path)
        self.assertTrue(settings.research_mode)
        lm = LanguageModel(settings)
        with patch('src.chat.provider.request.build_opener') as opener:
            with self.assertRaises(ProviderError): lm.complete('instruction',{})
            with self.assertRaises(ProviderError): lm.chat('message',[],{})
            opener.assert_not_called()

    def test_packet_exists_before_arranger_and_core_does_not_hold_memory_transaction(self):
        events=[]
        core = self.engine.core
        class CheckedCore:
            def solve(inner, problem, context):
                self.assertFalse(self.memory.db.in_transaction)
                acquired=[]
                def lock_probe():
                    with self.memory.lock: acquired.append(True)
                worker=threading.Thread(target=lock_probe); worker.start(); worker.join(timeout=1)
                self.assertEqual(acquired,[True])
                package=core.solve(problem,context); events.append(('packet',package.digest)); return package
        class Arranger:
            enabled=True
            def complete(inner,system,payload,schema):
                self.assertEqual(events,[('packet',payload['package_sha256'])])
                self.assertEqual(set(payload),{'package_sha256','sentences'})
                events.append(('arranger',True))
                return {'order':[s['id'] for s in payload['sentences']]}
            def chat(inner,*args): raise AssertionError('general chat')
        self.engine.core=CheckedCore(); self.engine.language_model=Arranger()
        self.engine.settings=Settings(provider='ollama',model='qa',research_mode=False)
        result=self.engine.reply(self.cid,'Calcule 3 * 7.')
        self.assertEqual(result['answer_package']['conclusions'][0]['value'],21)
        self.assertEqual(result['reasoning']['model_calls'],1)
        self.assertEqual(events[-1],('arranger',True))

    def test_json_deduction_plan_and_science_are_solved_through_real_chat_pipeline(self):
        tasks=[({'task':'calculate','expression':'7*8'},'arithmetic',56),
               ({'domain':'physics','operation':'simulate','parameters':{'x':1,'v':2,'a':1,'dt':1}},'physics',None),
               ({'task':'plan','initial':{'ready':False,'done':False},'goal':{'done':True},'actions':[{'name':'prepare','preconditions':{'ready':False},'effects':{'ready':True}}, {'name':'finish','preconditions':{'ready':True},'effects':{'done':True}}]},'planning',None)]
        for request,domain,value in tasks:
            with self.subTest(domain=domain):
                result=self.engine.reply(self.cid,json.dumps(request))
                package=AnswerPackage.from_dict(result['answer_package'])
                self.assertEqual(package.status,'answered')
                self.assertEqual(package.domain,domain)
                self.assertTrue(all(c['passed'] for c in package.verification))
                self.assertEqual(result['reasoning']['model_calls'],0)
                self.assertTrue(result['experience_ids'])
        self.assertEqual(self.memory.stats()['assertions'],0)

    def test_failed_core_retains_resumable_episode_without_reapplying_correction(self):
        self.engine.reply(self.cid,'Neral emite luz.')
        actual=self.engine.core
        with patch.object(self.engine.core,'solve',side_effect=RuntimeError('solver failed')):
            with self.assertRaises(RuntimeError): self.engine.reply(self.cid,'Corrigindo: Neral não emite luz.','resume')
        messages=self.memory.messages(self.cid)
        self.assertEqual(len(messages),3)
        self.assertEqual(messages[-1]['role'],'user')
        claims=self.memory.claims()
        episodes=len(self.engine.experience_store.export()['records'])
        result=self.engine.reply(self.cid,'Corrigindo: Neral não emite luz.','resume')
        self.assertIn('não emite luz',result['content'])
        self.assertEqual(self.memory.claims(),claims)
        self.assertEqual(len(self.engine.experience_store.export()['records']),episodes)
        self.assertEqual(len(self.memory.messages(self.cid)),4)

    def test_cancellation_before_processing_has_no_effect_and_after_core_can_resume(self):
        cancelled=threading.Event(); cancelled.set()
        with self.assertRaises(ValueError): self.engine.reply(self.cid,'Neral emite luz.',cancel_event=cancelled)
        self.assertEqual(self.memory.messages(self.cid),[])
        cancelled.clear(); original=self.engine.core.solve
        def finish_then_cancel(*args):
            package=original(*args); cancelled.set(); return package
        with patch.object(self.engine.core,'solve',side_effect=finish_then_cancel):
            with self.assertRaises(ValueError): self.engine.reply(self.cid,'Neral emite luz.','cancelled-turn',cancel_event=cancelled)
        self.assertEqual(len(self.memory.messages(self.cid)),1)
        cancelled.clear()
        result=self.engine.reply(self.cid,'Neral emite luz.','cancelled-turn',cancel_event=cancelled)
        self.assertEqual(result['answer_package']['status'],'answered')
        self.assertEqual(len(self.memory.messages(self.cid)),2)

    def test_resuming_saved_memory_package_rechecks_legacy_claims_after_correction(self):
        self.engine.reply(self.cid,'Neral emite luz.')
        flag=threading.Event();original=self.engine.core.solve
        def finish_then_cancel(*args):
            package=original(*args);flag.set();return package
        with patch.object(self.engine.core,'solve',side_effect=finish_then_cancel):
            with self.assertRaises(ValueError):
                self.engine.reply(self.cid,'O que sabe sobre Neral?','pending-memory',cancel_event=flag)
        flag.clear()
        self.engine.reply(self.cid,'Corrigindo: Neral não emite luz.')
        result=self.engine.reply(self.cid,'O que sabe sobre Neral?','pending-memory',cancel_event=flag)
        self.assertFalse(any(c.get('text')=='neral emite luz' for c in result['answer_package']['conclusions']))
        self.assertTrue(result['answer_package']['status']!='answered' or 'não emite luz' in result['content'])

    def test_memory_proof_replay_uses_roles_independently_of_premise_insertion_order(self):
        for statements in (("Todo metal conduz eletricidade.","Cobre é metal."),("Cobre é metal.","Todo metal conduz eletricidade.")):
            with self.subTest(statements=statements):
                memory=Memory(":memory:");engine=ChatEngine(memory)
                try:
                    cid=memory.create_conversation()["id"]
                    for statement in statements: engine.reply(cid,statement)
                    result=engine.reply(cid,"O que sabe sobre cobre?")
                    self.assertIn("cobre conduz eletricidade",result["content"])
                    self.assertTrue(any(c.get("status")=="deduced" for c in result["answer_package"]["conclusions"]))
                finally:engine.close();memory.close()

    def test_scientific_provenance_is_in_canonical_package_sources(self):
        result=self.engine.reply(self.cid,json.dumps({"domain":"discovery","operation":"calibration"}))
        self.assertEqual(result["answer_package"]["status"],"answered")
        self.assertIn("nist.gov",json.dumps(result["answer_package"]["sources"]))
        self.assertTrue(result["answer_package"]["premises"])
        self.assertTrue(result["answer_package"]["limitations"])

    def test_quantum_ambiguity_and_observed_context_study_survive_real_chat_contract(self):
        ambiguous={"domain":"quantum","operation":"fit","parameters":{"observations":[{"t":0,"shots":100,"zeros":100}],"candidates":[.2,.8,1.4]}}
        result=self.engine.reply(self.cid,json.dumps(ambiguous))
        self.assertEqual(result["answer_package"]["status"],"unknown")
        self.assertEqual(result["answer_package"]["conclusions"],[])
        observed=self.engine.reply(self.cid,json.dumps({"domain":"quantum","operation":"contextual_study"}))
        self.assertEqual(observed["answer_package"]["status"],"answered")
        self.assertIn("QuestOrdEff.pdf",json.dumps(observed["answer_package"]["sources"]))
        self.assertEqual(observed["reasoning"]["model_calls"],0)
        self.assertIn("observed_human_aggregate",json.dumps(observed["answer_package"]["calculations"]))
        self.assertEqual(self.memory.messages(self.cid)[-1]["metadata"]["answer_package"],observed["answer_package"])

    def test_scientific_failed_verification_never_becomes_answered(self):
        core=CognitiveCore(domain_services=lambda _: {'status':'answered','sentences':['A hipótese é verdadeira.'],'conclusions':['A'],'verification':{'passed':False}})
        problem=process_message(json.dumps({'domain':'physics','operation':'simulate','parameters':{}}))
        package=core.solve(problem)
        self.assertEqual(package.status,'unknown')
        self.assertEqual(package.conclusions,[])
        self.assertNotIn('A hipótese é verdadeira.',package.render())

    def test_own_trained_intent_proposal_is_persisted_without_semantic_authority(self):
        from src.cognition.neural import local_intent
        message='Calcule 13 + 4.'
        expected=local_intent(message)
        self.assertIsNotNone(expected)
        result=self.engine.reply(self.cid,message,'own-intent')
        proposal=result['problem']['payload']['neural_proposal']
        self.assertEqual(proposal['intent'],expected['intent'])
        self.assertEqual(proposal['probabilities'],expected['probabilities'])
        self.assertIs(proposal['adopted'],False)
        self.assertEqual(result['answer_package']['calculations'][0]['value'],17)
        self.assertEqual(self.memory.messages(self.cid)[-1]['metadata']['problem'],result['problem'])
        # A confident, wrong prediction cannot redefine the question or add facts.
        with patch('src.cognition.neural.local_intent',return_value={'intent':'statement','probability':1.0,'version':'adversarial-qa'}):
            changed=self.engine.reply(self.cid,'Calcule 19 + 2.')
        self.assertEqual(changed['problem']['intent'],'calculation')
        self.assertEqual(changed['problem']['facts'],[])
        self.assertIs(changed['problem']['payload']['neural_proposal']['adopted'],False)
        self.assertEqual(changed['answer_package']['calculations'][0]['value'],21)
        self.assertEqual(self.memory.stats()['assertions'],0)
        self.assertEqual(changed['reasoning']['model_calls'],0)

    def test_unavailable_intent_checkpoint_does_not_break_own_comprehension(self):
        with patch('src.cognition.neural.local_intent',side_effect=ValueError('invalid weights')):
            result=self.engine.reply(self.cid,'Calcule 5 * 9.')
        self.assertEqual(result['problem']['payload']['neural_proposal'],{'adopted':False,'status':'checkpoint_unavailable'})
        self.assertEqual(result['answer_package']['calculations'][0]['value'],45)
        self.assertEqual(result['reasoning']['model_calls'],0)

    def test_chat_resource_measurements_are_persisted_and_cache_does_not_remeasure(self):
        result=self.engine.reply(self.cid,'Calcule 14 * 3.','qa-resources')
        resources=result['reasoning']['resources']
        for name in ('wall_seconds','cpu_seconds'):
            self.assertGreaterEqual(resources[name],0)
        self.assertIs(resources['verified_solution'],True)
        self.assertEqual(resources['wall_seconds_per_verified_solution'],resources['wall_seconds'])
        self.assertIsNone(resources['monetary_cost'])
        self.assertIn('process lifetime',resources['memory_scope'])
        self.assertIn('before final persistence',resources['measurement_scope'])
        self.assertTrue(resources['process_peak_rss_bytes'] is None or resources['process_peak_rss_bytes']>0)
        persisted=self.memory.messages(self.cid)[-1]['metadata']['reasoning']['resources']
        self.assertEqual(persisted,resources)
        with patch('src.chat.engine.finish_measurement',side_effect=AssertionError('cached result remeasured')):
            cached=self.engine.reply(self.cid,'Calcule 14 * 3.','qa-resources')
        self.assertEqual(cached['reasoning']['resources'],resources)
        unknown=self.engine.reply(self.cid,'O que é um buraco de minhoca?')
        self.assertEqual(unknown['answer_package']['status'],'unknown')
        self.assertIs(unknown['reasoning']['resources']['verified_solution'],False)
        self.assertIsNone(unknown['reasoning']['resources']['wall_seconds_per_verified_solution'])


if __name__=='__main__': unittest.main()
