"""Primary-source aggregate reanalysis; counts are not fabricated participants.

Reference checked independently: Wang/Busemeyer2013, Table1 page700,
https://jbusemey.pages.iu.edu/quantum/QuestOrdEff.pdf, final two columns.
"""
import copy
import random
import unittest

from src.science import human_context


class HumanContextTests(unittest.TestCase):
    def test_transcription_and_reconstruction_match_primary_published_table(self):
        document,experiments=human_context.load_experiments()
        expected=[[[29,7,34,46],[35,7,23,43]],[[57,5,19,37],[60,14,3,29]]]
        self.assertEqual([[row['counts'] for row in e['orders']] for e in experiments],expected)
        self.assertEqual(document['source_doi'],'10.1111/tops.12040')
        self.assertEqual(sum(sum(row) for experiment in expected for row in experiment),448)
        self.assertEqual(document['data_kind'],'observed_human_aggregate')

    def test_rounding_ambiguity_inconsistent_sum_and_invalid_probabilities_are_rejected(self):
        for probabilities,n,decimals in (([.25]*4,1000,1),([.5]*4,100,4),([.3333,.3333,.3333,0],4,4),([True,0,0,0],1,4)):
            with self.subTest(probabilities=probabilities,n=n),self.assertRaises(ValueError):
                human_context.reconstruct_counts(probabilities,n,decimals)

    def test_partition_conserves_counts_and_does_not_mutate_or_duplicate_observations(self):
        _,experiments=human_context.load_experiments()
        observations=experiments[0]['orders']; original=copy.deepcopy(observations); state=random.getstate()
        first=human_context.partition(observations,7011);second=human_context.partition(observations,7011)
        self.assertEqual(first,second);self.assertEqual(random.getstate(),state);self.assertEqual(observations,original)
        for row,train,test in zip(observations,*first):
            self.assertEqual([a+b for a,b in zip(train['counts'],test['counts'])],row['counts'])
            self.assertEqual(sum(train['counts']),sum(row['counts'])//2)
            self.assertEqual(train['order'],test['order'])

    def test_equal_capacity_models_use_same_real_evidence_and_report_rejection_honestly(self):
        report=human_context.evaluate()
        self.assertFalse(report['new_human_data_collected'])
        self.assertEqual(report['unique_response_count'],448)
        for experiment in report['experiments']:
            self.assertEqual(len(experiment['partitions']),5)
            full=experiment['full_data']
            self.assertAlmostEqual(full['quantum']['score']['nll'],full['classical_context']['score']['nll'],places=10)
            self.assertEqual(experiment['restricted_model_rejected'],full['quantum']['score']['maximum_absolute_probability_residual']>.10)
            for partition in experiment['partitions']:
                a=partition['outcomes']['quantum']; b=partition['outcomes']['classical_context']
                self.assertAlmostEqual(a['evaluation']['nll_per_response'],b['evaluation']['nll_per_response'],places=12)
                self.assertEqual(a['fit']['grid_evaluations'],b['fit']['grid_evaluations'])
        self.assertTrue(any('not new independent' in item for item in report['limits']))


if __name__=='__main__':unittest.main()
