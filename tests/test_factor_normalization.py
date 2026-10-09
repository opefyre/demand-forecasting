from copy import deepcopy
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.datasets import DatasetStore
from app.factors import FactorStore, observations_available_at
from app.factor_imports import review_import, save_import
from app.factor_normalization import input_date, completed_jalali_month, numeric


class IranFactorTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        self.datasets=DatasetStore(self.root/'datasets');self.factors=FactorStore(self.root/'factors')

    def tearDown(self):
        self.tmp.cleanup()

    def payload(self,rows,**changes):
        source=self.datasets.upload('iran-factor.csv',('period,value,published\n'+rows).encode(),'factor_observations')
        return dict(source_id=source['id'],name='Synthetic Iran factor',unit='index points',geography='Iran · national',
                    provider='Synthetic test source',frequency='monthly',classification='synthetic_sample',
                    mapping={'period':'A','value':'B','available_at':'C'},calendar='jalali',
                    publication_timezone='Asia/Tehran',**changes)

    def save(self,payload):
        review=review_import(self.datasets,payload)
        body={**payload,'reviewed':True,'review_token':review['review_token'],'request_id':str(uuid.uuid4())}
        return save_import(self.datasets,self.factors,body),body

    def test_persian_digits_dates_month_boundaries_and_release_timezone(self):
        payload=self.payload('۱۴۰۴/۰۱/۳۱,۱۲۳٫۵,۱۴۰۴/۰۲/۰۵\n')
        report=review_import(self.datasets,payload,today=date(2026,10,3))
        self.assertEqual(report['issue_count'],0)
        p=report['points'][0]
        # Known Nowruz 1404: 21 March 2025; Farvardin has 31 days.
        self.assertEqual((p['period_start'],p['period'],p['publication_date']),('2025-03-21','2025-04-20','2025-04-25'))
        self.assertEqual(p['value'],123.5)
        self.assertEqual(p['original_period'],'۱۴۰۴/۰۱/۳۱')
        self.assertEqual(p['available_at'],'2025-04-25T20:29:59.999999+00:00')
        saved,_=self.save(payload)
        self.assertTrue(observations_available_at(saved,'2025-04-25T20:00:00Z').empty)
        self.assertEqual(observations_available_at(saved,'2025-04-25T21:00:00Z').value.tolist(),[123.5])
        self.assertEqual(saved['calendar'],'jalali')

    def test_jalali_leap_months_gaps_annual_and_wrong_calendar(self):
        self.assertEqual(input_date('۱۴۰۳-۱۲-۳۰','jalali'),date(2025,3,20))
        with self.assertRaises(ValueError):input_date('1404-12-30','jalali')
        with self.assertRaises(ValueError):input_date(date(2025,3,20),'jalali')
        report=review_import(self.datasets,self.payload('1404-01-31,100,1404-02-05\n1404-03-31,110,1404-04-05\n'))
        self.assertEqual(report['summary']['gaps'],['2025-05-21'])
        payload=self.payload('1403-12-30,40,1404-01-05\n');payload['frequency']='annual'
        self.assertEqual(review_import(self.datasets,payload)['issue_count'],0)
        payload=self.payload('1404-01-30,100,1404-02-05\n')
        self.assertEqual(review_import(self.datasets,payload)['issue_count'],1)
        payload['calendar']='gregorian'
        self.assertEqual(review_import(self.datasets,payload)['issue_count'],1)
        self.assertEqual(completed_jalali_month(date(2025,4,30)),'2025-04-20')
        self.assertEqual(completed_jalali_month(date(2025,4,19)),'2025-03-20')

    def fx(self,**changes):
        return dict(kind='exchange_rate',currency='USD',market='settlement',side='settlement',
                    amount_unit='toman',quote_quantity=100,**changes)

    def test_fx_conversion_original_values_market_and_quote_quantity(self):
        payload=self.payload('1404-01-31,۹٬۵۰۰٬۰۰۰,1404-02-05\n',factor_details=self.fx())
        review=review_import(self.datasets,payload)
        self.assertEqual(review['issue_count'],0)
        self.assertEqual(review['config']['unit'],'IRR per USD')
        # 9,500,000 toman per 100 USD = 950,000 rial per USD.
        self.assertEqual(review['points'][0]['value'],950_000)
        self.assertEqual(review['points'][0]['original_value'],'۹٬۵۰۰٬۰۰۰')
        self.assertEqual(review['normalization']['value_rule'],'value × 10 ÷ quote quantity')
        saved,body=self.save(payload)
        self.assertEqual(saved,save_import(self.datasets,self.factors,body))
        self.assertEqual(saved['normalization']['factor_details']['market'],'settlement')
        for patch in ({'market':''},{'amount_unit':'rial/toman'},{'side':'guess'},{'quote_quantity':0},{'quote_quantity':True},
                      {'currency':'IRR'},{'currency':'USD/IRR'},{'quote_quantity':'nan'}):
            with self.subTest(patch=patch),self.assertRaises(ValueError):
                review_import(self.datasets,{**payload,'factor_details':{**self.fx(),**patch}})
        for raw in ('0','-1','inf','1e-999','1,2'):
            if raw=='1,2':
                # Comma separates columns in CSV; test numeric parser directly.
                with self.assertRaises(ValueError):numeric(raw)
            else:
                bad=self.payload(f'1404-01-31,{raw},1404-02-05\n',factor_details=self.fx())
                self.assertEqual(review_import(self.datasets,bad)['issue_count'],1)

    def test_inflation_semantics_index_and_negative_change(self):
        for measure,raw,expected in [('cpi_index','۲۴۰٫۵',240.5),('monthly_change','-2',-2),
                                     ('year_on_year','40',40),('annual_average','35',35)]:
            details={'kind':'inflation','measure':measure,**({'base_year':'۱۴۰۰'} if measure=='cpi_index' else {})}
            payload=self.payload(f'1404-01-31,{raw},1404-02-05\n',factor_details=details)
            report=review_import(self.datasets,payload)
            self.assertEqual(report['issue_count'],0)
            self.assertEqual(report['points'][0]['value'],expected)
            self.assertEqual(report['normalization']['value_rule'],'No value conversion')
        with self.assertRaises(ValueError):review_import(self.datasets,{**payload,'factor_details':{'kind':'inflation','measure':'cpi_index'}})
        zero=self.payload('1404-01-31,0,1404-02-05\n',factor_details={'kind':'inflation','measure':'cpi_index','base_year':'1400'})
        self.assertEqual(review_import(self.datasets,zero)['issue_count'],1)

    def test_definition_changes_require_separate_factor_and_new_review(self):
        payload=self.payload('1404-01-31,100,1404-02-05\n',factor_details=self.fx())
        original,body=self.save(payload)
        changed={**body,'factor_details':{**self.fx(),'market':'free_market'}}
        with self.assertRaisesRegex(ValueError,'exact inputs'):save_import(self.datasets,self.factors,changed)
        changed={**payload,'parent_id':original['id'],'factor_details':{**self.fx(),'amount_unit':'rial'}}
        with self.assertRaisesRegex(ValueError,'same calendar'):self.save(changed)
        self.assertEqual(self.factors.get(original['id']),original)
        changed={**payload,'parent_id':original['id'],'publication_timezone':'UTC'}
        with self.assertRaisesRegex(ValueError,'same calendar'):self.save(changed)

    def test_api_metadata_cutoff_and_rejected_conventions(self):
        import app.main as main
        payload=self.payload('1404-01-31,100,1404-02-05\n',factor_details=self.fx())
        with patch.object(main,'DATASET_STORE',self.datasets),patch.object(main,'FACTOR_STORE',self.factors),TestClient(main.app) as client:
            report=client.post('/api/factor-imports/preview',json=payload)
            self.assertEqual(report.status_code,200,report.text)
            saved=client.post('/api/factor-imports',json={**payload,'reviewed':True,'review_token':report.json()['review_token'],'request_id':str(uuid.uuid4())})
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(saved.json()['unit'],'IRR per USD')
            self.assertEqual(saved.json()['calendar'],'jalali')
            cutoff=client.get('/api/factor-imports/'+saved.json()['id']+'/available?cutoff=2025-04-25')
            self.assertEqual(cutoff.json()['points'][0]['value'],10)
            self.assertEqual(client.post('/api/factor-imports/preview',json={**payload,'calendar':'guess'}).status_code,400)

    def test_freshness_uses_observation_end_and_not_latest_import_date(self):
        from app.factor_imports import freshness
        saved,_=self.save(self.payload('1404-01-31,100,1404-02-05\n'))
        self.assertEqual(freshness(saved,today=date(2025,5,1))['status'],'recent')
        result=freshness(saved,today=date(2026,10,3))
        self.assertEqual(result['status'],'behind')
        self.assertEqual(result['latest_period'],'2025-04-20')
        self.assertEqual(result['days_since_last_period'],531)


if __name__=='__main__':unittest.main()
