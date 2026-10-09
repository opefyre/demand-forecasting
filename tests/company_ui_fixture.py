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


def run():
    import uvicorn
    fixture=PublicSalesTests();fixture.setUp()
    root=Path(__file__).resolve().parents[1]
    for company,multiplier in [('tehran_a',1),('tehran_b',2)]:
        fixture.company=company
        _,dataset,_=fixture.history(multiplier)
        snapshot=fixture.orders(dataset)
        fixture.calculate(dataset,snapshot)
    fixture.company='tehran_a';fixture.permissions=ALL.copy();fixture.role='planner'
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


if __name__=='__main__':run()
