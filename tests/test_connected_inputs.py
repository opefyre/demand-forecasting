"""Synthetic captures, provider HTTP and scheduled permissions; no client calls."""
from copy import deepcopy
from datetime import timedelta
import io,json,socket,unittest,uuid
from unittest.mock import patch,Mock
from concurrent.futures import ThreadPoolExecutor
import csv
import httpx
from app.business_connections import ConnectionInput,ConnectionError,InputFetcher
from app.connection_providers import OdooReader
from app.connection_review import RowReview,accept_rows
from app.connection_schedules import ImportSchedule,configure,tick
from app.order_books import BookRequest
from app.customers import Customer
from tests import test_business_connections as base
config=base.config


class ConnectedRowsTests(unittest.TestCase):
    def setUp(self):
        self.t=base.ConnectionTests();self.t.setUp();self.addCleanup(self.t.tearDown)
        self.f,self.store=self.t.f,self.t.store

    def capture(self,role,payload):
        self.t.fetcher.fetch.return_value=payload
        connection=self.f.post('/connections/inputs',{**config(),'role':role,'template_dataset_id':self.t.dataset['id'] if role=='sales_orders' else None},201)
        candidate=self.t.candidate(self.t.pull(connection))
        return connection,candidate

    def review(self,candidate,body):
        root='/connections/imports/'+candidate['id']+'/rows'
        report=self.f.post(root+'/preview',body)
        return self.f.post(root+'/accept',{**body,'reviewed':True,'review_token':report['review_token']},201)

    def order_file(self):
        rows=[dict(reference='C-'+c,customer=c,sku=sku,unit='tonnes',due_date=str(self.f.today),ordered=qty,fulfilled=0,cancelled=0,status='confirmed')
              for c,sku,qty in [('Mehr','001',30),('Aftab','001',3),('Pars','002',7),('Negin','002',2)]]
        buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
        return buf.getvalue().encode()

    def order_body(self,**changes):
        return dict(mapping=dict(zip(['reference','customer','sku','unit','due_date','ordered','fulfilled','cancelled','status'],'ABCDEFGHI')),
            as_of=str(self.f.today),valid_until=str(self.f.today+timedelta(days=20)),order_mode='changes',order_feed='unknown',**changes)

    def test_connected_customers_are_reviewed_upserts_not_overwrites_or_deletes(self):
        original=self.f.ws.customers.list()
        _,c=self.capture('sales_customers',b'customer,external_id\nMehr,customer-1\nAftab,customer-2\nPars,customer-3\nNegin,customer-4\n')
        self.assertEqual(self.f.ws.customers.list(),original)
        body=dict(mapping={'customer':'A','external_id':'B'})
        result=self.review(c,body)
        self.assertEqual(result['count'],4)
        after=self.f.ws.customers.list();self.assertEqual({r['id'] for r in after},{r['id'] for r in original})
        self.assertTrue(all(r['products'] for r in after))
        self.assertEqual(self.review(c,body),result)
        self.assertEqual(self.f.get('/connections/imports/'+c['id'])['accepted_resource'],result)

    def test_customer_directory_change_invalidates_review_and_alias_collision_is_atomic(self):
        _,c=self.capture('sales_customers',b'customer,external_id\nMehr,customer-1\nAftab,customer-2\n')
        root='/connections/imports/'+c['id']+'/rows';body=dict(mapping={'customer':'A','external_id':'B'})
        report=self.f.post(root+'/preview',body)
        self.f.ws.customers.save([Customer(customer='New buyer')])
        self.f.post(root+'/accept',{**body,'reviewed':True,'review_token':report['review_token']},409)
        self.assertFalse(any(r['external_id'] for r in self.f.ws.customers.list()))

    def test_changed_order_lines_keep_other_orders_and_do_not_claim_complete_coverage(self):
        book=self.f.ws.order_books.get(self.t.dataset['id'])
        self.f.ws.order_books.save(self.t.dataset['id'],BookRequest(version=0,as_of=str(self.f.today),valid_until=str(self.f.today+timedelta(days=20)),
            order_feed='complete_snapshot',orders=[dict(reference='old-line',customer='Mehr',sku='001',unit='tonnes',due_date=str(self.f.today),ordered=1,status='confirmed')]))
        _,c=self.capture('sales_orders',self.order_file());result=self.review(c,self.order_body())
        saved=self.f.ws.order_books.get(self.t.dataset['id'])
        self.assertEqual(len(saved['inputs']['orders']),5);self.assertEqual(saved['inputs']['order_feed'],'unknown')
        self.assertEqual(result['provenance']['source_sha256'],c['digest'])
        self.assertEqual(self.review(c,self.order_body()),result)

    def test_complete_connected_order_book_reaches_grouped_forecast_without_double_counting(self):
        _,c=self.capture('sales_orders',self.order_file())
        body={**self.order_body(),'order_mode':'replace','order_feed':'complete_snapshot'}
        self.review(c,body)
        inputs=deepcopy(self.f.ws.order_books.get(self.t.dataset['id'])['inputs']);inputs.update(reviewed=True,note='Synthetic connected order review.')
        path='/datasets/'+self.t.dataset['id']+'/orders';request={'inputs':inputs,'request_id':str(uuid.uuid4())}
        preview=self.f.post(path+'/preview',request)
        snapshot=self.f.post(path+'/snapshots',{**request,'review_token':preview['review_token']},201)
        group,_=self.f.calculate(self.t.dataset,snapshot,['model:Last observed'])
        outlook=self.f.get('/runs/'+group['jobs'][0]['run_id']+'/demand')
        self.assertEqual({r['customer'] for r in outlook['rows']},{'Mehr','Aftab','Pars','Negin'})
        self.assertTrue(outlook['can_export']);self.assertEqual(len(snapshot['inputs']['orders']),4)

    def test_order_coverage_empty_replacement_duplicate_invalid_units_and_stale_review_block(self):
        _,c=self.capture('sales_orders',self.order_file())
        root='/connections/imports/'+c['id']+'/rows'
        self.f.post(root+'/preview',{**self.order_body(),'order_feed':'complete_snapshot'},400)
        body=self.order_body();report=self.f.post(root+'/preview',body)
        book=self.f.ws.order_books.get(self.t.dataset['id'])
        self.f.ws.order_books.save(self.t.dataset['id'],BookRequest(version=book['version'],as_of=str(self.f.today),valid_until=str(self.f.today+timedelta(days=2)),order_feed='unknown',orders=[]))
        self.f.post(root+'/accept',{**body,'reviewed':True,'review_token':report['review_token']},409)
        for bad in [self.order_file().replace(b'tonnes',b'kg'),self.order_file()+self.order_file().splitlines()[1]+b'\n',self.order_file().replace(b'confirmed',b'guess')]:
            _,invalid=self.capture('sales_orders',bad)
            self.f.post('/connections/imports/'+invalid['id']+'/rows/preview',body,400)
        header=self.order_file().splitlines()[0]+b'\n';_,empty=self.capture('sales_orders',header)
        self.f.post('/connections/imports/'+empty['id']+'/rows/preview',{**body,'order_mode':'replace'},400)
        report=self.f.post('/connections/imports/'+empty['id']+'/rows/preview',{**body,'order_mode':'replace','confirm_empty':True})
        self.assertEqual(report['count'],0)

    def test_codes_resolve_only_owned_customers_and_persian_dates_are_explicit(self):
        from persiantools.jdatetime import JalaliDate
        buyer=next(r for r in self.f.ws.customers.list() if r['customer']=='Mehr')
        self.f.ws.customers.save([Customer(customer='Mehr',products=buyer['products'],external_id='odoo:1:10')],buyer['id'])
        payload=self.order_file().replace(b',Mehr,',b',odoo:1:10,').replace(str(self.f.today).encode(),str(JalaliDate(self.f.today)).encode())
        _,c=self.capture('sales_orders',payload)
        report=self.f.post('/connections/imports/'+c['id']+'/rows/preview',{**self.order_body(),'calendar':'jalali'})
        self.assertEqual(report['rows'][0]['customer'],'Mehr');self.assertEqual(report['rows'][0]['due_date'],str(self.f.today))
        self.f.company='tehran_b'
        self.assertEqual(self.f.client.post('/api/v1/connections/imports/'+c['id']+'/rows/preview',json=self.order_body()).status_code,404)

    def test_capture_receipt_interruption_cannot_apply_customers_twice(self):
        _,c=self.capture('sales_customers',b'customer\nBuyer one\nBuyer two\nBuyer three\nBuyer four\n')
        body=RowReview(mapping={'customer':'A'})
        report=self.f.post('/connections/imports/'+c['id']+'/rows/preview',body.model_dump(mode='json'))
        body=body.model_copy(update={'reviewed':True,'review_token':report['review_token']})
        candidate=self.store.candidate(c['id'])
        with patch.object(self.store,'db',side_effect=RuntimeError('Synthetic interruption')):
            with self.assertRaises(RuntimeError):accept_rows(self.f.ws,candidate,body)
        self.assertEqual(len(self.f.ws.customers.list()),8)
        result=accept_rows(self.f.ws,candidate,body)
        self.assertEqual(result['count'],4);self.assertEqual(len(self.f.ws.customers.list()),8)

    def test_restricted_customer_scope_can_review_customer_sources_but_not_orders(self):
        _,c=self.capture('sales_customers',b'customer\nNew buyer\n')
        self.f.permissions=['connections:read','connections:sync','customers:read','customers:write']
        self.f.post('/sources/'+c['source_id']+'/preview',dict(header_row=1))
        self.review(c,dict(mapping={'customer':'A'}))
        self.f.permissions.remove('customers:write')
        self.f.post('/connections/imports/'+c['id']+'/rows/preview',dict(mapping={'customer':'A'}),403)

    def test_schedule_claims_only_once_and_never_accepts_or_runs_forecasts(self):
        connection=self.t.create();owner=json.dumps([self.f.company,'https://company.test','admin'])
        schedule=configure(self.store,connection['id'],ImportSchedule(connection_version=1,enabled=True,confirmed=True,minutes=60),owner)
        now=schedule['next_due']+1
        with ThreadPoolExecutor(2) as pool:results=list(pool.map(lambda _:tick(self.store,lambda _:True,now=now),range(2)))
        self.t.fetcher.fetch.assert_called_once()
        self.assertEqual(len(self.f.ws.datasets.list()),1);self.assertEqual(self.f.dispatched,[])
        latest=self.store.get(connection['id']);self.assertEqual(latest['pulls'][0]['state'],'ready')
        self.assertIsNone(latest['pulls'][0]['accepted_dataset_id'])

    def test_revoked_schedule_permissions_and_config_changes_pause_before_network(self):
        connection=self.t.create();body=ImportSchedule(connection_version=1,enabled=True,confirmed=True)
        schedule=configure(self.store,connection['id'],body,'owner')
        tick(self.store,lambda _:False,now=schedule['next_due']+1);self.t.fetcher.fetch.assert_not_called()
        self.assertFalse(self.store.get(connection['id'])['schedule']['enabled'])
        configure(self.store,connection['id'],body.model_copy(update={'version':1}),'owner')
        self.store.save(ConnectionInput(**{**config(),'name':'Changed'}),connection['id'],1)
        tick(self.store,lambda _:True,now=10**12);self.t.fetcher.fetch.assert_not_called()

    def test_schedule_revoked_during_fetch_discards_capture_and_schedule_api_is_admin_only(self):
        connection=self.t.create();schedule=configure(self.store,connection['id'],ImportSchedule(connection_version=1,enabled=True,confirmed=True),'owner')
        allowed=[True]
        def fetched(*args):allowed[0]=False;return self.t.payload
        self.t.fetcher.fetch.side_effect=fetched
        tick(self.store,lambda _:allowed[0],now=schedule['next_due']+1)
        self.assertEqual(self.store.get(connection['id'])['pulls'][0]['state'],'failed')
        self.assertEqual(len(self.f.ws.datasets.list_sources()),1)
        self.f.role='planner'
        self.assertEqual(self.f.client.put('/api/v1/connections/inputs/'+connection['id']+'/schedule',json={'version':0,'connection_version':1,'confirmed':True}).status_code,403)

    def test_schedule_api_versions_owner_redaction_pause_and_foreign_company(self):
        connection=self.t.create();self.f.role='admin'
        root='/connections/inputs/'+connection['id']+'/schedule'
        body=dict(version=0,connection_version=1,minutes=60,enabled=True,confirmed=True)
        scheduled=self.f.client.put('/api/v1'+root,json=body)
        self.assertEqual(scheduled.status_code,200,scheduled.text)
        self.assertNotIn('owner',scheduled.json());self.assertNotIn('owner',self.store.get(connection['id'])['schedule'])
        self.assertEqual(self.f.client.put('/api/v1'+root,json=body).status_code,409)
        self.f.company='tehran_b'
        self.assertEqual(self.f.client.put('/api/v1'+root,json=body).status_code,404)
        self.f.company='tehran_a'
        paused=self.f.client.request('DELETE','/api/v1'+root,json={'version':1})
        self.assertEqual(paused.status_code,200,paused.text);self.assertFalse(paused.json()['enabled'])
        tick(self.store,lambda _:True,now=10**12);self.t.fetcher.fetch.assert_not_called()

    def test_schedule_pause_during_network_discards_new_capture(self):
        connection=self.t.create();schedule=configure(self.store,connection['id'],ImportSchedule(connection_version=1,enabled=True,confirmed=True),'owner')
        def fetched(*args):
            configure(self.store,connection['id'],ImportSchedule(version=1,connection_version=1,enabled=False,confirmed=True),'owner')
            return self.t.payload
        self.t.fetcher.fetch.side_effect=fetched
        tick(self.store,lambda _:True,now=schedule['next_due']+1)
        self.assertFalse(self.store.get(connection['id'])['schedule']['enabled'])
        self.assertEqual(self.store.get(connection['id'])['pulls'][0]['state'],'failed')
        self.assertEqual(len(self.f.ws.datasets.list_sources()),1)

    def test_explicit_inactive_customer_does_not_delete_other_buyers_or_links(self):
        original=self.f.ws.customers.list()
        _,candidate=self.capture('sales_customers',b'customer,active\nMehr,false\n')
        self.review(candidate,dict(mapping={'customer':'A','active':'B'}))
        after=self.f.ws.customers.list()
        self.assertEqual(len(after),4)
        buyer=next(r for r in after if r['customer']=='Mehr')
        self.assertFalse(buyer['active']);self.assertEqual(buyer['products'],next(r for r in original if r['customer']=='Mehr')['products'])


