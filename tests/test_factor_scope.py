from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import pandas as pd
from app.factor_scope import apply_factor_scope


class FactorScopeTests(unittest.TestCase):
    def fixture(self):
        def series(key,value):
            return {'forecast':[dict(item_id=key,timestamp='2026-10-01',mean=value,p50=value,p10=0,p90=100)],'history':[],'methods':{}}
        base={'series':{'A':series('A',10),'B':series('B',20),'__all__':series('All series',30)}}
        base['forecast_rows']=[deepcopy(base['series'][key]['forecast'][0]) for key in ('A','B')]
        result=deepcopy(base)
        for rows in (result['forecast_rows'],result['series']['A']['forecast'],result['series']['B']['forecast']):
            for row in rows: row['mean']=99
        result['metrics']={'wape_pct':4,'independent_accuracy_verified':True,'range_check':{'rows':[1]}}
        return base,result

    def test_unselected_values_and_exports_preserved_totals_rebuilt(self):
        base,result=self.fixture(); original=deepcopy(base)
        with TemporaryDirectory() as path:
            folder=Path(path)
            with pd.ExcelWriter(folder/'forecast_package.xlsx') as writer:
                pd.DataFrame({'stale':[1]}).to_excel(writer,sheet_name='Models',index=False)
                pd.DataFrame({'stale':[1]}).to_excel(writer,sheet_name='Forecast',index=False)
            apply_factor_scope(result,base,['A'],folder)
            self.assertEqual(result['series']['B'],base['series']['B'])
            self.assertEqual(result['series']['A']['forecast'][0]['mean'],99)
            self.assertEqual(result['series']['__all__']['forecast'][0]['mean'],119)
            self.assertIsNone(result['series']['__all__']['forecast'][0]['p90'])
            self.assertFalse(result['metrics']['independent_accuracy_verified'])
            self.assertIsNone(result['metrics']['wape_pct'])
            for frame in (pd.read_csv(folder/'forecast.csv'),pd.read_excel(folder/'forecast_package.xlsx')):
                # First workbook sheet is Forecast after stale Models removal.
                self.assertEqual(dict(zip(frame.item_id,frame['mean'])),{'A':99,'B':20})
            self.assertNotIn('Models',pd.ExcelFile(folder/'forecast_package.xlsx').sheet_names)
        self.assertEqual(base,original)

    def test_invalid_scope_and_period_changes_rejected_before_mutation(self):
        for selected in ([],['unknown']):
            base,result=self.fixture(); original=deepcopy(result)
            with self.assertRaises(ValueError):apply_factor_scope(result,base,selected,Path('/unused'))
            self.assertEqual(result,original)
        base,result=self.fixture()
        result['series']['A']['forecast'][0]['timestamp']='2026-11-01'
        with self.assertRaises(ValueError):apply_factor_scope(result,base,['A'],Path('/unused'))

    def test_factor_choice_evidence_and_download_only_cover_selected_series(self):
        import json
        base,result=self.fixture()
        result['factor_evaluation']={'rows':[{'item_id':key,'selected_factors':['fx']} for key in ('A','B')]}
        with TemporaryDirectory() as path:
            folder=Path(path)
            with pd.ExcelWriter(folder/'forecast_package.xlsx') as writer:
                pd.DataFrame(result['forecast_rows']).to_excel(writer,sheet_name='Forecast',index=False)
            apply_factor_scope(result,base,['A'],folder)
            self.assertEqual([r['item_id'] for r in result['factor_evaluation']['rows']],['A'])
            self.assertEqual(json.loads((folder/'factor_evaluation.json').read_text()),result['factor_evaluation'])
            self.assertEqual(pd.read_excel(folder/'forecast_package.xlsx',sheet_name='Factor choices').item_id.tolist(),['A'])
