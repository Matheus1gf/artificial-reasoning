"""Natural multi-turn reasoning: target, reference, conditional assumptions and provenance."""
import json
import unittest
from dataclasses import asdict, replace
from unittest.mock import patch

from src.chat.domain import Assertion, Proposal, normalize
from src.chat.engine import ChatEngine
from src.chat.memory import Memory
from src.chat.provider import Settings
from src.chat.reasoner import verify_hypothesis


class ConceptualReasoningTests(unittest.TestCase):
    def setUp(self):
        self.memory=Memory(':memory:');self.engine=ChatEngine(self.memory,Settings(research_mode=True))
        self.cid=self.memory.create_conversation()['id']
        self.addCleanup(self.memory.close);self.addCleanup(self.engine.close)

    def ask(self,text,cid=None):
        with patch.object(self.engine.language_model,'complete',side_effect=AssertionError('Qwen is forbidden')):
            result=self.engine.reply(cid or self.cid,text)
        self.assertEqual(result['reasoning']['model_calls'],0)
        return result

    def triples(self,origin=None):
        return {(r['subject'],r['predicate'],r['object'],r['polarity']) for r in self.memory.claims()
                if origin is None or r['origin']==origin}

    def assert_hypothesis(self,result,subject,relation,obj):
        expected=normalize(subject+' '+relation+' '+obj)
        hypotheses=result['answer_package']['hypotheses']
        matching=[h for h in hypotheses if expected in normalize(json.dumps(h,ensure_ascii=False))]
        self.assertTrue(matching,(expected,result['content'],hypotheses))
        for hypothesis in matching:
            self.assertTrue(hypothesis.get('method') or hypothesis.get('transformation'),hypothesis)
            self.assertTrue(hypothesis.get('test') or hypothesis.get('validation'),hypothesis)
            self.assertTrue(hypothesis.get('premise_ids') or hypothesis.get('premises'),hypothesis)
        self.assertTrue(any(marker in normalize(result['content']) for marker in ('hipotese','condicional','supondo','oposicao')))

    def test_relative_definition_decomposes_types_functions_and_conjunctions(self):
        message='Um buraco negro é uma região do espaço que absorve matéria e luz devido à sua gravidade.'
        result=self.ask(message)
        expected={('buraco negro','é','regiao do espaco',True),('buraco negro','absorve','materia',True),('buraco negro','absorve','luz',True)}
        self.assertTrue(expected <= self.triples('user'),self.triples('user'))
        for claim in result['learned']:
            self.assertTrue(all(source['quote'] in message for source in claim['sources']))
        self.assertFalse(any(r['predicate']=='causa' for r in self.memory.claims()))

    def test_literal_reported_conversation_keeps_target_and_temporary_assumption(self):
        first=self.ask('o que é um buraco negro?')
        self.assertEqual(first['answer_package']['status'],'unknown')
        learned=self.ask('buraco negro é um corpo celeste que absorve matéria e luz por causa da sua infinita gravidade.')
        with self.subTest(step='relative definition'):
            self.assertTrue({('buraco negro','é','corpo celeste',True),('buraco negro','absorve','materia',True),('buraco negro','absorve','luz',True)} <= self.triples('user'))
        without_relation=self.ask('considerando um buraco negro, o que seria um buraco branco?')
        with self.subTest(step='new target before explicit relation'):
            self.assertEqual(without_relation['focus'],'buraco branco')
            self.assertIn('buraco branco',normalize(without_relation['content']))
            self.assertFalse(any('buraco branco' in normalize(c.get('text','')) and c.get('status') in ('asserted','deduced') for c in without_relation['answer_package']['conclusions']))
        before=self.triples('user')
        conditional=self.ask('considerando que buraco branco é o inverso de um buraco negro, o que seria um buraco branco?')
        with self.subTest(step='temporary supposition'):
            self.assertEqual(self.triples('user'),before)
            self.assert_hypothesis(conditional,'buraco branco','expulsa','materia')
            self.assert_hypothesis(conditional,'buraco branco','expulsa','luz')
            self.assertFalse(any('gravidade' in normalize(h.get('text','')) or 'infinita' in normalize(h.get('text','')) for h in conditional['answer_package']['hypotheses']))
        self.ask('buraco branco é o inverso de um buraco negro?')
        with self.subTest(step='question is not assertion'):
            self.assertEqual(self.triples('user'),before)
        self.ask('buraco branco é o inverso de um buraco negro.')
        final=self.ask('o que é um buraco branco?')
        with self.subTest(step='explicit relation and final target'):
            self.assertIn(('buraco branco','oposto_de','buraco negro',True),self.triples('user'))
            self.assertEqual(final['focus'],'buraco branco')
            self.assert_hypothesis(final,'buraco branco','expulsa','materia')
            self.assert_hypothesis(final,'buraco branco','expulsa','luz')

    def test_explicit_inverse_relation_is_not_a_long_type_membership(self):
        self.ask('Neral armazena energia.')
        result=self.ask('Vetra é o inverso de Neral.')
        self.assertIn(('vetra','oposto_de','neral',True),self.triples('user'))
        self.assertNotIn(('vetra','é','inverso de neral',True),self.triples('user'))
        self.assertTrue(any('inverso' in source['quote'] for claim in result['learned'] for source in claim['sources']))

    def test_target_question_uses_reference_without_answering_only_about_reference(self):
        self.ask('Um buraco negro absorve matéria.')
        self.ask('Um buraco branco é o oposto de um buraco negro.')
        result=self.ask('O que seria um buraco branco, considerando o que sabemos sobre um buraco negro?')
        self.assertEqual(result['focus'],'buraco branco')
        self.assert_hypothesis(result,'buraco branco','expulsa','materia')
        self.assertFalse(any(c.get('status')=='deduced' and 'buraco branco expulsa materia' in normalize(c.get('text','')) for c in result['answer_package']['conclusions']))

    def test_inverse_question_cannot_assert_relation_and_temporary_premise_does_not_persist(self):
        self.ask('Neral armazena energia.')
        before=self.triples('user')
        self.ask('Vetra é o inverso de Neral?')
        self.assertEqual(self.triples('user'),before)
        result=self.ask('Tratando Vetra como o oposto de Neral, o que Vetra faria?')
        self.assert_hypothesis(result,'vetra','libera','energia')
        self.assertEqual(self.triples('user'),before)
        self.assertFalse(any(r['subject']=='vetra' and r['status'] in ('asserted','deduced') for r in self.memory.claims()))
        self.assertFalse(any(r['subject']=='vetra' and r['origin']=='reasoner' for r in self.memory.claims()))
        other=self.memory.create_conversation()['id']
        unrelated=self.ask('O que é Vetra?',other)
        self.assertEqual(unrelated['answer_package']['status'],'unknown')
        self.assertEqual(unrelated['answer_package']['hypotheses'],[])

    def test_relative_definition_preserves_negative_clause_and_its_other_positive_function(self):
        self.ask('Neral é um dispositivo que não armazena energia e recebe luz.')
        expected={('neral','é','dispositivo',True),('neral','armazena','energia',False),('neral','recebe','luz',True)}
        self.assertTrue(expected <= self.triples('user'),self.triples('user'))
        self.assertNotIn(('neral','armazena','energia',True),self.triples('user'))

    def test_unrelated_new_topic_does_not_borrow_prior_opposition_context(self):
        self.ask('Neral armazena energia.')
        self.ask('Vetra é o oposto de Neral.')
        self.ask('O que Vetra faria como oposto de Neral?')
        result=self.ask('O que é Taven?')
        self.assertEqual(result['focus'],'taven')
        self.assertEqual(result['answer_package']['status'],'unknown')
        self.assertEqual(result['answer_package']['hypotheses'],[])
        self.assertNotIn('neral',normalize(result['content']))

    def test_arbitrary_named_counterparts_and_nonastronomical_functions(self):
        for source,target,verb,inverse,obj in [('xalor','breno','armazena','libera','energia'),('maru','tiven','aquece','resfria','agua')]:
            with self.subTest(source=source):
                cid=self.memory.create_conversation()['id']
                self.ask(source+' '+verb+' '+obj+'.',cid)
                self.ask(target+' é o oposto de '+source+'.',cid)
                result=self.ask('O que '+target+' faria em oposição a '+source+'?',cid)
                self.assertEqual(result['focus'],target)
                self.assert_hypothesis(result,target,inverse,obj)

    def test_learned_predicate_opposition_and_unrelated_attribute_are_not_inverted(self):
        self.ask('O oposto de filtrar é transportar.')
        self.ask('Neral filtra areia. Neral tem massa.')
        self.ask('Vetra é o oposto de Neral.')
        result=self.ask('O que Vetra faria como oposto de Neral?')
        self.assert_hypothesis(result,'vetra','transporta','areia')
        self.assertFalse(any('massa' in normalize(json.dumps(h,ensure_ascii=False)) for h in result['answer_package']['hypotheses']))

    def test_negative_property_blocks_opposition_proposal(self):
        self.ask('Neral armazena energia.')
        self.ask('Vetra é o oposto de Neral.')
        initial=self.ask('O que Vetra faria como oposto de Neral?')
        self.assert_hypothesis(initial,'vetra','libera','energia')
        self.ask('Vetra não libera energia.')
        result=self.ask('O que Vetra faria como oposto de Neral?')
        self.assertFalse(any('vetra libera energia' in normalize(json.dumps(h,ensure_ascii=False)) for h in result['answer_package']['hypotheses']))

    def test_repeated_opposition_does_not_duplicate_generated_claim_and_source_withdrawal_invalidates(self):
        self.ask('Neral armazena energia.')
        self.ask('Vetra é o oposto de Neral.')
        first=self.ask('O que Vetra faria como oposto de Neral?')
        self.assert_hypothesis(first,'vetra','libera','energia')
        generated=[r for r in self.memory.claims() if r['origin']=='reasoner' and r['subject']=='vetra']
        second=self.ask('O que Vetra faria como oposto de Neral?')
        self.assert_hypothesis(second,'vetra','libera','energia')
        self.assertEqual([r['id'] for r in generated],[r['id'] for r in self.memory.claims() if r['origin']=='reasoner' and r['subject']=='vetra'])
        self.ask('Corrigindo: Neral não armazena energia.')
        self.assertTrue(all(self.memory.claim(r['id'])['status']=='retracted' for r in generated))
        result=self.ask('O que Vetra faria como oposto de Neral?')
        self.assertFalse(any('vetra libera energia' in normalize(json.dumps(h,ensure_ascii=False)) for h in result['answer_package']['hypotheses']))

    def test_legacy_relative_claim_is_interpreted_without_rewriting_user_history(self):
        message='Neral é um dispositivo que armazena energia.'
        with self.memory.transaction():
            mid=self.memory.add_message(self.cid,'user',message)
            self.memory.learn(Assertion('Neral','é','um dispositivo que armazena energia',message),mid)
        original=self.memory.messages(self.cid)[0]
        self.ask('Vetra é o oposto de Neral.')
        result=self.ask('O que Vetra faria como oposto de Neral?')
        self.assert_hypothesis(result,'vetra','libera','energia')
        self.assertEqual(self.memory.messages(self.cid)[0],original)
        self.assertIn(('neral','é','dispositivo que armazena energia',True),self.triples('user'))

    def test_simple_causal_sentence_splits_functions_without_transferring_cause(self):
        message='Neral absorve matéria e luz por causa da sua infinita gravidade.'
        self.ask(message)
        self.assertTrue({('neral','absorve','materia',True),('neral','absorve','luz',True)} <= self.triples('user'))
        self.ask('Vetra é o oposto de Neral.')
        result=self.ask('O que é Vetra?')
        self.assert_hypothesis(result,'vetra','expulsa','materia')
        self.assert_hypothesis(result,'vetra','expulsa','luz')
        self.assertFalse(any('gravidade' in normalize(h.get('text','')) or 'infinita' in normalize(h.get('text','')) for h in result['answer_package']['hypotheses']))

    def test_negative_and_tentative_inverse_relations_do_not_license_target_hypothesis(self):
        for sentence in ('Vetra não é o oposto de Neral.','Talvez Vetra seja o oposto de Neral.'):
            with self.subTest(sentence=sentence):
                memory=Memory(':memory:'); engine=ChatEngine(memory,Settings(research_mode=True))
                try:
                    cid=memory.create_conversation()['id']
                    with patch.object(engine.language_model,'complete',side_effect=AssertionError('Qwen is forbidden')):
                        engine.reply(cid,'Neral armazena energia.')
                        engine.reply(cid,sentence)
                        result=engine.reply(cid,'O que é Vetra?')
                    self.assertFalse(any('vetra libera energia' in normalize(json.dumps(h,ensure_ascii=False)) for h in result['answer_package']['hypotheses']))
                finally: engine.close();memory.close()

    def test_analogy_proposes_new_target_function_with_three_distinct_premises(self):
        self.ask('Mavon armazena energia. Mavon emite luz. Zedir armazena energia.')
        result=self.ask('Faça uma analogia para Zedir.')
        self.assert_hypothesis(result,'zedir','emite','luz')
        hypothesis=next(h for h in result['answer_package']['hypotheses'] if h['subject']=='zedir')
        self.assertEqual(hypothesis['method'],'analogy')
        premises=[self.memory.claim(pid) for pid in hypothesis['premise_ids']]
        self.assertEqual({(p['subject'],p['predicate'],p['object']) for p in premises},
                         {('mavon','armazena','energia'),('mavon','emite','luz'),('zedir','armazena','energia')})
        self.ask('Zedir não emite luz.')
        blocked=self.ask('Faça uma analogia para Zedir.')
        self.assertFalse(any(h.get('subject')=='zedir' and h.get('predicate')=='emite' and h.get('object')=='luz'
                             for h in blocked['answer_package']['hypotheses']))

    def test_natural_conversion_composition_builds_new_sequence_and_replays_it(self):
        self.ask('Plorin converte luz em energia. Xaret converte energia em movimento.')
        result=self.ask('Crie uma solução para transformar luz em movimento.')
        self.assert_hypothesis(result,'sistema de plorin e xaret','transforma','luz em movimento')
        hypothesis=next(h for h in result['answer_package']['hypotheses'] if h['method']=='conversion_composition')
        premises=[self.memory.claim(pid) for pid in hypothesis['premise_ids']]
        self.assertEqual({p['subject'] for p in premises},{'plorin','xaret'})
        package_json=normalize(json.dumps(result['answer_package'],ensure_ascii=False))
        self.assertIn('physical_feasibility_verified',package_json)
        self.assertIn('perdas',normalize(result['content']))
        self.assertFalse(any(c.get('status')=='deduced' and 'luz em movimento' in normalize(c.get('text',''))
                             for c in result['answer_package']['conclusions']))
        generated=next(c for c in self.memory.claims() if c.get('method')=='conversion_composition')
        repeated=self.ask('Crie uma solução para transformar luz em movimento.')
        self.assert_hypothesis(repeated,'sistema de plorin e xaret','transforma','luz em movimento')
        self.assertEqual([c['id'] for c in self.memory.claims() if c.get('method')=='conversion_composition'],[generated['id']])

    def test_natural_conversion_composition_rejects_reverse_and_missing_edge(self):
        self.ask('Plorin converte luz em energia. Xaret converte energia em movimento.')
        for goal in ('movimento em luz','luz em agua'):
            with self.subTest(goal=goal):
                result=self.ask('Crie uma solução para transformar '+goal+'.')
                self.assertEqual(result['answer_package']['status'],'unknown')
                self.assertFalse(any(h.get('method')=='conversion_composition' for h in result['answer_package']['hypotheses']))

    def test_natural_conversion_composition_retracts_after_source_correction(self):
        self.ask('Plorin converte luz em energia. Xaret converte energia em movimento.')
        first=self.ask('Crie uma solução para transformar luz em movimento.')
        self.assert_hypothesis(first,'sistema de plorin e xaret','transforma','luz em movimento')
        generated=next(c for c in self.memory.claims() if c.get('method')=='conversion_composition')
        self.ask('Corrigindo: Xaret não converte energia em movimento.')
        self.assertEqual(self.memory.claim(generated['id'])['status'],'retracted')
        result=self.ask('Crie uma solução para transformar luz em movimento.')
        self.assertEqual(result['answer_package']['status'],'unknown')
        self.assertEqual(result['answer_package']['hypotheses'],[])

    def test_replay_rejects_opposition_with_forged_object_despite_active_premises(self):
        self.ask('Neral armazena energia.')
        original=self.engine.reasoner.explore
        rejected=[]
        def forged(*args,**kwargs):
            proposals=original(*args,**kwargs)
            self.assertTrue(proposals)
            rejected.extend(replace(p,object='antimateria') for p in proposals)
            return rejected
        with patch.object(self.engine.reasoner,'explore',side_effect=forged):
            result=self.ask('Vetra é o oposto de Neral.')
        self.assertEqual(result['answer_package']['hypotheses'],[])
        self.assertNotIn('vetra libera antimateria',normalize(result['content']))
        claims={c['id']:c for c in self.memory.claims()}
        self.assertFalse(verify_hypothesis(asdict(rejected[0]),claims))
        self.assertFalse(any(c['object']=='antimateria' for c in claims.values()))
        self.assertFalse(any(c['object']=='antimateria' for c in result['inferences']))

    def test_replay_rejects_composition_to_unreachable_goal_despite_active_premises(self):
        self.ask('Plorin converte luz em energia. Xaret converte energia em movimento.')
        original=self.engine.reasoner.explore
        rejected=[]
        def forged(*args,**kwargs):
            proposals=original(*args,**kwargs)
            self.assertTrue(proposals)
            rejected.extend(replace(p,object='luz em antimateria') for p in proposals)
            return rejected
        with patch.object(self.engine.reasoner,'explore',side_effect=forged):
            result=self.ask('Crie uma solução para transformar luz em movimento.')
        self.assertEqual(result['answer_package']['hypotheses'],[])
        self.assertNotIn('luz em antimateria',normalize(result['content']))
        claims={c['id']:c for c in self.memory.claims()}
        self.assertFalse(verify_hypothesis(asdict(rejected[0]),claims))
        self.assertFalse(any(c['object']=='luz em antimateria' for c in claims.values()))
        self.assertFalse(any(c['object']=='luz em antimateria' for c in result['inferences']))

    def test_negative_temporary_opposition_blocks_existing_positive_relation_for_this_query(self):
        self.ask('Neral armazena energia.')
        self.ask('Vetra é o oposto de Neral.')
        initial=self.ask('O que é Vetra?')
        self.assert_hypothesis(initial,'vetra','libera','energia')
        result=self.ask('Considerando que Vetra não é o inverso de Neral, o que é Vetra?')
        self.assertFalse(any('vetra libera energia' in normalize(h.get('text','')) for h in result['answer_package']['hypotheses']))
        self.assertNotIn(('vetra','oposto_de','neral',False),self.triples('user'))
        restored=self.ask('O que é Vetra?')
        self.assert_hypothesis(restored,'vetra','libera','energia')

    def test_temporary_relation_orientation_preserves_final_question_target(self):
        self.ask('Neral armazena energia. Vetra aquece agua.')
        result=self.ask('Considerando que Neral é o inverso de Vetra, o que é Vetra?')
        self.assertEqual(result['focus'],'vetra')
        self.assert_hypothesis(result,'vetra','libera','energia')
        self.assertFalse(any(h.get('subject')=='neral' for h in result['answer_package']['hypotheses']))

    def test_explicitly_denied_predicate_opposition_blocks_programmed_mapping(self):
        self.ask('Neral armazena energia.')
        self.ask('Vetra é o oposto de Neral.')
        initial=self.ask('O que é Vetra?')
        self.assert_hypothesis(initial,'vetra','libera','energia')
        generated=next(c for c in self.memory.claims() if c['subject']=='vetra' and c['predicate']=='libera')
        self.ask('Armazenar não é o inverso de liberar.')
        result=self.ask('O que é Vetra?')
        self.assertFalse(any('vetra libera energia' in normalize(h.get('text','')) for h in result['answer_package']['hypotheses']))
        self.assertNotIn(generated['id'],{c['id'] for c in self.memory.claims()})

    def test_causal_phrase_em_razao_de_is_not_part_of_opposed_function(self):
        for index,cause in enumerate(('em razão de sua força','graças à sua força')):
            with self.subTest(cause=cause):
                source,target='neral'+str(index),'vetra'+str(index)
                self.ask(source+' absorve energia '+cause+'.')
                self.ask(target+' é o oposto de '+source+'.')
                result=self.ask('O que é '+target+'?')
                self.assert_hypothesis(result,target,'expulsa','energia')
                self.assertFalse(any('razao' in normalize(h.get('text','')) or 'forca' in normalize(h.get('text','')) for h in result['answer_package']['hypotheses']))

    def test_symmetric_negative_entity_opposition_blocks_previous_positive_relation(self):
        self.ask('Neral armazena energia.')
        self.ask('Neral é o oposto de Vetra.')
        initial=self.ask('O que é Vetra?')
        self.assert_hypothesis(initial,'vetra','libera','energia')
        generated=next(c for c in self.memory.claims() if c['subject']=='vetra' and c['predicate']=='libera')
        self.ask('Vetra não é o oposto de Neral.')
        result=self.ask('O que é Vetra?')
        self.assertFalse(any('vetra libera energia' in normalize(h.get('text','')) for h in result['answer_package']['hypotheses']))
        self.assertNotIn(generated['id'],{c['id'] for c in self.memory.claims()})

    def test_replay_rejects_composition_naming_components_absent_from_its_premises(self):
        self.ask('Plorin converte luz em energia. Xaret converte energia em movimento.')
        original=self.engine.reasoner.explore
        rejected=[]
        def forged(*args,**kwargs):
            proposals=original(*args,**kwargs)
            self.assertTrue(proposals)
            rejected.extend(replace(p,subject='sistema de luma') for p in proposals)
            return rejected
        with patch.object(self.engine.reasoner,'explore',side_effect=forged):
            result=self.ask('Crie uma solução para transformar luz em movimento.')
        self.assertFalse(any(h.get('subject')=='sistema de luma' for h in result['answer_package']['hypotheses']))
        self.assertFalse(any(c['subject']=='sistema de luma' for c in self.memory.claims()))
        self.assertFalse(any(c['subject']=='sistema de luma' for c in result['inferences']))
        self.assertFalse(verify_hypothesis(asdict(rejected[0]),{c['id']:c for c in self.memory.claims()}))

    def test_replay_rejects_unjustified_negative_or_universal_opposition(self):
        original=self.engine.reasoner.explore
        for index,change in enumerate(({'polarity':False},{'scope':'universal'})):
            with self.subTest(change=change):
                source,target='fonte'+str(index),'alvo'+str(index)
                self.ask(source+' armazena energia.')
                rejected=[]
                def forged(*args,**kwargs):
                    proposals=original(*args,**kwargs)
                    self.assertTrue(proposals)
                    rejected.extend(replace(p,**change) for p in proposals)
                    return rejected
                with patch.object(self.engine.reasoner,'explore',side_effect=forged):
                    result=self.ask(target+' é o oposto de '+source+'.')
                self.assertFalse(any(h.get('subject')==target for h in result['answer_package']['hypotheses']))
                self.assertFalse(any(c['origin']=='reasoner' and c['subject']==target for c in self.memory.claims()))
                self.assertFalse(verify_hypothesis(asdict(rejected[0]),{c['id']:c for c in self.memory.claims()}))

    def test_independent_replay_blocks_injected_proposal_using_a_locally_negated_relation(self):
        self.ask('Neral armazena energia.')
        self.ask('Vetra é o oposto de Neral.')
        by_id={c['id']:c for c in self.memory.claims()}
        source=next(c for c in by_id.values() if c['subject']=='neral' and c['predicate']=='armazena')
        link=next(c for c in by_id.values() if c['subject']=='vetra' and c['predicate']=='oposto_de')
        proposal=Proposal('vetra','libera','energia','opposition',[source['id'],link['id']],
                          'Oposição funcional armazena para libera.','Testar entrada e saída de energia.')
        with patch.object(self.engine.reasoner,'explore',return_value=[proposal]):
            result=self.ask('Considerando que Vetra não é o inverso de Neral, o que é Vetra?')
        self.assertFalse(any('vetra libera energia' in normalize(h.get('text','')) for h in result['answer_package']['hypotheses']))
        negative=[{'subject':'vetra','predicate':'oposto_de','object':'neral','polarity':False}]
        self.assertFalse(verify_hypothesis(asdict(proposal),by_id,negative))

    def test_taught_mapping_replaces_programmed_prior_and_retracts_its_old_hypothesis(self):
        self.ask('Neral armazena energia.')
        self.ask('Vetra é o oposto de Neral.')
        initial=self.ask('O que é Vetra?')
        self.assert_hypothesis(initial,'vetra','libera','energia')
        generated=next(c for c in self.memory.claims() if c['subject']=='vetra' and c['predicate']=='libera')
        taught=self.ask('O oposto de armazenar é consumir.')
        mapping=next(c for c in taught['learned'] if c['predicate']=='oposto_de')
        result=self.ask('O que é Vetra?')
        self.assert_hypothesis(result,'vetra','consome','energia')
        self.assertFalse(any('vetra libera energia' in normalize(h.get('text','')) for h in result['answer_package']['hypotheses']))
        self.assertNotIn(generated['id'],{c['id'] for c in self.memory.claims()})
        replacement=next(h for h in result['answer_package']['hypotheses'] if h.get('predicate')=='consome')
        self.assertIn(mapping['id'],replacement['premise_ids'])

    def test_wrong_target_injected_into_temporary_reasoning_is_rejected(self):
        self.ask('Neral armazena energia. Vetra aquece agua.')
        source=next(c for c in self.memory.claims() if c['subject']=='vetra' and c['predicate']=='aquece')
        wrong=Proposal('neral','resfria','agua','opposition',[source['id']],
                       'Oposição funcional aquece para resfria.','Testar a temperatura da água.')
        with patch.object(self.engine.reasoner,'explore',return_value=[wrong]):
            result=self.ask('Considerando que Neral é o inverso de Vetra, o que é Vetra?')
        self.assertEqual(result['focus'],'vetra')
        self.assertFalse(any(h.get('subject')=='neral' for h in result['answer_package']['hypotheses']))
        self.assertFalse(any(c['subject']=='neral' and c['predicate']=='resfria' for c in self.memory.claims()))
        self.assertNotIn('neral resfria agua',normalize(result['content']))

    def test_creation_uses_its_components_without_repeating_unrelated_earlier_topic(self):
        unrelated=self.ask('Um buraco negro absorve luz.')['learned'][0]
        self.ask('Plorin converte luz em calor. Xaret converte calor em movimento.')
        result=self.ask('Crie uma solução para transformar luz em movimento.')
        self.assert_hypothesis(result,'sistema de plorin e xaret','transforma','luz em movimento')
        self.assertNotIn('buraco negro',normalize(result['content']))
        self.assertFalse(any(p.get('claim_id')==unrelated['id'] for p in result['answer_package']['premises']))


if __name__=='__main__':unittest.main()
