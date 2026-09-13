"""Train the own classifier, verify optimization/provenance and deterministic features."""
import copy
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import unittest

from src.cognition.neural import IntentNetwork, LABELS, features


class IntentNetworkTests(unittest.TestCase):
    @staticmethod
    def examples():
        phrases=['Neral emite luz.','O que significa Vetra?','Calcule 12 + 8.','Invente uma máquina para aquecer água.','Corrigindo: Neral não emite luz.','Talvez Neral emita luz.','Resuma a resposta.','Olá, bom dia.','Compare a estrutura de Neral e Vetra.','Prefiro respostas breves.']
        return [{'id':'qa:'+str(i),'text':text,'intent':label} for i,(text,label) in enumerate(zip(phrases,LABELS))]

    def test_real_gradient_training_changes_weights_and_reduces_cross_entropy(self):
        examples=self.examples(); model=IntentNetwork(seed=37)
        initial=model.artifact(); loss0=-sum(math.log(model.predict(row['text'])['probabilities'][row['intent']]) for row in examples)/len(examples)
        artifact=model.train(examples,epochs=35,learning_rate=.3)
        loss1=-sum(math.log(model.predict(row['text'])['probabilities'][row['intent']]) for row in examples)/len(examples)
        self.assertLess(loss1,loss0*.2)
        self.assertNotEqual(artifact['w1'],initial['w1'])
        self.assertNotEqual(artifact['w2'],initial['w2'])
        self.assertEqual(artifact['training_ids'],[row['id'] for row in examples])
        self.assertEqual(len(artifact['loss_curve']),35)
        restored=IntentNetwork(artifact=artifact)
        self.assertEqual(restored.predict(examples[0]['text']),model.predict(examples[0]['text']))
        artifact['w1'][0][0]=99
        self.assertNotEqual(restored.artifact()['w1'][0][0],99)

    def test_reproducible_training_and_features_ignore_python_hash_seed(self):
        before=random.getstate()
        first=IntentNetwork(seed=42); second=IntentNetwork(seed=42)
        self.assertEqual(first.train(self.examples(),epochs=2),second.train(self.examples(),epochs=2))
        self.assertEqual(random.getstate(),before)
        root=Path(__file__).resolve().parents[2]
        command=[sys.executable,'-c','import json; from src.cognition.neural import features; print(json.dumps(features("Neral não emite luz."), sort_keys=True))']
        outputs=[]
        for seed in ('1','999'):
            proc=subprocess.run(command,cwd=root,env=dict(os.environ,PYTHONHASHSEED=seed),capture_output=True,text=True)
            self.assertEqual(proc.returncode,0,proc.stderr); outputs.append(proc.stdout)
        self.assertEqual(*outputs)
        self.assertNotEqual(features('Neral emite luz.'),features('Neral não emite luz.'))

    def test_corrupt_checkpoint_or_invalid_training_cannot_silently_change_model(self):
        original=IntentNetwork(seed=5).artifact()
        mutations=[('seed',None),('seed',True),('seed',-1),('labels',list(reversed(LABELS))),('w1',[]),('b2',[math.nan]*len(LABELS))]
        for key,value in mutations:
            bad=copy.deepcopy(original);bad[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ValueError): IntentNetwork(artifact=bad)
        model=IntentNetwork(seed=5); examples=self.examples(); examples[-1]['id']=examples[0]['id']
        with self.assertRaises(ValueError):model.train(examples)
        self.assertEqual(model.artifact(),original)
        for kwargs in ({'epochs':True},{'epochs':201},{'learning_rate':math.nan},{'learning_rate':0}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):model.train(self.examples(),**kwargs)
        prediction=model.predict('Nenhuma certeza é presumida.')
        self.assertAlmostEqual(sum(prediction['probabilities'].values()),1)
        self.assertTrue(0<=prediction['probability']<=1)


if __name__=='__main__':unittest.main()
