from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import uuid
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

from app.datasets import DatasetStore
from app.data import build_future_covariates
from app.factor_review import review_factors,save_factor_comparison
from app.forecast_engine import _engine_versions,_validation_factor_rows,_fit_backtest,ModelSpec


class FactorCutoffTests(unittest.TestCase):
    def test_holdout_factors_never_reach_predictions_and_calendar_is_preserved(self):
        train=pd.DataFrame({'fx':[100,999], 'raw_driver__fx':[100,np.nan]})
        validation=pd.DataFrame({'fx':[2000,3000],'calendar_month':[10,11],'target':[10,20]})
        result=_validation_factor_rows(train,validation,['fx'])
        self.assertEqual(result.fx.tolist(),[100,100])
        self.assertEqual(result.calendar_month.tolist(),[10,11])
        self.assertEqual(validation.fx.tolist(),[2000,3000])
        with self.assertRaisesRegex(ValueError,'no factor value'):
            _validation_factor_rows(train.assign(raw_driver__fx=np.nan),validation,['fx'])

    def test_future_factor_actuals_cannot_improve_reserved_test_score(self):
        dates=pd.date_range('2021-01-01',periods=60,freq='MS')
        history=pd.DataFrame({'item_id':'A','timestamp':dates,'target':100+np.arange(60)*2,'fx':np.arange(60)+20.})
        changed=history.copy();changed.loc[54:,'fx']=1e9
        specs=[ModelSpec('Last observed','last'),ModelSpec('Ridge + drivers','ml',Ridge(alpha=2))]
        with patch('app.forecast_engine._model_specs',return_value=specs):
            before=_fit_backtest(history,['fx'],6,'monthly','deep','model:Ridge + drivers')
            after=_fit_backtest(changed,['fx'],6,'monthly','deep','model:Ridge + drivers')
        self.assertEqual(before[4]['wape_pct'],after[4]['wape_pct'])
        self.assertEqual(before[4]['evaluation_signature'],after[4]['evaluation_signature'])
        self.assertEqual(before[4]['factor_test_policy'],'last_training_value')
        self.assertFalse(before[4]['factor_release_dates_verified'])

    def test_all_missing_factor_is_not_silently_zero(self):
        history=pd.DataFrame({'item_id':['A']*6,'timestamp':pd.date_range('2025-01-01',periods=6,freq='MS'),'target':10,'fx':np.nan})
        for policy in ('carry','median'):
            with self.assertRaisesRegex(ValueError,'missing is not zero'):
                build_future_covariates(history,None,future_date_col=None,future_item_col=None,
                    known_driver_cols=['fx'],frequency='monthly',horizon=2,missing_future_policy=policy)


class FactorReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=DatasetStore(Path(self.tmp.name))
        data=('date,series,customer,sku,qty,fx\n'+''.join(f'2025-{m:02d}-01,A/P,A,P,{10+m},{100+m if m!=2 else ""}\n' for m in range(1,13))).encode()
        sources={'history':self.store.upload('history.csv',data,'history')['id'],
                 'future':self.store.upload('future.csv',b'date,series,fx\n2026-01-01,A/P,150\n','future')['id']}
        settings={'date_col':'date','target_col':'qty','item_col':'series','sku_col':'sku','customer_col':'customer',
            'drivers':['fx'],'frequency':'monthly','horizon':2,'unit':'tonnes','calendar_country':'IR',
            'future_date_col':'date','future_item_col':'series','future_driver_policy':'carry','method_selection':'recommended'}
        self.dataset=self.store.save('Sample',sources,settings,'synthetic_sample',True)
        self.base={'run_id':'base','dataset_id':self.dataset['id'],'source_classification':'synthetic_sample',
            'engine':_engine_versions(),'metrics':{'factor_test_policy':'last_training_value'},
            'method_selection':'recommended','series':{'A/P':{'forecast':[{'timestamp':'2026-01-01'},{'timestamp':'2026-02-01'}]}},
            'input_manifest':{'settings':settings,'sources':[{'role':r,'id':i,'sha256':self.store.source(i)[0]['sha256']} for r,i in sources.items()]}}
        self.payload={'request_id':str(uuid.uuid4()),'reviewed':True}

    def test_report_counts_gaps_and_separates_provided_and_filled_assumptions(self):
        report=review_factors(self.base,self.store);factor=report['factors'][0]
        self.assertEqual((factor['history_rows'],factor['history_missing']),(12,1))
        self.assertEqual((factor['future_provided'],factor['future_filled'],factor['future_expected']),(1,1,2))
        self.assertEqual(factor['latest_recorded_period'],'2025-12-01')
        self.assertEqual(factor['future_kind'],'planning_assumptions')
        self.assertIsNone(factor['geography']);self.assertIsNone(factor['unit'])
        self.assertTrue(report['can_compare'])
        self.assertEqual(len(self.store.list()),1)

    def test_comparison_only_removes_factors_and_is_idempotent(self):
        old=deepcopy(self.dataset)
        saved=save_factor_comparison(self.base,self.store,self.payload)
        self.assertEqual(saved['sources'],old['sources'])
        self.assertEqual(saved['parent_dataset_id'],old['id'])
        self.assertEqual(saved['settings'],{**old['settings'],'drivers':[],'driver_roles':{}})
        self.assertEqual(saved['scenario_provenance']['removed_factors'],['fx'])
        self.assertFalse(saved['scenario_provenance']['orders_changed'])
        self.assertEqual(saved,save_factor_comparison(self.base,self.store,self.payload))
        self.assertEqual(self.store.get(old['id']),old)
        self.assertEqual(len(self.store.list()),2)

    def test_manual_method_is_preserved(self):
        self.base['method_selection']='model:Ridge + drivers'
        saved=save_factor_comparison(self.base,self.store,self.payload)
        self.assertEqual(saved['settings']['method_selection'],'model:Ridge + drivers')

    def test_old_engine_and_unreviewed_requests_are_blocked(self):
        self.base['engine']={'revision':'old'}
        self.assertFalse(review_factors(self.base,self.store)['can_compare'])
        with self.assertRaisesRegex(ValueError,'Recalculate'):
            save_factor_comparison(self.base,self.store,self.payload)
        for payload in ({'request_id':self.payload['request_id']},{'request_id':'bad','reviewed':True}):
            with self.assertRaises(ValueError):save_factor_comparison(self.base,self.store,payload)

    def test_source_tampering_and_nested_scenarios_rejected(self):
        for alteration in ('scenario','hash'):
            base=deepcopy(self.base)
            if alteration=='scenario':base['scenario_name']='Other'
            else:base['input_manifest']['sources'][0]['sha256']='changed'
            with self.assertRaises(ValueError):review_factors(base,self.store)

    def test_api_save_uses_existing_queue_and_no_order_actions(self):
        from fastapi.testclient import TestClient
        import app.main as main
        with patch.object(main,'DATASET_STORE',self.store),patch.object(main,'_load_run',return_value=self.base),TestClient(main.app) as client:
            report=client.get('/api/runs/base/factors');self.assertEqual(report.status_code,200,report.text)
            saved=client.post('/api/runs/base/factor-comparison',json=self.payload);self.assertEqual(saved.status_code,200,saved.text)
            with patch.object(main.jobs,'submit',side_effect=lambda values,name,key:values):
                response=client.post('/api/jobs',json={'dataset_id':saved.json()['id'],'request_id':'comparison-test'})
                self.assertEqual(response.status_code,202,response.text)
                self.assertEqual(response.json()['base_run_id'],'base')

