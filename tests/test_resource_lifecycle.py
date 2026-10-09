"""Real public routes and engine fixtures; no client data or provider calls."""
import unittest
import uuid
import json
from concurrent.futures import ThreadPoolExecutor
from tests import test_platform_sales as base
from app.resource_lifecycle import MetadataConflict
from app.company_jobs import execute_company_job


class ResourceLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.f=base.PublicSalesTests();self.f.setUp()
        self.source,self.dataset,_=self.f.history()

    def tearDown(self):self.f.tearDown()

    def update(self,kind,key,version=0,name='October sales'):
        return self.f.client.patch(f'/api/v1/{kind}/{key}/metadata',json=dict(version=version,name=name))

    def archive(self,kind,key,version=0):
        return self.f.post(f'/{kind}/{key}/archive',dict(version=version))

    def test_names_are_presentation_only_and_original_files_unchanged(self):
        before={p.name:p.read_bytes() for p in self.f.ws.datasets.root.iterdir()}
        for kind,row in [('sources',self.source),('datasets',self.dataset)]:
            self.assertEqual(self.update(kind,row['id']).status_code,200)
            value=self.f.get(f'/{kind}/{row["id"]}')
            self.assertEqual(value['name'],'October sales')
            self.assertEqual(value['original_name'],row['name'])
            self.assertEqual(self.update(kind,row['id']).status_code,409)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.f.ws.datasets.root.iterdir()})

    def test_archive_restore_lists_and_direct_revision_access(self):
        row=self.archive('datasets',self.dataset['id'])
        self.assertTrue(row['lifecycle']['archived'])
        self.assertEqual(self.f.get('/datasets')['total'],0)
        self.assertEqual(self.f.get('/datasets?include_archived=true')['total'],1)
        self.assertEqual(len(self.f.get('/datasets/'+self.dataset['id']+'/revisions')['revisions']),1)
        self.f.post('/datasets/'+self.dataset['id']+'/restore',dict(version=1))
        self.assertEqual(self.f.get('/datasets')['total'],1)
        self.archive('sources',self.source['id'])
        self.assertEqual(self.f.get('/sources')['total'],0)
        self.assertEqual(self.f.get('/sources?include_archived=true')['total'],1)

    def test_company_cannot_read_or_change_other_company_resources(self):
        self.f.company='tehran_b'
        for kind,row in [('datasets',self.dataset),('sources',self.source)]:
            for suffix in ('metadata','revisions'):
                self.assertEqual(self.f.client.get(f'/api/v1/{kind}/{row["id"]}/{suffix}').status_code,404)
            self.assertEqual(self.update(kind,row['id']).status_code,404)
        self.assertEqual(self.f.get('/datasets')['total'],0)

    def test_scopes_and_version_validation(self):
        self.f.permissions=['inputs:read']
        self.assertEqual(self.update('datasets',self.dataset['id']).status_code,403)
        self.f.get('/datasets/'+self.dataset['id']+'/metadata')
        self.f.permissions=base.ALL.copy()
        for body in (dict(version=True,name='Name'),dict(version=-1,name='Name'),dict(version=0,name=' '),dict(version=0,name='Name',company_id='other')):
            response=self.f.client.patch('/api/v1/datasets/'+self.dataset['id']+'/metadata',json=body)
            self.assertEqual(response.status_code,422,response.text)

    def test_concurrent_edits_have_one_winner(self):
        store=self.f.ws.lifecycle
        def edit(index):
            try:store.update('datasets',self.dataset['id'],0,name=str(index));return 'saved'
            except MetadataConflict:return 'conflict'
        with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(edit,range(2)))
        self.assertEqual(sorted(results),['conflict','saved'])
        self.assertEqual(store.get('datasets',self.dataset['id'])['version'],1)

    def test_dataset_versions_include_branches_not_unrelated_inputs(self):
        root=self.dataset
        children=[self.f.ws.datasets.save('Revision '+str(i),root['sources'],{**root['settings'],'horizon':4+i},
                  root['classification'],True,parent_dataset_id=root['id']) for i in range(2)]
        self.f.ws.datasets.save('Unrelated',root['sources'],root['settings'],root['classification'],True)
        self.archive('datasets',root['id'])
        rows=self.f.get('/datasets/'+children[0]['id']+'/revisions')['revisions']
        self.assertEqual({r['id'] for r in rows},{root['id'],*(c['id'] for c in children)})
        self.assertEqual({r['parent_id'] for r in rows},{None,root['id']})

    def test_archived_inputs_block_new_forecasts_not_saved_outputs(self):
        snapshot=self.f.orders(self.dataset)
        group,body=self.f.calculate(self.dataset,snapshot)
        run_id=group['jobs'][0]['run_id']
        evidence=self.f.ws.load_run(run_id)
        for kind,key in [('datasets',self.dataset['id']),('sources',self.source['id'])]:
            self.archive(kind,key)
            response=self.f.client.post('/api/v1/forecasts',json={**body,'request_id':str(uuid.uuid4())})
            self.assertEqual(response.status_code,400,response.text)
            self.assertEqual(self.f.get('/runs/'+run_id)['run_id'],run_id)
            self.assertEqual(self.f.client.get('/api/v1/runs/'+run_id+'/files/csv').status_code,200)
            self.f.post(f'/{kind}/{key}/restore',dict(version=1))
        self.assertEqual(evidence,self.f.ws.load_run(run_id))

    def test_pending_group_archive_blocked_and_worker_rechecks_inputs(self):
        snapshot=self.f.orders(self.dataset)
        group=self.f.post('/forecasts',dict(name='Pending',dataset_id=self.dataset['id'],sales_input_id=snapshot['id'],
               methods=['model:Last observed'],request_id=str(uuid.uuid4())),202)
        self.f.post('/forecasts/'+group['id']+'/archive',dict(version=0),409)
        self.archive('datasets',self.dataset['id'])
        execute_company_job(self.f.ws,group['jobs'][0]['id'])
        self.assertEqual(self.f.get('/jobs/'+group['jobs'][0]['id'])['state'],'failed')

    def test_group_name_archive_and_restore_preserve_all_method_evidence(self):
        group,body=self.f.calculate(self.dataset,self.f.orders(self.dataset))
        hashes={j['run_id']:(self.f.ws.runs/j['run_id']/'result.json').read_bytes() for j in group['jobs']}
        self.assertEqual(self.update('forecasts',group['id'],name='Tehran November').status_code,200)
        rows=self.f.get('/runs')['runs'];self.assertEqual({r['forecast_name'] for r in rows},{'Tehran November'})
        self.archive('forecasts',group['id'],1)
        self.assertEqual(self.f.get('/runs')['total'],0)
        self.assertEqual(self.f.get('/forecasts')['total'],0)
        self.assertEqual(self.f.get('/runs?include_archived=true')['total'],2)
        alias=self.f.get('/runs/'+group['jobs'][0]['run_id']+'/metadata')
        self.assertEqual(alias['id'],group['id'])
        self.f.post('/runs/'+group['jobs'][0]['run_id']+'/restore',dict(version=2))
        self.assertEqual(self.f.get('/runs')['total'],2)
        for key,value in hashes.items():self.assertEqual((self.f.ws.runs/key/'result.json').read_bytes(),value)
        self.assertEqual(self.f.post('/forecasts',body,202)['id'],group['id'])

    def test_explicit_forecast_revisions_and_foreign_parent_rejected(self):
        parent,body=self.f.calculate(self.dataset,self.f.orders(self.dataset))
        child=self.f.post('/forecasts',{**body,'name':'Revised demand','parent_forecast_id':parent['id'],
              'request_id':str(uuid.uuid4())},202)
        for job in child['jobs']:
            execute_company_job(self.f.ws,job['id'])
            self.assertEqual(self.f.get('/jobs/'+job['id'])['state'],'succeeded')
        rows=self.f.get('/forecasts/'+child['id']+'/revisions')['revisions']
        self.assertEqual({r['id'] for r in rows},{parent['id'],child['id']})
        self.assertEqual(next(r['parent_id'] for r in rows if r['id']==child['id']),parent['id'])
        self.f.company='tehran_b'
        _,dataset,_=self.f.history();snapshot=self.f.orders(dataset)
        self.f.post('/forecasts',{**body,'dataset_id':dataset['id'],'sales_input_id':snapshot['id'],
          'parent_forecast_id':parent['id'],'request_id':str(uuid.uuid4())},404)

    def test_viewer_cannot_discover_draft_names_or_revision_ids(self):
        group,_=self.f.calculate(self.dataset,self.f.orders(self.dataset))
        self.f.permissions=['reports:read'];self.f.role='viewer'
        for kind,key in [('forecasts',group['id']),('runs',group['jobs'][0]['run_id'])]:
            for suffix in ['metadata','revisions']:
                self.assertEqual(self.f.client.get(f'/api/v1/{kind}/{key}/{suffix}').status_code,404)
            self.assertEqual(self.update(kind,key).status_code,403)

    def test_monthly_results_link_back_to_their_grouped_baseline(self):
        group,_=self.f.calculate(self.dataset,self.f.orders(self.dataset))
        baseline=group['jobs'][0]['run_id']
        # Navigation-only fixture, not a claim of mathematical acceptance.
        value=self.f.ws.load_run(baseline)
        key='b'*12
        for field in ['job_id','job_owner','forecast_group_id','forecast_name']:value.pop(field,None)
        value.update(run_id=key,base_run_id=baseline,dataset_name='Monthly update')
        folder=self.f.ws.runs/key;folder.mkdir();(folder/'result.json').write_text(json.dumps(value))
        for kind,identifier in [('forecasts',group['id']),('runs',key)]:
            rows=self.f.get(f'/{kind}/{identifier}/revisions')['revisions']
            self.assertEqual({r['id'] for r in rows},{group['id'],key})
            self.assertEqual(next(r['parent_id'] for r in rows if r['id']==key),group['id'])

    def test_source_permissions_follow_its_role(self):
        source=self.f.ws.datasets.upload('customers.csv',b'customer\nMehr\n','sales_customers')
        self.f.permissions=['inputs:read','inputs:write']
        self.assertEqual(self.update('sources',source['id']).status_code,403)
        self.f.permissions=['customers:read','customers:write']
        self.assertEqual(self.update('sources',source['id']).status_code,200)
        self.assertEqual(self.update('datasets',self.dataset['id']).status_code,403)

    def test_approved_viewer_reads_only_approved_revision_metadata(self):
        group,_=self.f.calculate(self.dataset,self.f.orders(self.dataset))
        key=group['jobs'][0]['run_id'];snapshot=self.f.ws.load_run(key)['sales_input_snapshot_id']
        body=dict(snapshot_id=snapshot,receiver='ERP',mode='combined_demand',request_id='lifecycle-release')
        report=self.f.post('/releases/preview',body)
        record=self.f.post('/releases',{**body,'review_token':report['review_token'],'reviewed':True},201)
        self.f.role='approver';self.f.subject='independent_reviewer'
        self.f.post('/releases/'+record['id']+'/approve',dict(reviewed=True,review_token=record['report']['review_token']))
        self.assertEqual(self.update('forecasts',group['id'],name='Approved autumn').status_code,200)
        self.archive('forecasts',group['id'],1)
        self.f.role='viewer';self.f.permissions=['reports:read']
        self.assertEqual(self.f.get('/runs/'+key+'/metadata')['name'],'Approved autumn')
        rows=self.f.get('/forecasts/'+group['id']+'/revisions')['revisions']
        self.assertEqual(len(rows),1);self.assertEqual(rows[0]['run_id'],key)
        self.assertTrue(rows[0]['lifecycle']['archived'])

    def test_retry_is_part_of_archive_guard_and_revision_navigation(self):
        snapshot=self.f.orders(self.dataset)
        group=self.f.post('/forecasts',dict(name='Retry fixture',dataset_id=self.dataset['id'],sales_input_id=snapshot['id'],
              methods=['model:Last observed'],request_id='lifecycle-retry-group'),202)
        old=group['jobs'][0]
        self.f.ws.jobs.cancel(old['id']);execute_company_job(self.f.ws,old['id'])
        retry=self.f.ws.jobs.create(old['payload'],old['name'],'lifecycle-retry-job',retry_of=old['id'])
        self.f.post('/forecasts/'+group['id']+'/archive',dict(version=0),409)
        execute_company_job(self.f.ws,retry['id'])
        key=self.f.ws.jobs.get(retry['id'])['run_id'];self.assertIsNotNone(key)
        rows=self.f.get('/forecasts/'+group['id']+'/revisions')['revisions']
        self.assertEqual(rows[0]['run_id'],key)
