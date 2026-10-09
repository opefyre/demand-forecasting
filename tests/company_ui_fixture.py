"""Loopback-only disposable UI acceptance fixture. Never deploy this test server.

Uses real company stores/API/models with synthetic data and mocked identity/AI.
Authentication itself is covered by the separate Node/PostgreSQL roundtrip suite.
Run: .venv/bin/python -m tests.company_ui_fixture
"""
from pathlib import Path
from unittest.mock import AsyncMock,patch
from fastapi import Request,HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from tests.test_platform_sales import PublicSalesTests
from tests.test_company_context import ALL,VIEW
from app.company_jobs import execute_company_job


def run(*,notifications=False):
    import uvicorn
    fixture=PublicSalesTests();fixture.setUp()
    if notifications:
        from types import SimpleNamespace
        from app.platform_api import create_platform_api
        from app.notifications import Notifications
        from app.company_context import personal_owner
        from tests.test_notifications import MemoryVault,Sender,body
        fixture.kind='session'
        class IdentityFixture:
            config=SimpleNamespace(origin='http://127.0.0.1:8013')
            async def call(self,operation,values):
                if operation=='schedules/authorize':return {'allowed':True}
                return {'members':[],'keys':[],'invitations':[]}
        fixture.app.router.routes=[r for r in fixture.app.router.routes if getattr(r,'path',None)!='/api/v1']
        fixture.api=create_platform_api(IdentityFixture(),fixture.workspaces,dispatcher=lambda ws,key:fixture.dispatched.append((ws.company_id,key)))
        fixture.app.mount('/api/v1',fixture.api)
        for company in ('tehran_a','tehran_b'):
            w=fixture.workspaces.for_principal({'company_id':company})
            sender=Sender();store=Notifications(w.path('notifications.sqlite3'),vault=MemoryVault(),sender=sender)
            w._stores['notifications']=store
            owner=personal_owner({'company_id':company,'issuer':'https://company.test','subject':'admin_'+company})
            destination=store.save(body(enabled=True,events=['forecast_ready','inputs_ready']),owner)
            for state in ('accepted','rejected','unknown'):
                sender.state=state;store.queue(destination['id'],'test','fixture-'+state,owner,version=1);store.drain(lambda _:True,'http://127.0.0.1:8013')
            sender.state='accepted'
    root=Path(__file__).resolve().parents[1]
    for company,multiplier in [('tehran_a',1),('tehran_b',2)]:
        fixture.company=company
        _,dataset,_=fixture.history(multiplier)
        snapshot=fixture.orders(dataset)
        fixture.calculate(dataset,snapshot)
    fixture.company='tehran_a';fixture.permissions=ALL.copy();fixture.role='planner'
    # Business input pulls use a synthetic in-memory remote, never a real account.
    from app.business_connections import BusinessConnections,ConnectionInput
    class ExportFixture:
        def __init__(self,payload,multiplier):self.payload,self.multiplier=payload,multiplier
        def fetch(self,config,credential):
            if config['url']!='https://erp.example/sales/export':
                raise ValueError('Only the synthetic fixture export is available.')
            if config['role']=='sales_customers':return b'customer,external_id,active\nMehr,buyer-1,true\nAftab,buyer-2,true\nPars,buyer-3,true\nNegin,buyer-4,true\n'
            if config['role']=='sales_orders':
                rows=['reference,customer,sku,unit,due_date,ordered,fulfilled,cancelled,status']
                for name,sku,qty,status in [('Mehr','001',30,'confirmed'),('Aftab','001',3,'confirmed'),('Pars','002',7,'unconfirmed'),('Negin','002',2,'confirmed')]:
                    rows.append(f'Connected-{name},{name},{sku},tonnes,{fixture.today},{qty*self.multiplier},0,0,{status}')
                return ('\n'.join(rows)+'\n').encode()
            return self.payload
    for company in ['tehran_a','tehran_b']:
        workspace=fixture.workspaces.for_principal({'company_id':company})
        dataset=workspace.datasets.list()[0]
        payload=workspace.datasets.source(dataset['sources']['history'])[1]
        workspace._stores['connections']=BusinessConnections(workspace.path('connections.sqlite3'),workspace.datasets,
            fetcher=ExportFixture(payload,1 if company=='tehran_a' else 2))
        store=workspace.connections
        connected=store.save(ConnectionInput(name='Tehran sales export' if company=='tehran_a' else 'Second company sales export',
            provider='http',role='history',filename='sales.csv',url='https://erp.example/sales/export',
            template_dataset_id=dataset['id'],confirmed_read_access=True))
        store.pull(connected['id'],'synthetic-browser-seed')
        for role,name in [('sales_customers','Customer directory'),('sales_orders','Customer orders')]:
            connection=store.save(ConnectionInput(name=name,provider='http',role=role,filename=role+'.csv',
                url='https://erp.example/sales/export',template_dataset_id=dataset['id'] if role=='sales_orders' else None,
                confirmed_read_access=True))
            store.pull(connection['id'],'synthetic-browser-'+role)
    class InlineDispatch(list):
        def append(self, item):
            super().append(item)
            company, key = item
            execute_company_job(fixture.workspaces.for_principal({'company_id':company}),key)
    fixture.dispatched=InlineDispatch()
    app=fixture.app
    @app.get('/api/auth/session')
    def session(request:Request):
        who=request.state.principal
        return {'mode':'better_auth','user':who,'csrf':'synthetic-ui-token'}

    @app.post('/fixture/switch')
    def switch(body:dict):
        if body.get('company') not in {'tehran_a','tehran_b'}:raise HTTPException(400)
        role=body.get('role','planner')
        if role not in {'planner','viewer','admin'}:raise HTTPException(400)
        fixture.company=body['company'];fixture.role=role
        fixture.permissions=VIEW.copy() if role=='viewer' else ALL.copy()
        fixture.subject=role+'_'+fixture.company
        return {'ok':True}

    app.mount('/assets',StaticFiles(directory=root/'app/static/client/assets'))
    app.mount('/ui',StaticFiles(directory=root/'app/static/client'))
    app.mount('/fonts',StaticFiles(directory=root/'app/static/fonts'))
    app.mount('/static',StaticFiles(directory=root/'app/static'))
    @app.get('/{page:path}')
    def page(page:str):
        if page.startswith('api/'):raise HTTPException(404,'Unscoped API is disabled in this fixture.')
        return FileResponse(root/'app/static/client/index.html')

    async def reply(payload,forecast,outlook,**kwargs):
        return dict(answer='Saved total demand: '+str(sum(row['total'] for row in outlook['rows'])) if outlook else 'Choose a forecast to review.',
            actions=[],run_id=forecast['run_id'],dataset_id=payload.dataset_id,snapshot_id=payload.snapshot_id,
            role='query',model='mock',usage={},provider='mock')
    status={'ready':True,'configured':True,'enabled':True,'provider_label':'Test provider','consent_id':'f'*64,
            'models':{'query':'mock','review':'mock','decision':'mock','title':'mock'},'limits':{'daily_calls':100,'request_calls':5}}
    try:
        with patch('app.ai_workspace.run_chat',AsyncMock(side_effect=reply)),\
             patch('app.ai_workspace.generate_chat_title',AsyncMock(return_value='Customer demand overview')),\
             patch('app.ai_workspace.ai_status',return_value=status):
            print('Synthetic company UI fixture ready: http://127.0.0.1:8013',flush=True)
            uvicorn.run(app,host='127.0.0.1',port=8013,log_level='warning')
    finally:fixture.tearDown()


if __name__=='__main__':
    import sys
    run(notifications='--notifications' in sys.argv)
