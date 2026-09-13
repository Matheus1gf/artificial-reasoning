"""Independent checks of real-source normalization, holdout isolation and negative results."""
import copy
import hashlib
import json
import math
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from src.science import discovery, resolve
from src.science import physics, symbolic


class DiscoveryTests(unittest.TestCase):
    def test_nist_normalization_preserves_all_raw_pairs_and_units_remain_unapproved(self):
        corpus = discovery.load_corpus()
        raw = (discovery.CORPUS / 'Norris.dat').read_text()
        lines = raw.splitlines()
        start = next(i for i,line in enumerate(lines) if line.strip().startswith('Data:'))
        pairs = []
        for line in lines[start+1:]:
            try:
                values = list(map(float, line.split()))
            except ValueError:
                continue
            if len(values) == 2:
                pairs.append(values)
        self.assertEqual(len(pairs), 36)
        self.assertEqual([(r['target'], r['variables']['q']) for r in corpus['rows']], [tuple(p) for p in pairs])
        self.assertFalse(corpus['physical_interpretation_approved'])
        self.assertEqual(corpus['provenance']['units']['x'], 'unspecified')
        metadata = copy.deepcopy(corpus['provenance']); metadata['units'] = {'x':'m','y':'m'}
        self.assertFalse(discovery.ingest([{'x':i,'y':i+1} for i in range(4)], metadata)['physical_interpretation_approved'])

    def test_corrupted_raw_and_normalized_sources_are_rejected(self):
        for name in ('Norris.dat', 'nist-norris.observations.v1.json'):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as folder:
                target = Path(folder)/'corpus'; shutil.copytree(discovery.CORPUS, target)
                with (target/name).open('ab') as handle: handle.write(b' ')
                with patch.object(discovery, 'CORPUS', target), self.assertRaises(ValueError):
                    discovery.load_corpus()

    def test_provenance_and_nonfinite_rows_are_rejected(self):
        metadata = discovery.load_corpus()['provenance']
        rows = [{'x':i, 'y':2*i} for i in range(4)]
        for changes in ({'data_kind':'generated'}, {'source_url':'https://secret:pwd@example.org/a'}, {'sha256':'x'*64}, {'units':{}}, {'uncertainty':{}}, {'license':{}}):
            with self.subTest(changes=changes), self.assertRaises((ValueError, TypeError)):
                discovery.ingest(rows, dict(metadata, **changes))
        rows[-1]['y'] = math.nan
        with self.assertRaises(ValueError): discovery.ingest(rows, metadata)

    def test_anonymous_fitting_input_contains_no_certified_model_or_evaluation_rows(self):
        rows = discovery.load_corpus()['rows']; fitting = [i for i in range(36) if i%3]; testing = list(range(0,36,3))
        with patch.object(discovery, 'discover', wraps=discovery.discover) as learner:
            result = discovery.calibration_study(rows, fitting, testing)
        training = learner.call_args.args[0]
        self.assertEqual(training, [rows[i] for i in fitting])
        self.assertTrue(all(set(row)=={'variables','target'} and set(row['variables'])=={'q'} for row in training))
        self.assertEqual(result['expected'], [rows[i]['target'] for i in testing])
        # Independent centered ordinary least squares, not implementation's QR helper.
        xs = [r['variables']['q'] for r in training]; ys = [r['target'] for r in training]
        mx, my = sum(xs)/len(xs), sum(ys)/len(ys)
        slope = sum((x-mx)*(y-my) for x,y in zip(xs,ys))/sum((x-mx)**2 for x in xs)
        errors = [rows[i]['target']-(my+slope*(rows[i]['variables']['q']-mx)) for i in testing]
        self.assertAlmostEqual(result['ordinary_least_squares_rmse'], math.sqrt(sum(e*e for e in errors)/len(errors)), places=10)
        self.assertGreater(result['rmse'], result['ordinary_least_squares_rmse'] + 1e-8)
        self.assertLess(result['rmse'], result['mean_baseline_rmse'])

    def test_overlap_duplicates_and_invalid_indices_are_rejected(self):
        rows = discovery.load_corpus()['rows']
        for train, test in (([0,1,2],[2,3]),([0,0,1],[3]),([0,1,2],[True]),([0,1,2],[36]),([],[3])):
            with self.subTest(train=train,test=test), self.assertRaises((ValueError,TypeError)):
                discovery.calibration_study(rows, train, test)

    def test_catalog_absence_never_establishes_scientific_novelty(self):
        known = discovery.prior_art_search('Norris ozone calibration')
        self.assertTrue(known['matches'])
        self.assertFalse(known['scientific_novelty_established'])
        unknown = discovery.prior_art_search('zxqv987651234')
        self.assertEqual(unknown['matches'], [])
        self.assertFalse(unknown['scientific_novelty_established'])


