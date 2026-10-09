from copy import deepcopy
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest
import uuid

import pandas as pd
from fastapi.testclient import TestClient

from app.datasets import DatasetStore
from app.factors import FactorStore
from app.factor_imports import review_import, save_import
from app.factor_links import choices, preview_link, save_link
from app.forecast_engine import _engine_versions
from app.data import read_table


class FactorLinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.root=Path(self.tmp.name)
        self.store=DatasetStore(self.root/'datasets'); self.factors=FactorStore(self.root/'factors')
        dates=pd.date_range('2024-01-01',periods=24,freq='MS')
        rows=[dict(date=d.strftime('%Y-%m-%d'),item=item,sku='SKU',customer=item,qty=20+i+(j*5))
              for j,item in enumerate(['A','B']) for i,d in enumerate(dates)]
        self.original=pd.DataFrame(rows)
        source=self.store.upload('sales.csv',self.original.to_csv(index=False).encode(),'history')
        settings=dict(date_col='date',target_col='qty',item_col='item',sku_col='sku',customer_col='customer',
            drivers=[],frequency='monthly',horizon=2,unit='tonnes',profile='fast',future_driver_policy='require',
            method_selection='model:Ridge + drivers',missing_strategy='auto',outlier_strategy='none')
        self.dataset=self.store.save('Monthly sales',{'history':source['id']},settings,'synthetic_sample',True)
        self.base=dict(run_id='base',dataset_id=self.dataset['id'],source_classification='synthetic_sample',engine=_engine_versions(),
            method_selection=settings['method_selection'],series={item:{'forecast':[{'timestamp':'2026-01-01'},{'timestamp':'2026-02-01'}]} for item in ['A','B']},
            input_manifest={'settings':settings,'sources':[{'role':'history','id':source['id'],'sha256':source['sha256']}]})
        self.factor_rows=[dict(period=d.strftime('%Y-%m-%d'),value=100+i,published=(d.to_pydatetime()+timedelta(days=5)).strftime('%Y-%m-%d'))
            for i,d in enumerate(pd.date_range('2023-11-30',periods=27,freq='ME'))]
        # Later correction must not rewrite the information available in Jan 2024.
        self.factor_rows.append(dict(period='2023-11-30',value=999,published='2024-02-15'))
        self.snapshot=self.factor(self.factor_rows)
        self.payload={'snapshot_id':self.snapshot['id'],'lag_months':2,'future_value':150}

    def tearDown(self): self.tmp.cleanup()

    def factor(self,rows):
        source=self.store.upload('factor.csv',pd.DataFrame(rows).to_csv(index=False).encode(),'factor_observations')
        config=dict(source_id=source['id'],name='Index',unit='index points',geography='Iran · synthetic',provider='Test',
            frequency='monthly',classification='synthetic_sample',mapping={'period':'A','value':'B','available_at':'C'})
        review=review_import(self.store,config)
        return save_import(self.store,self.factors,{**config,'review_token':review['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())})

    def save(self,payload=None):
        payload=payload or self.payload
        review=preview_link(self.base,self.store,self.factors,payload)
        body={**payload,'review_token':review['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())}
        return save_link(self.base,self.store,self.factors,body),body

    def test_cutoffs_exclude_revisions_and_future_releases(self):
        result=preview_link(self.base,self.store,self.factors,self.payload)
        self.assertEqual(result['missing'],0)
        self.assertEqual(result['rows'][0]['value'],100)
        self.assertEqual(result['rows'][0]['publication_date'],'2023-12-05')
        future=[r for r in result['rows'] if r['kind']=='future']
        self.assertEqual(future[0]['treatment'],'published_observation')
        self.assertEqual(future[1]['treatment'],'planning_assumption')
        self.assertEqual(future[1]['value'],150)
        self.assertEqual(future[1]['available_before'],'2026-01-01')
        self.assertEqual(len(choices(self.base,self.store,self.factors)['snapshots']),1)

    def test_reviewed_factor_testing_is_explicit_and_saved(self):
        original=deepcopy(self.dataset)
        saved,_=self.save({**self.payload,'method':'factor_test'})
        self.assertEqual(saved['settings']['method_selection'],'factor_test')
        self.assertEqual(saved['settings']['evidence_policy'],'standard')
        self.assertEqual(self.store.get(original['id']),original)

    def test_followup_scenario_uses_canonical_model_not_subset_variant_name(self):
        base={**self.base,'method_selection':'factor_test',
              'leaderboard':[{'model':'Ridge + drivers [fx]'},{'model':'Ridge + drivers [history only]'}]}
        report=preview_link(base,self.store,self.factors,{**self.payload,'method':'model:Ridge + drivers'})
        self.assertEqual(report['method'],'model:Ridge + drivers')
        with self.assertRaises(ValueError):
            preview_link(base,self.store,self.factors,{**self.payload,'method':'model:Ridge + drivers [fx]'})

    def test_scope_is_validated_and_bound_to_review(self):
        for selected in ([],['unknown'],['A','A'],[True],'A'):
            with self.assertRaises(ValueError):
                preview_link(self.base,self.store,self.factors,{**self.payload,'series_ids':selected})
        saved,body=self.save({**self.payload,'series_ids':['A']})
        self.assertEqual(saved['scenario_provenance']['alignment']['series_ids'],['A'])
        body['series_ids']=['B']
        with self.assertRaisesRegex(ValueError,'Review these exact inputs'):
            save_link(self.base,self.store,self.factors,body)

    def test_unpublished_history_and_missing_assumptions_block(self):
        for changes in ({'lag_months':1},{'future_value':None}):
            payload={**self.payload,**changes}
            self.assertGreater(preview_link(self.base,self.store,self.factors,payload)['missing'],0)
            with self.assertRaisesRegex(ValueError,'missing or unpublished'): self.save(payload)

    def test_monthly_assumptions_preserve_known_values_and_saved_evidence(self):
        payload={**self.payload, 'future_value':None,
                 'future_values':{'2026-01-01':500, '2026-02-01':175}}
        report=preview_link(self.base,self.store,self.factors,payload)
        future=[r for r in report['rows'] if r['kind']=='future']
        self.assertEqual(future[0]['treatment'],'published_observation')
        self.assertNotEqual(future[0]['value'],500)
        self.assertEqual(future[1]['value'],175)
        saved,body=self.save(payload)
        self.assertEqual(saved['scenario_provenance']['alignment']['future_values'],payload['future_values'])
        source,content=self.store.source(saved['sources']['future'])
        frame=read_table(source['name'],content)
        self.assertTrue((frame.loc[frame.timestamp.eq('2026-02-01'),report['column']]==175).all())
        body['future_values']['2026-02-01']=190
        with self.assertRaisesRegex(ValueError,'Review these exact inputs'):
            save_link(self.base,self.store,self.factors,body)

    def test_monthly_assumptions_reject_invalid_or_ambiguous_inputs(self):
        for curve in ([], {'2027-01-01':5}, {'2026-02-01':True},
                      {'2026-02-01':float('inf')}, {'2026-02-01':'175'}):
            with self.subTest(curve=curve), self.assertRaises(ValueError):
                preview_link(self.base,self.store,self.factors,
                    {**self.payload,'future_value':None,'future_values':curve})
        with self.assertRaises(ValueError):
            preview_link(self.base,self.store,self.factors,{**self.payload,'future_values':{}})
        report=preview_link(self.base,self.store,self.factors,
            {**self.payload,'future_value':None,'future_values':{}})
        self.assertGreater(report['missing'],0)

    def test_different_months_feed_different_future_values(self):
        snapshot=self.factor([r for r in self.factor_rows if r['period']<'2025-11-01'])
        payload={**self.payload,'snapshot_id':snapshot['id'],'future_value':None,
                 'future_values':{'2026-01-01':160,'2026-02-01':185}}
        saved,_=self.save(payload)
        alignment=saved['scenario_provenance']['alignment']
        self.assertEqual([r['value'] for r in alignment['rows'] if r['kind']=='future'],[160,185])
        source,content=self.store.source(saved['sources']['future'])
        frame=read_table(source['name'],content)
        for period,value in payload['future_values'].items():
            self.assertEqual(frame.loc[frame.timestamp.eq(period),alignment['column']].tolist(),[value,value])

    def test_no_silent_gap_fill(self):
        snapshot=self.factor(self.factor_rows[1:])
        result=preview_link(self.base,self.store,self.factors,{**self.payload,'snapshot_id':snapshot['id']})
        self.assertEqual(result['rows'][0]['treatment'],'missing_or_unpublished')
        self.assertIsNone(result['rows'][0]['value'])

    def test_sales_gaps_and_classification_mismatch_are_blocked(self):
        frame=self.original[self.original.date.ne('2024-05-01')]
        source=self.store.upload('gapped.csv',frame.to_csv(index=False).encode(),'history')
        saved=self.store.save('Gaps',{'history':source['id']},self.dataset['settings'],'synthetic_sample',True)
        base={**self.base,'dataset_id':saved['id'],'input_manifest':{'settings':saved['settings'],
            'sources':[{'role':'history','id':source['id'],'sha256':source['sha256']}]}}
        with self.assertRaisesRegex(ValueError,'missing months'):preview_link(base,self.store,self.factors,self.payload)
        with self.assertRaisesRegex(ValueError,'classification'):
            preview_link({**self.base,'source_classification':'user_provided'},self.store,self.factors,self.payload)

    def test_immutable_idempotent_reconciled_sources(self):
        original=deepcopy(self.dataset)
        saved,body=self.save()
        self.assertEqual(saved,save_link(self.base,self.store,self.factors,body))
        self.assertEqual(self.store.get(original['id']),original)
        source,content=self.store.source(saved['sources']['history']); frame=read_table(source['name'],content)
        pd.testing.assert_frame_equal(frame[self.original.columns],self.original)
        self.assertEqual(saved['scenario_provenance']['alignment']['history_quantity'],self.original.qty.sum())
        self.assertFalse(saved['scenario_provenance']['orders_changed'])
        self.assertEqual(saved['settings']['future_driver_policy'],'require')
        future_source,data=self.store.source(saved['sources']['future']);future=read_table(future_source['name'],data)
        self.assertEqual(len(future),4)
        self.assertEqual(future[future.timestamp.eq('2026-02-01')][saved['settings']['drivers'][0]].tolist(),[150,150])
        with self.assertRaises(ValueError):save_link(self.base,self.store,self.factors,{**body,'future_value':999})
        with self.assertRaises(ValueError):save_link(self.base,self.store,self.factors,{**body,'reviewed':False})

    def test_invalid_lag_classification_engine_and_source(self):
        for lag in (0,13,True,1.5):
            with self.assertRaises(ValueError):preview_link(self.base,self.store,self.factors,{**self.payload,'lag_months':lag})
        with self.assertRaises(ValueError):preview_link({**self.base,'engine':{}},self.store,self.factors,self.payload)
        with self.assertRaises(ValueError):preview_link(self.base,self.store,self.factors,{**self.payload,'future_value':float('inf')})
        source_id=self.snapshot['source']['id']
        (self.store.root/f'{source_id}.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed since import'):preview_link(self.base,self.store,self.factors,self.payload)

    def test_combined_factors_preserve_rows_values_and_review_identity(self):
        second=self.factor([{**r,'value':r['value']*3} for r in self.factor_rows])
        payload={'links':[self.payload,{'snapshot_id':second['id'],'lag_months':2,
            'future_values':{'2026-02-01':450}}],'series_ids':['A']}
        report=preview_link(self.base,self.store,self.factors,payload)
        self.assertEqual((report['factor_count'],report['missing'],len(report['rows'])),(2,0,52))
        self.assertEqual(report['series_ids'],['A'])
        self.assertEqual([r['rows'][0]['value'] for r in report['factors']],[100,300])
        saved,body=self.save(payload)
        self.assertEqual(saved,save_link(self.base,self.store,self.factors,body))
        self.assertEqual(len(saved['settings']['drivers']),2)
        source,content=self.store.source(saved['sources']['history']);history=read_table(source['name'],content)
        pd.testing.assert_frame_equal(history[self.original.columns],self.original)
        source,content=self.store.source(saved['sources']['future']);future=read_table(source['name'],content)
        columns=saved['settings']['drivers']
        feb=future.loc[future.timestamp.eq('2026-02-01')]
        self.assertEqual(feb[columns[0]].tolist(),[150,150])
        self.assertEqual(feb[columns[1]].tolist(),[450,450])
        self.assertEqual(len(saved['scenario_provenance']['definitions']),2)
        changed=deepcopy(body);changed['links'][1]['future_values']['2026-02-01']=460
        with self.assertRaisesRegex(ValueError,'Review these exact inputs'):save_link(self.base,self.store,self.factors,changed)

    def test_combined_factors_reject_duplicates_missing_data_and_invalid_methods(self):
        second=self.factor(self.factor_rows)
        for links in ([],[self.payload]*2,[None],[self.payload]*9):
            with self.assertRaises(ValueError):preview_link(self.base,self.store,self.factors,{'links':links})
        payload={'links':[self.payload,{'snapshot_id':second['id'],'lag_months':2}]}
        report=preview_link(self.base,self.store,self.factors,payload)
        self.assertGreater(report['missing'],0)
        with self.assertRaisesRegex(ValueError,'missing or unpublished'):self.save(payload)
        for extra in ({'method':'made up'},{'snapshot_id':self.snapshot['id']},{'links':[{**self.payload,'series_ids':['A']}]}):
            with self.assertRaises(ValueError):preview_link(self.base,self.store,self.factors,{**payload,**extra})
        approved=preview_link(self.base,self.store,self.factors,{'links':[self.payload],'method':'recommended'})
        self.assertEqual(approved['method'],'recommended')

    def test_jalali_factor_requires_approved_alignment_and_does_not_fill_missing_months(self):
        from persiantools.jdatetime import JalaliDate
        rows=[]
        for ordinal in range(1402*12+7,1404*12+10):
            year,month=divmod(ordinal,12);month+=1
            j=JalaliDate(year,month,JalaliDate.days_in_month(month,year))
            release=JalaliDate(j.to_gregorian()+timedelta(days=3))
            rows.append({'period':j.isoformat(),'value':100+ordinal-(1402*12+7),'published':release.isoformat()})
        def snapshot(data):
            source=self.store.upload('jalali.csv',pd.DataFrame(data).to_csv(index=False).encode(),'factor_observations')
            config=dict(source_id=source['id'],name='Persian index',unit='index points',geography='Iran · synthetic',provider='Test',
                frequency='monthly',classification='synthetic_sample',mapping={'period':'A','value':'B','available_at':'C'},
                calendar='jalali',publication_timezone='Asia/Tehran')
            review=review_import(self.store,config)
            self.assertEqual(review['issue_count'],0)
            return save_import(self.store,self.factors,{**config,'review_token':review['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())})
        factor=snapshot(rows)
        payload={'snapshot_id':factor['id'],'lag_months':2,'future_value':150}
        with self.assertRaisesRegex(ValueError,'Approve linking'):preview_link(self.base,self.store,self.factors,payload)
        payload['period_alignment']='last_completed_jalali_month'
        report=preview_link(self.base,self.store,self.factors,payload)
        self.assertEqual(report['missing'],0)
        first=report['rows'][0]
        self.assertEqual(first['lag_cutoff'],'2023-11-30')
        self.assertEqual(first['observation_period'],'2023-11-21')
        self.assertEqual(first['original_period'],'1402-08-30')
        saved,_=self.save(payload)
        self.assertEqual(saved['scenario_provenance']['alignment']['period_alignment'],'last_completed_jalali_month')
        self.assertEqual(saved['settings']['factor_definitions'][report['column']]['normalization']['calendar'],'jalali')
        import app.main as main
        runs=self.root/'jalali-runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.store),patch.object(main,'FACTOR_STORE',self.factors),patch.object(main,'RUNS_DIR',runs),TestClient(main.app) as client:
            baseline=client.post('/api/run-saved',json={'dataset_id':self.dataset['id']})
            self.assertEqual(baseline.status_code,200,baseline.text)
            run=baseline.json();url=f"/api/runs/{run['run_id']}/factor-links"
            reviewed=client.post(url+'/preview',json=payload)
            self.assertEqual(reviewed.status_code,200,reviewed.text)
            dataset=client.post(url,json={**payload,'reviewed':True,'review_token':reviewed.json()['review_token'],'request_id':str(uuid.uuid4())})
            self.assertEqual(dataset.status_code,200,dataset.text)
            forecast=client.post('/api/run-saved',json={'dataset_id':dataset.json()['id']})
            self.assertEqual(forecast.status_code,200,forecast.text)
            linked=forecast.json()
            self.assertTrue(linked['factor_validation']['available'])
            package=runs/linked['run_id']/'forecast_package.xlsx'
            evidence=pd.read_excel(package,sheet_name='Factor alignment')
            self.assertEqual(evidence.iloc[0]['observation_period'],'2023-11-21')
            self.assertEqual(evidence.iloc[0]['original_period'],'1402-08-30')
            self.assertEqual(linked['metrics']['evaluation_signature'],run['metrics']['evaluation_signature'])
            self.assertEqual(client.get(f"/api/runs/{run['run_id']}").json(),run)
        missing=snapshot(rows[1:])
        bad=preview_link(self.base,self.store,self.factors,{**payload,'snapshot_id':missing['id']})
        self.assertEqual(bad['missing'],1)
        self.assertIsNone(bad['rows'][0]['value'])

    def test_real_engine_api_and_export(self):
        import app.main as main
        runs=self.root/'runs';runs.mkdir()
        with patch.object(main,'DATASET_STORE',self.store),patch.object(main,'FACTOR_STORE',self.factors),patch.object(main,'RUNS_DIR',runs),TestClient(main.app) as client:
            baseline=client.post('/api/run-saved',json={'dataset_id':self.dataset['id']})
            self.assertEqual(baseline.status_code,200,baseline.text)
            run=baseline.json();url=f"/api/runs/{run['run_id']}/factor-links"
            review=client.post(url+'/preview',json=self.payload)
            self.assertEqual(review.status_code,200,review.text)
            saved=client.post(url,json={**self.payload,'reviewed':True,'review_token':review.json()['review_token'],'request_id':str(uuid.uuid4())})
            self.assertEqual(saved.status_code,200,saved.text)
            result=client.post('/api/run-saved',json={'dataset_id':saved.json()['id']})
            self.assertEqual(result.status_code,200,result.text)
            linked=result.json()
            self.assertEqual(linked['metrics']['evaluation_signature'],run['metrics']['evaluation_signature'])
            self.assertEqual(set(linked['series']),set(run['series']))
            self.assertEqual(linked['scenario']['type'],'factor_link')
            rows=linked['series']['__all__']['forecast']
            self.assertAlmostEqual(sum(r['mean'] for r in rows),sum(r['mean'] for k,v in linked['series'].items() if k!='__all__' for r in v['forecast']))
            package=runs/linked['run_id']/'forecast_package.xlsx'
            with pd.ExcelFile(package) as workbook:
                self.assertIn('Factor alignment',workbook.sheet_names)
            self.assertEqual(len(pd.read_excel(package,sheet_name='Factor alignment')),26)
            scoped_payload={**self.payload,'series_ids':['A']}
            review=client.post(url+'/preview',json=scoped_payload)
            self.assertEqual(review.status_code,200,review.text)
            saved=client.post(url,json={**scoped_payload,'reviewed':True,
                'review_token':review.json()['review_token'],'request_id':str(uuid.uuid4())})
            self.assertEqual(saved.status_code,200,saved.text)
            response=client.post('/api/run-saved',json={'dataset_id':saved.json()['id']})
            self.assertEqual(response.status_code,200,response.text)
            scoped=response.json()
            self.assertEqual(scoped['series']['B'],run['series']['B'])
            self.assertEqual(scoped['metrics']['independent_accuracy_verified'],scoped['scoped_accuracy']['available'])
            self.assertTrue(scoped['scoped_accuracy']['available'],scoped['scoped_accuracy']['reason'])
            self.assertTrue(scoped['factor_validation']['available'],scoped['factor_validation']['reason'])
            self.assertAlmostEqual(scoped['factor_validation']['scenario_error_pct'],scoped['metrics']['wape_pct'])
            if scoped['scoped_accuracy']['available']:
                evidence=scoped['scoped_accuracy']['rows']
                expected=100*sum(abs(r['actual']-r['predicted']) for r in evidence)/sum(abs(r['actual']) for r in evidence)
                self.assertAlmostEqual(scoped['metrics']['wape_pct'],expected)
            package=runs/scoped['run_id']/'forecast_package.xlsx'
            exported=pd.read_excel(package,sheet_name='Forecast')
            self.assertEqual(exported.loc[exported.item_id.eq('B'),'mean'].tolist(),
                [r['mean'] for r in run['series']['B']['forecast']])
            self.assertEqual(client.get(f"/api/runs/{run['run_id']}").json(),run)
            second=self.factor([{**r,'value':r['value']*3} for r in self.factor_rows])
            combined_payload={'links':[self.payload,{'snapshot_id':second['id'],'lag_months':2,'future_value':450}]}
            review=client.post(url+'/preview',json=combined_payload)
            self.assertEqual(review.status_code,200,review.text)
            saved=client.post(url,json={**combined_payload,'reviewed':True,'review_token':review.json()['review_token'],'request_id':str(uuid.uuid4())})
            self.assertEqual(saved.status_code,200,saved.text)
            response=client.post('/api/run-saved',json={'dataset_id':saved.json()['id']})
            self.assertEqual(response.status_code,200,response.text)
            combined=response.json()
            self.assertEqual(combined['metrics']['evaluation_signature'],run['metrics']['evaluation_signature'])
            self.assertEqual(combined['scenario']['alignment']['factor_count'],2)
            proof=combined['factor_validation']
            self.assertTrue(proof['available'],proof['reason'])
            denominator=sum(abs(r['actual']) for r in proof['rows'])
            expected=100*sum(abs(r['actual']-r['predicted']) for r in proof['rows'])/denominator
            self.assertAlmostEqual(proof['scenario_error_pct'],expected)
            self.assertAlmostEqual(proof['scenario_error_pct'],combined['metrics']['wape_pct'])
            self.assertAlmostEqual(proof['baseline_error_pct'],run['metrics']['wape_pct'])
            from app.factor_links import accuracy_comparison
            same_mix={**combined,'method_selection':run['method_selection'],
                      'series_ensemble_weights':run['series_ensemble_weights']}
            self.assertFalse(accuracy_comparison(run,same_mix)['method_changed'])
            changed_mix={**same_mix,'series_ensemble_weights':{**run['series_ensemble_weights'],'A':{'different model':1}}}
            self.assertTrue(accuracy_comparison(run,changed_mix)['method_changed'])
            self.assertEqual(sum(len(s['forecast']) for k,s in combined['series'].items() if k!='__all__'),4)
            package=runs/combined['run_id']/'forecast_package.xlsx'
            self.assertEqual(len(pd.read_excel(package,sheet_name='Factor alignment')),52)
            self.assertEqual(len(pd.read_excel(package,sheet_name='Factor sources')),2)
            self.assertEqual(len(pd.read_excel(package,sheet_name='Factor test evidence')),len(proof['rows']))
            self.assertEqual(client.get(f"/api/runs/{run['run_id']}").json(),run)


if __name__=='__main__':unittest.main()
