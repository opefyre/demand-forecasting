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


def run(*,notifications=False,factors=False,complete_factors=False,revision_journey=False):
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
        _,dataset,body=fixture.history(multiplier,classification='user_provided' if revision_journey else 'synthetic_sample')
        snapshot=fixture.orders(dataset)
        fixture.calculate(dataset,snapshot)
        if revision_journey:
            # Fictional uploaded-history workflow; never seed real/client stores.
            from io import BytesIO
            import pandas as pd
            import uuid
            frame=pd.read_csv(BytesIO(fixture.ws.datasets.source(dataset['sources']['history'])[1]),dtype={'sku':str})
            frame.loc[frame.loc[frame.customer.eq('Aftab')].index[-1],'quantity']=26*multiplier
            source=fixture.ws.datasets.upload('corrected-tehran-history.csv',frame.to_csv(index=False).encode(),'history')
            revised={**body,'name':'Tehran sales · corrected September','sources':{'history':source['id']},
                'parent_dataset_id':dataset['id'],'request_id':str(uuid.uuid4())}
            fixture.post('/datasets/preview',revised)
            fixture.post('/datasets',revised,201)
        if complete_factors:
            # Real legacy scenario inputs, wholly synthetic and company-bound.
            from copy import deepcopy
            from io import BytesIO
            import uuid
            import pandas as pd
            frame=pd.read_csv(BytesIO(fixture.ws.datasets.source(dataset['sources']['history'])[1]),dtype={'sku':str})
            frame['fx']=400000.+pd.to_datetime(frame.date).dt.month*1000.
            history=fixture.ws.datasets.upload('factor-history.csv',frame.to_csv(index=False).encode(),'history')
            body=deepcopy(body)
            body.update(name='Sales with currency',sources={'history':history['id']},request_id=str(uuid.uuid4()))
            body['settings'].update(drivers=['fx'],future_driver_policy='carry',method_selection='model:Ridge + drivers')
            factor_dataset=fixture.post('/datasets',body,201)
            fixture.calculate(factor_dataset,fixture.orders(factor_dataset),['model:Ridge + drivers'])
        if factors:
            # Disposable UI data only; no external request or production seed.
            from app.commodity_prices import parse_prices
            from tests.test_live_factor_alignment import prices, CAPTURE
            if complete_factors:
                import pandas as pd
                start=(pd.Timestamp(fixture.today.replace(day=1))-pd.DateOffset(months=40)).strftime('%Y-%m')
                end=(pd.Timestamp(fixture.today.replace(day=1))-pd.DateOffset(months=1)).strftime('%Y-%m')
                raw=prices(end,start=start)
            else:
                raw=prices()
            definitions={'worldbank_'+key:{**row,'provider':'World Bank','frequency':'monthly','geography':'Global reference'}
                         for key,row in list(parse_prices(raw,CAPTURE).items())[:3]}
            with patch('app.live_sources.now',return_value=CAPTURE):
                fixture.ws.live_sources.save('commodities',definitions,raw,'xlsx','https://example.invalid/fixture')
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
    # Seed requests built the test app's stack; rebuild for the fixture-only hook.
    app.middleware_stack=None
    # A bounded read failure for visible recovery tests; no mutation interception.
    read_failures={}
    @app.post('/fixture/fail-read')
    def fail_read(body:dict):
        path=body.get('path')
        if path not in {'/api/v1/members','/api/v1/api-keys','/api/v1/connections/inputs',
                        '/api/v1/notifications/destinations','/api/v1/notifications/deliveries'}:
            raise HTTPException(400,'Only acceptance-test read routes are allowed.')
        read_failures[path]=1
        return {'ok':True}

    @app.middleware('http')
    async def fail_saved_read(request:Request,call_next):
        if request.method=='GET' and read_failures.get(request.url.path,0):
            from fastapi.responses import JSONResponse
            read_failures[request.url.path]-=1
            return JSONResponse({'detail':'Saved data is temporarily unavailable.'},status_code=503)
        return await call_next(request)

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
        if complete_factors and forecast and payload.question in {'Prepare factor scenario', 'Prepare factor batch'}:
            from app.ai_factor_batch import AssistantFactorBatch
            workspace=fixture.ws
            adapter=AssistantFactorBatch(forecast,workspace.datasets,workspace.factors,workspace.live_sources,workspace.profiles)
            options=adapter.choices()
            snapshot=next(row for row in options['snapshots'] if row['ready'])
            links=[{'snapshot_id':snapshot['id'],'lag_months':1,'future_value':75.0}]
            method=options['methods'][0]
            if payload.question=='Prepare factor batch':
                groups=[{'series_ids':[key],'method':method,'links':links}
                        for key in sorted(set(forecast['series'])-{'__all__'})[:2]]
                action=adapter.proposal(groups)
            else:
                action=adapter.scenarios.proposal(links,method)
            return dict(answer='Review these factor assumptions before continuing.',actions=[action],run_id=forecast['run_id'],
                dataset_id=payload.dataset_id,snapshot_id=payload.snapshot_id,role='decision',model='mock',usage={},provider='mock')
        if factors and forecast and payload.question=='Review customer factors':
            from app.ai_factor_batch import AssistantFactorBatch
            workspace=fixture.ws
            assistant=AssistantFactorBatch(forecast,workspace.datasets,workspace.factors,workspace.live_sources,workspace.profiles)
            action=assistant.handoff(sorted(set(forecast['series'])-{'__all__'})[:2])
            return dict(answer='Review the selected customer factors.',actions=[action],run_id=forecast['run_id'],dataset_id=payload.dataset_id,
                snapshot_id=payload.snapshot_id,role='query',model='mock',usage={},provider='mock')
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
    run(notifications='--notifications' in sys.argv,factors='--factors' in sys.argv,complete_factors='--complete-factors' in sys.argv,
        revision_journey='--revision-journey' in sys.argv)