class ScientificDispatcherTests(unittest.TestCase):
    def test_dispatcher_fits_positions_and_contains_invalid_parameters(self):
        observations = [{'t':t,'x':2+3*t+.4*t*t} for t in (0,.3,.6,.9,1.2)]
        result = resolve({'domain':'physics','operation':'fit','parameters':{'observations':observations,'degree':2}})
        self.assertEqual(result['status'], 'answered')
        self.assertAlmostEqual(result['values']['parameters']['a'], .8)
        for request in ([], {'domain':[]}, {'domain':'physics','operation':'fit','parameters':{'observations':[{'t':i*.2,'x':(-1)**i*1e200} for i in range(5)]}}, {'domain':'physics','operation':'simulate','parameters':{'x':0,'v':1,'dt':1,'units':[]}}):
            with self.subTest(request=request):
                result = resolve(request)
                self.assertEqual(result['status'], 'invalid')
                json.dumps(result, allow_nan=False)
        ambiguous = resolve({'domain':'quantum','operation':'fit','parameters':{'observations':[{'t':0,'shots':100,'zeros':100}], 'candidates':[.2,.8,1.4]}})
        self.assertEqual(ambiguous['status'], 'unknown')
        self.assertFalse(ambiguous['verification']['parameter_identified'])

    def test_active_experiment_selects_before_hidden_environment_is_used(self):
        observations = [{'t':t, 'x':1+2*t+.5*t*t} for t in (0,.2,.4,.6,.8)]
        first = physics.simulated_experiment(observations, {'x':1,'v':2,'a':1}, times=[1,1.5,2])
        second = physics.simulated_experiment(observations, {'x':1,'v':2,'a':1.5}, times=[1,1.5,2])
        self.assertEqual(first['selection'], second['selection'])
        self.assertNotEqual(first['observation'], second['observation'])
        self.assertTrue(first['revision']['refuted'])
        self.assertIsNotNone(first['revision']['negative_result'])
        self.assertAlmostEqual(physics.predict_motion(first['revision']['revised'],1.8), 1+2*1.8+.5*1.8**2)

    def test_declared_even_symmetry_and_independent_sandbox_artifact(self):
        rows = [{'variables':{'q':x}, 'target':x*x+1} for x in (-2,-1,0,1,2)]
        model = symbolic.discover(rows, max_degree=3, max_terms=2, symmetries=[{'variables':['q'],'parity':'even'}])
        self.assertEqual(model['status'],'identified')
        self.assertAlmostEqual(symbolic.predict(model, {'q':3}),10)
        self.assertAlmostEqual(symbolic.predict(model, {'q':-3}),10)
        checked = symbolic.verify_artifact(model, [{'variables':{'q':3},'target':-999}, {'variables':{'q':-4},'target':-999}])
        self.assertTrue(checked['passed'])
        self.assertEqual([c['actual'] for c in checked['checks']], [10,17])
        self.assertFalse(symbolic.verify_artifact(model,[])['passed'])


if __name__ == '__main__': unittest.main()
