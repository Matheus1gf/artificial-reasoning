"""Validate authored semantic annotations, structural split manifests and saved model claims."""
import hashlib
import json
from pathlib import Path
import unittest

from src.cognition.datasets import language_corpus, context_corpus
from src.cognition.neural import IntentNetwork
from src.cognition.processor import process_message


class LanguageCorpusTests(unittest.TestCase):
    def test_template_entity_text_and_id_partitions_are_disjoint_and_authored(self):
        corpus=language_corpus()
        self.assertEqual({key:len(rows) for key,rows in corpus.items()},{'training':150,'validation':50,'held_out':50})
        for field in ('id','text','template_id','entities_used'):
            sets=[]
            for rows in corpus.values():
                sets.append({value for row in rows for value in (row[field] if isinstance(row[field],list) else [row[field]])})
                self.assertTrue(all('project-authored' in row['provenance'] and 'no Qwen' in row['provenance'] for row in rows))
            for i,left in enumerate(sets):
                for right in sets[i+1:]:self.assertFalse(left & right,field)

    def test_semantic_context_annotations_are_satisfied_before_any_arrangement(self):
        for row in context_corpus():
            with self.subTest(id=row['id']):
                result=process_message(row['text'],history=row['history']); expected=row['expected']
                for key,value in expected.items():
                    if key=='ambiguous':self.assertEqual(bool(result.ambiguities),value)
                    elif key=='quantities':self.assertEqual(len(result.payload['quantities']),value)
                    elif key=='temporal':self.assertIn(value,[t['relation'] for t in result.payload['temporal']])
                    elif key in ('scope','polarity','object'):
                        self.assertTrue(result.facts);self.assertEqual(result.facts[0][key],value)
                    else:self.assertEqual(getattr(result,key),value)

    def test_committed_checkpoint_and_report_correspond_to_declared_training_only(self):
        directory=Path(__file__).resolve().parents[2]/'experiments/cognition'
        protocol=json.loads((directory/'intent-protocol.v1.json').read_text())
        corpus=json.loads((directory/'language-corpus.v1.json').read_text())
        self.assertEqual(hashlib.sha256((directory/'language-corpus.v1.json').read_bytes()).hexdigest(),protocol['corpus_sha256'])
        artifact=json.loads((directory/'intent-model.v1.json').read_text());model=IntentNetwork(artifact=artifact)
        self.assertEqual(artifact['seed'],protocol['selected_checkpoint_seed'])
        self.assertEqual(set(artifact['training_ids']),{row['id'] for row in corpus['training']})
        self.assertFalse(set(artifact['training_ids']) & {row['id'] for row in corpus['held_out']})
        report=json.loads((directory/'intent-results.v1.json').read_text())
        self.assertEqual([run['seed'] for run in report['runs']],protocol['seeds'])
        selected=next(run for run in report['runs'] if run['seed']==artifact['seed'])
        for split,rows in corpus.items():
            correct=sum(model.predict(row['text'])['intent']==row['intent'] for row in rows)
            self.assertEqual(correct,selected[split]['correct'])
            self.assertEqual(selected[split]['accuracy'],correct/len(rows))
        self.assertLess(selected['held_out']['accuracy'],selected['training']['accuracy'])
        self.assertEqual(report['qwen_calls'],0)


if __name__=='__main__':unittest.main()
