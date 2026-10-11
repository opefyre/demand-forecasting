"""Local sales → factors → existing orders → grouped models → filtered exports."""
import csv
import unittest
import uuid
import pandas as pd
from tests import test_platform_sales as fixtures


class FullForecastWorkflowTests(unittest.TestCase):
    def test_factors_current_order_book_two_methods_and_exports(self):
        f=fixtures.PublicSalesTests();f.setUp()
        try:
            _,base,_=f.history()
            saved=f.orders(base)
            current=f.get('/datasets/'+base['id']+'/orders')
            book={key:saved['inputs'][key] for key in ('as_of','valid_until','order_feed','orders')}
            f.client.put('/api/v1/datasets/'+base['id']+'/orders',json={**book,'version':current['version']}).raise_for_status()
            dates=pd.date_range(end=pd.Timestamp(f.today.replace(day=1))-pd.Timedelta(days=1),periods=39,freq='ME')
            frame=pd.DataFrame([dict(period=str(d.date()),value=100+i,published=str((d+pd.Timedelta(days=5)).date())) for i,d in enumerate(dates)])
            uploaded=f.client.post('/api/v1/sources',data={'role':'factor_observations'},files={'file':('inflation.csv',frame.to_csv(index=False).encode(),'text/csv')})
            self.assertEqual(uploaded.status_code,201)
            body=dict(source_id=uploaded.json()['id'],name='Iran inflation test index',unit='index points',geography='Iran',provider='Synthetic fixture',frequency='monthly',classification='synthetic_sample',mapping={'period':'A','value':'B','available_at':'C'},request_id=str(uuid.uuid4()))
            review=f.post('/factors/imports/preview',body)
            factor=f.post('/factors/imports',{**body,'review_token':review['review_token'],'reviewed':True},201)
            path='/datasets/'+base['id']+'/factors'
            selection={'snapshot_id':factor['id'],'lag_months':2,'future_value':145,'method':'model:Ridge + drivers'}
            preview=f.post(path+'/preview',selection)
            linked=f.post(path,{**selection,'review_token':preview['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())},201)
            starter=f.get('/datasets/'+linked['id']+'/orders')
            self.assertEqual(starter['inputs']['orders'],book['orders'])
            self.assertEqual({row['customer'] for row in starter['inputs']['customers']},{'Mehr','Aftab','Pars','Negin'})
            orders_path='/datasets/'+linked['id']+'/orders'
            inputs={**starter['inputs'],'reviewed':True,'note':'Customers and current order coverage reviewed.'}
            payload={'inputs':inputs,'request_id':str(uuid.uuid4())}
            receipt=f.post(orders_path+'/preview',payload)
            snapshot=f.post(orders_path+'/snapshots',{**payload,'review_token':receipt['review_token']},201)
            group,_=f.calculate(linked,snapshot,['model:Ridge + drivers','model:Elastic Net + drivers'])
            self.assertEqual(len(group['jobs']),2)
            for job in group['jobs']:
                run=f.get('/runs/'+job['run_id'])
                self.assertEqual(run['forecast_group_id'],group['id'])
                self.assertEqual(run['input_manifest']['settings']['drivers'],linked['settings']['drivers'])
                self.assertEqual(run['input_manifest']['import_provenance']['type'],'forecast_factors')
                for column in linked['settings']['drivers']:
                    self.assertTrue(all(column in row and row[column]>0 for row in run['forecast_rows']))
                    self.assertTrue(any(row[column]==145 for row in run['forecast_rows']))
                outlook=f.get('/runs/'+job['run_id']+'/demand')
                self.assertEqual(len(outlook['rows']),12)
                self.assertEqual(sum(row['booked'] for row in outlook['rows']),20)
                self.assertEqual(sum(row['fulfilled'] for row in outlook['rows']),2)
                for row in outlook['rows']:
                    self.assertAlmostEqual(row['total'],row['booked']+row['fulfilled']+row['remaining'])
                self.assertTrue(all(row['remaining']>0 for row in outlook['rows'] if row['customer']=='Pars'))
                params={'customer':'Aftab','sku':'001','kind':'json','mode':'combined_demand'}
                filtered=f.client.get('/api/v1/runs/'+job['run_id']+'/export',params=params)
                self.assertEqual(filtered.status_code,200)
                rows=filtered.json()
                export=f.client.get('/api/v1/runs/'+job['run_id']+'/export',params={**params,'kind':'csv'})
                csv_rows=list(csv.DictReader(export.content.decode('utf-8-sig').splitlines()))
                self.assertEqual(len(rows),3)
                self.assertEqual({row['sku'] for row in csv_rows},{'001'})
                self.assertEqual([float(row['quantity']) for row in csv_rows],[row['quantity'] for row in rows])
                self.assertAlmostEqual(sum(row['quantity'] for row in rows),sum(row['still_to_serve'] for row in outlook['rows'] if row['customer']=='Aftab' and row['sku']=='001'))
            self.assertEqual(f.ws.datasets.get(base['id'])['settings']['drivers'],[])
        finally:
            f.tearDown()