class ProviderTests(unittest.TestCase):
    def network(self,reply):
        fetcher=InputFetcher(transport=httpx.MockTransport(reply))
        fetcher.policy.resolve=lambda host,port:(socket.AF_INET,socket.SOCK_STREAM,6,'',('8.8.8.8',443))
        return fetcher

    def test_google_official_auth_uses_fixed_token_target_readonly_scope_and_full_worksheet(self):
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        key=rsa.generate_private_key(public_exponent=65537,key_size=2048)
        secret=json.dumps(dict(type='service_account',client_email='fixture@synthetic.iam.gserviceaccount.com',token_uri='http://169.254.169.254/',
            private_key=key.private_bytes(serialization.Encoding.PEM,serialization.PrivateFormat.PKCS8,serialization.NoEncryption()).decode()))
        calls=[]
        def reply(req):
            calls.append(req)
            if req.headers['host']=='oauth2.googleapis.com':return httpx.Response(200,json={'access_token':'synthetic-token','expires_in':3600,'token_type':'Bearer'})
            return httpx.Response(200,json={'values':[['customer','qty'],['Mehr','15'],['Pars','4']]})
        cfg=ConnectionInput(**{**config(),'provider':'sheets','url':'','spreadsheet_id':'synthetic_sheet_123','sheet_range':'Sales'}).public_config()
        payload=self.network(reply).fetch(cfg,secret)
        self.assertIn(b'Mehr,15',payload);self.assertEqual(len(calls),2)
        self.assertEqual(calls[0].headers['host'],'oauth2.googleapis.com');self.assertIn(b'assertion=',calls[0].content)
        from urllib.parse import parse_qs
        import base64
        jwt=parse_qs(calls[0].content.decode())['assertion'][0].split('.')[1]
        claims=json.loads(base64.urlsafe_b64decode(jwt+'='*((4-len(jwt)%4)%4)))
        self.assertEqual(claims['scope'],'https://www.googleapis.com/auth/spreadsheets.readonly');self.assertNotIn('sub',claims)
        self.assertIn('/values/%27Sales%27',str(calls[1].url));self.assertEqual(calls[1].method,'GET')

    def odoo_config(self,version='odoo19',role='sales_customers'):
        return ConnectionInput(**{**config(),'provider':version,'role':role,'filename':'sales.json','url':'https://odoo.example',
            'database':'client','username':'readonly' if version=='odoo18' else '',
            'template_dataset_id':'a'*32 if role=='sales_orders' else None}).public_config()

    def test_odoo18_and19_use_only_read_api_and_selected_company_context(self):
        for version in ['odoo18','odoo19']:
            calls=[]
            def reply(req):
                calls.append(req);data=json.loads(req.content)
                if version=='odoo18':
                    args=data['params']['args']
                    if data['params']['service']=='common':return httpx.Response(200,json={'result':7})
                    self.assertEqual(args[4],'search_read');self.assertEqual(args[3],'res.partner');kw=args[6]
                else:
                    self.assertTrue(req.url.path.endswith('/res.partner/search_read'));self.assertEqual(req.headers['x-odoo-database'],'client');kw=data
                self.assertEqual(kw['context']['allowed_company_ids'],[1]);self.assertEqual(kw['context']['active_test'],False)
                records=[dict(id=10,name='Mehr',active=True,write_date='2026-10-01')]
                return httpx.Response(200,json={'result':records} if version=='odoo18' else records)
            result=json.loads(self.network(reply).fetch(self.odoo_config(version),'synthetic-test-key'))
            self.assertEqual(result[0]['external_id'],'odoo:1:10');self.assertEqual(len(calls),3 if version=='odoo18' else 2)

    def test_odoo_pagination_drift_and_partial_data_fail_closed(self):
        reader=OdooReader.__new__(OdooReader)
        reader.page=Mock(side_effect=[[{'id':i} for i in range(1,1001)],[{'id':1001}]])
        self.assertEqual(len(reader.records('res.partner',[],['id'])),1001)
        reader.page=Mock(return_value=[{'id':2},{'id':1}])
        with self.assertRaises(ConnectionError):reader.records('res.partner',[],['id'])
        counter=[0]
        def reply(req):counter[0]+=1;return httpx.Response(200,json=[dict(id=1,name='Changed'+str(counter[0]),active=True)])
        with self.assertRaises(ConnectionError):self.network(reply).fetch(self.odoo_config(),'synthetic-test-key')

    def test_odoo_orders_preserve_delivery_units_unique_refs_and_cancellation_math(self):
        for version in ['odoo18','odoo19']:
            uom='product_uom_id' if version=='odoo19' else 'product_uom'
            snapshot={'orders':[dict(id=20,name='SO20',partner_id=[10,'Mehr'],commitment_date='2026-10-09 12:00:00',state='cancel')],
                'partners':[dict(id=10,name='Mehr')],'products':[dict(id=30,default_code='001')],'units':[dict(id=1,name='tonnes')],
                'lines':[dict(id=40,order_id=[20,'SO20'],product_id=[30,'Product'],product_uom_qty=12,qty_delivered=3,**{uom:[1,'tonnes']})]}
            from app.connection_providers import odoo
            with patch.object(OdooReader,'__init__',return_value=None),patch.object(OdooReader,'snapshot',return_value=snapshot):
                rows=json.loads(odoo(None,self.odoo_config(version,'sales_orders'),'synthetic-test-key'))
            self.assertEqual(rows[0]['cancelled'],'9');self.assertEqual(rows[0]['fulfilled'],3);self.assertEqual(rows[0]['reference'],'odoo:1:20:40')
            snapshot['orders'][0]['commitment_date']='2026-10-09 23:00:00'
            snapshot['lines'][0].update(product_uom_qty=0.3,qty_delivered=0.1)
            with patch.object(OdooReader,'__init__',return_value=None),patch.object(OdooReader,'snapshot',return_value=snapshot):
                row=json.loads(odoo(None,self.odoo_config(version,'sales_orders'),'synthetic-test-key'))[0]
            self.assertEqual(row['due_date'],'2026-10-10');self.assertEqual(row['cancelled'],'0.2')
            snapshot['orders'][0]['commitment_date']=False
            with patch.object(OdooReader,'__init__',return_value=None),patch.object(OdooReader,'snapshot',return_value=snapshot):
                with self.assertRaises(ConnectionError):odoo(None,self.odoo_config(version,'sales_orders'),'synthetic-test-key')

    def test_google_and_odoo_errors_never_echo_keys_and_destination_changes_need_new_key(self):
        for cfg in [self.odoo_config()]:
            with self.assertRaises(ConnectionError) as failure:
                self.network(lambda req:httpx.Response(401,text='synthetic-test-key')).fetch(cfg,'synthetic-test-key')
            self.assertNotIn('synthetic-test-key',str(failure.exception))
        for values in [dict(provider='sheets',url='',spreadsheet_id='synthetic_sheet_123',sheet_range='Sales!A1:B10'),
                       dict(provider='odoo19',role='history',url='https://odoo.example',database='db')]:
            with self.assertRaises(ValueError):ConnectionInput(**{**config(),**values})

    def test_odoo_order_http_joins_versioned_fields_and_keeps_product_ids(self):
        for version in ['odoo18','odoo19']:
            uom='product_uom_id' if version=='odoo19' else 'product_uom'
            data={
                'sale.order':[dict(id=20,name='SO20',partner_id=[10,'Mehr'],commitment_date='2026-11-01 22:00:00',state='sale',write_date='stamp')],
                'sale.order.line':[dict(id=40,order_id=[20,'SO20'],product_id=[30,'Product'],product_uom_qty=12,qty_delivered=3,write_date='stamp',**{uom:[1,'tonnes']})],
                'res.partner':[dict(id=10,name='Mehr',active=True,write_date='stamp')],
                'product.product':[dict(id=30,default_code='001',write_date='stamp')],
                'uom.uom':[dict(id=1,name='tonnes',write_date='stamp')]}
            calls=[]
            def reply(req):
                payload=json.loads(req.content)
                if version=='odoo18':
                    args=payload['params']['args']
                    if payload['params']['service']=='common':return httpx.Response(200,json={'result':7})
                    model,method,kw=args[3],args[4],args[6];self.assertEqual(method,'search_read')
                else:model=req.url.path.split('/')[3];kw=payload
                calls.append(model)
                self.assertEqual(kw['context']['allowed_company_ids'],[1])
                self.assertEqual(kw['order'],'id asc')
                if model=='sale.order.line':self.assertIn(uom,kw['fields'])
                return httpx.Response(200,json={'result':data[model]} if version=='odoo18' else data[model])
            rows=json.loads(self.network(reply).fetch(self.odoo_config(version,'sales_orders'),'synthetic-test-key'))
            self.assertEqual(len(calls),10);self.assertEqual(rows[0]['due_date'],'2026-11-02')
            self.assertEqual(rows[0]['customer'],'odoo:1:10');self.assertEqual(rows[0]['sku'],'001')
            self.assertEqual(rows[0]['fulfilled'],3);self.assertEqual(rows[0]['cancelled'],'0')
            data['product.product'].append(dict(id=31,default_code='001',write_date='stamp'))
            with self.assertRaises(ConnectionError):self.network(reply).fetch(self.odoo_config(version,'sales_orders'),'synthetic-test-key')
