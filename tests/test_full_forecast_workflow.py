"""Local sales → factors → existing orders → grouped models → filtered exports."""
import csv
import unittest
import uuid
import math
from io import BytesIO
import pandas as pd
from tests import test_platform_sales as fixtures


class FullForecastWorkflowTests(unittest.TestCase):
    def test_persian_new_customer_commitments_and_orders_are_not_added_twice(self):
        f=fixtures.PublicSalesTests();f.setUp()
        try:
            _,dataset,_=f.history(calendar='jalali')
            snapshot=f.orders(dataset)
            inputs=snapshot['inputs']
            inputs['customers'].append(dict(customer='New Tehran Buyer',sku='001',unit='tonnes',series_id=''))
            inputs['orders'].append(dict(reference='New-1',customer='New Tehran Buyer',sku='001',unit='tonnes',
                due_date=str(f.today),ordered=12,fulfilled=2,cancelled=3,status='confirmed'))
            path='/datasets/'+dataset['id']+'/orders'
            payload={'inputs':inputs,'request_id':str(uuid.uuid4())}
            preview=f.post(path+'/preview',payload)
            self.assertEqual(preview['missing_history'],[{'customer':'New Tehran Buyer','sku':'001'}])
            inputs['commitments']=[dict(customer='New Tehran Buyer',sku='001',unit='tonnes',period=period,
                quantity='15.123456',owner='Planner',reason='Customer confirmed full monthly requirement',
                valid_until=inputs['valid_until']) for period in preview['periods']]
            preview=f.post(path+'/preview',payload)
            self.assertEqual(preview['missing_history'],[])
            self.assertTrue(any(not period.endswith('-01') for period in preview['periods']))
            saved=f.post(path+'/snapshots',{**payload,'review_token':preview['review_token']},201)
            group,_=f.calculate(dataset,saved,['model:Last observed'])
            key=group['jobs'][0]['run_id']
            outlook=f.get('/runs/'+key+'/demand')
            rows=[row for row in outlook['rows'] if row['customer']=='New Tehran Buyer']
            self.assertTrue(outlook['can_export']);self.assertEqual(len(rows),3)
            self.assertTrue(all(row['total']==15.123456 for row in rows))
            self.assertEqual((rows[0]['booked'],rows[0]['fulfilled']),(7,2))
            self.assertAlmostEqual(rows[0]['remaining'],6.123456)
            exported=f.client.get('/api/v1/runs/'+key+'/export',params={'customer':'New Tehran Buyer','kind':'json','mode':'combined_demand'})
            self.assertEqual(exported.status_code,200,exported.text)
            self.assertEqual(exported.json()[0]['quantity'],13.123456)
        finally:f.tearDown()

    def test_short_and_intermittent_history_keep_customer_order_math_and_grouped_results(self):
        for periods,method in [(7,'model:Last observed'),(36,'model:Croston')]:
            with self.subTest(periods=periods,method=method):
                f=fixtures.PublicSalesTests();f.setUp()
                try:
                    _,base,body=f.history()
                    frame=pd.read_csv(BytesIO(f.ws.datasets.source(base['sources']['history'])[1]),dtype={'sku':str})
                    frame=frame.groupby(['customer','sku'],group_keys=False).tail(periods).copy()
                    if periods==36:
                        frame.loc[pd.to_datetime(frame.date).dt.month.mod(3).ne(0),'quantity']=0
                    source=f.ws.datasets.upload('exception-sales.csv',frame.to_csv(index=False).encode(),'history')
                    body={**body,'name':'Short history' if periods==7 else 'Intermittent history',
                        'sources':{'history':source['id']},'parent_dataset_id':base['id'],'request_id':str(uuid.uuid4())}
                    dataset=f.post('/datasets',body,201)
                    snapshot=f.orders(dataset)
                    inputs=snapshot['inputs']
                    inputs['orders'] += [dict(reference='cancelled',customer='Pars',sku='002',unit='tonnes',
                        due_date=str(f.today),ordered=9,fulfilled=0,cancelled=9,status='cancelled'),
                        dict(reference='not-confirmed',customer='Negin',sku='002',unit='tonnes',
                        due_date=str(f.today),ordered=99,fulfilled=0,cancelled=0,status='unconfirmed')]
                    path='/datasets/'+dataset['id']+'/orders'
                    payload={'inputs':inputs,'request_id':str(uuid.uuid4())}
                    review=f.post(path+'/preview',payload)
                    snapshot=f.post(path+'/snapshots',{**payload,'review_token':review['review_token']},201)
                    group,_=f.calculate(dataset,snapshot,[method])
                    outlook=f.get('/runs/'+group['jobs'][0]['run_id']+'/demand')
                    self.assertEqual(len(outlook['rows']),12)
                    self.assertEqual(sum(r['booked'] for r in outlook['rows']),20)
                    self.assertEqual(sum(r['fulfilled'] for r in outlook['rows']),2)
                    self.assertTrue(all(math.isfinite(r['total']) and r['total']>=0 for r in outlook['rows']))
                    self.assertTrue(all(r['booked']==0 for r in outlook['rows'] if r['customer'] in {'Pars','Negin'}))
                    for row in outlook['rows']:
                        self.assertAlmostEqual(row['total'],row['fulfilled']+row['booked']+row['remaining'])
                finally:f.tearDown()

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
