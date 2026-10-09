from copy import deepcopy
import unittest
from app.scoped_accuracy import scoped_accuracy


class ScopedAccuracyTests(unittest.TestCase):
    def fixture(self):
        rows=[dict(item_id='A',timestamp='2026-01-01',step=1,actual=10.,predicted=8.),
              dict(item_id='B',timestamp='2026-01-01',step=1,actual=90.,predicted=80.)]
        base={'engine':{'version':1},'series':{'A':{},'B':{},'__all__':{}},
              'metrics':{'evaluation_signature':'same','independent_accuracy_verified':True,
              'confirmation_periods':['2026-01-01'],'validation_points':2,'range_check':{'rows':rows}}}
        candidate=deepcopy(base)
        candidate['metrics']['range_check']['rows'][0]['predicted']=11.
        candidate['metrics']['range_check']['rows'][1]['predicted']=150.
        return base,candidate

    def test_recomputes_weighted_error_not_average_of_percentages(self):
        base,candidate=self.fixture(); originals=deepcopy((base,candidate))
        result=scoped_accuracy(base,candidate,{'A'})
        self.assertTrue(result['available'])
        # |10-11| + |90-80| = 11; actual total = 100, so WAPE = 11%.
        self.assertAlmostEqual(result['metrics']['wape_pct'],11.)
        self.assertEqual([r['predicted'] for r in result['rows']],[11.,80.])
        self.assertAlmostEqual(result['metrics']['mae'],5.5)
        self.assertEqual((base,candidate),originals)

    def test_bad_or_unmatched_evidence_withholds_scores(self):
        for kind in ('missing','duplicate','actual','signature','unverified','nonfinite','period'):
            base,candidate=self.fixture(); metrics=candidate['metrics']; rows=metrics['range_check']['rows']
            if kind=='missing': rows.pop()
            if kind=='duplicate': rows.append(deepcopy(rows[0]))
            if kind=='actual': rows[0]['actual']=12
            if kind=='signature': metrics['evaluation_signature']='different'
            if kind=='unverified': metrics['independent_accuracy_verified']=False
            if kind=='nonfinite': rows[0]['predicted']=float('nan')
            if kind=='period': rows[0]['timestamp']='2025-12-01'
            with self.subTest(kind=kind): self.assertFalse(scoped_accuracy(base,candidate,{'A'})['available'])

    def test_zero_actuals_keep_percentage_unknown(self):
        base,candidate=self.fixture()
        for run in (base,candidate):
            for row in run['metrics']['range_check']['rows']:row['actual']=0.
        result=scoped_accuracy(base,candidate,{'A'})
        self.assertTrue(result['available'])
        self.assertIsNone(result['metrics']['wape_pct'])
        self.assertIsNotNone(result['metrics']['mae'])
