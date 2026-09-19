import tempfile
import unittest
from pathlib import Path

import pandas as pd

from app.datasets import DatasetStore
from app.data import prepare_history, build_future_covariates
from app.operations import calculate_operations
from app.scenarios import quantity_scenario


class SavedWorkflowTests(unittest.TestCase):
    def test_scenario_preserves_chosen_forecast_and_history(self):
        row={'timestamp':'2026-09-01','mean':100.,'p50':100.,'p10':80.,'p90':120.}
        base={'run_id':'base','run_settings':{},'series':{'A':{'forecast':[row],'history':[{'target':90}]}},'forecast_rows':[dict(row,item_id='A')]}
        with tempfile.TemporaryDirectory() as folder:
            result=quantity_scenario(base,name='Higher demand',adjustment=10,runs_dir=Path(folder))
            self.assertEqual(result['base_run_id'],'base')
            self.assertAlmostEqual(result['series']['A']['forecast'][0]['mean'],110)
            self.assertEqual(base['series']['A']['forecast'][0]['mean'],100)
            self.assertEqual(result['series']['A']['history'],base['series']['A']['history'])
            self.assertFalse(result['scenario']['refitted'])

    def test_midmonth_observations_are_not_discarded(self):
        frame = pd.DataFrame({'date':pd.date_range('2025-01-01', periods=6, freq='MS')+pd.Timedelta(days=14),'qty':[10,20,30,40,50,60]})
        clean, _ = prepare_history(frame,date_col='date',target_col='qty',item_col=None,driver_cols=[],frequency='monthly',outlier_strategy='none')
        self.assertEqual(clean.target.tolist(),[10,20,30,40,50,60])
        self.assertTrue((clean.timestamp.dt.day==1).all())

    def test_saved_inputs_survive_store_recreation(self):
        with tempfile.TemporaryDirectory() as folder:
            store=DatasetStore(Path(folder))
            source=store.upload('history.csv',b'date,qty\n2025-01-15,10\n2025-02-15,20\n2025-03-15,30\n2025-04-15,40\n2025-05-15,50\n2025-06-15,60\n','history')
            settings={'date_col':'date','target_col':'qty','frequency':'monthly','horizon':3,'unit':'units'}
            dataset=store.save('Production',{'history':source['id']},settings,accept_warnings=True)
            reopened=DatasetStore(Path(folder))
            self.assertEqual(reopened.get(dataset['id'])['sources']['history'],source['id'])
            self.assertEqual(reopened.inspect(dataset['sources'],settings)['forecast_start'],'2025-07-01')
            self.assertIn(b'2025-01-15',reopened.source(source['id'])[1])

    def test_invalid_quantities_block_review(self):
        with tempfile.TemporaryDirectory() as folder:
            store=DatasetStore(Path(folder))
            source=store.upload('bad.csv',b'date,qty\n2025-01-01,-10\n','history')
            with self.assertRaisesRegex(ValueError,'negative'):
                store.inspect({'history':source['id']},{'date_col':'date','target_col':'qty'})

    def test_future_factors_reject_ambiguous_periods(self):
        history=pd.DataFrame({'item_id':['A']*6,'timestamp':pd.date_range('2025-01-01',periods=6,freq='MS'),'target':[10]*6,'price':[2]*6})
        future=pd.DataFrame({'date':['2025-07-02','2025-07-20'],'price':[2,3]})
        with self.assertRaisesRegex(ValueError,'one row'):
            build_future_covariates(history,future,future_date_col='date',future_item_col=None,known_driver_cols=['price'],frequency='monthly',horizon=1)

    def test_mrp_nets_proposals_and_adds_customers(self):
        forecast=[{'timestamp':f'2026-{month:02d}-01','mean':50} for month in [7,8,9]]
        run={'metadata':{x:{'sku':'A','production_line':'L'} for x in ['c1','c2']},'series':{x:{'forecast':forecast} for x in ['c1','c2']}}
        sheets={'bom':pd.DataFrame([{'sku':'A','material_id':'M','quantity_per_tonne':1}]),'materials':pd.DataFrame([{'material_id':'M','material_name':'Material','inventory_on_hand':0,'safety_stock':0,'lead_time_days':10,'moq':100}]),'capacity':pd.DataFrame([{'production_line':'L','period':f'2026-{m:02d}-01','available_tonnes':0} for m in [7,8,9]])}
        result=calculate_operations(run,sheets)
        self.assertEqual([r['gross_requirement'] for r in result['materials']],[100,100,100])
        self.assertEqual([r['recommended_order'] for r in result['materials']],[100,100,100])
        self.assertEqual(result['capacity'][0]['forecast_tonnes'],100)
        self.assertEqual(result['capacity'][0]['status'],'bottleneck')


if __name__=='__main__': unittest.main()
