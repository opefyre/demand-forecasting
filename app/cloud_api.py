"""Reuse the existing company API inside isolated, offline cloud scratch space.

Only the private Worker supplies validated principals. No external HTTP, login,
background schedulers or alternate business/calculation implementation is used.
"""
import asyncio
import json
import re
from pathlib import Path

import httpx

from .cloud_state import capture, restore, company_id
from .company_workspace import CompanyWorkspaces

CONTRACT = json.loads(Path(__file__).with_name('cloud_api_contract.json').read_text())
VIEW_LIMIT = 12 * 1024 * 1024
RECORD_LIMIT = 5000


def route(method, path):
    if not isinstance(path, str) or len(path) > 512:
        raise ValueError('Unsupported company operation.')
    for entry in CONTRACT:
        pattern = re.escape(entry['path']).replace(r'\{id\}', r'[a-zA-Z0-9_-]{1,128}')
        if method == entry['method'] and re.fullmatch(pattern, path):
            return entry
    raise ValueError('Unsupported company operation.')


async def invoke(api, who, method, path, body=b'', content_type='application/json'):
    # ASGITransport deliberately does not run startup/lifespan hooks. The company
    # router is unchanged; its schedulers and local identity server never start.
    async def scoped(scope, receive, send):
        scope = {**scope, 'state': {'principal': who}}
        await api(scope, receive, send)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=scoped), base_url='http://company.invalid',
            trust_env=False, follow_redirects=False) as client:
        return await client.request(method, path, content=body, headers={'content-type': content_type})


async def projection(api, workspace, company):
    # Private projection creation is NOT login or privilege escalation. It has
    # read-only resource scopes. Consumers must independently check each route's
    # live key/session scopes. Unpublished results require drafts:read throughout.
    who = {'company_id': company, 'issuer': 'https://forecast.vrolen.com', 'subject': 'cloud-projection',
        'auth_kind': 'api_key', 'role': 'planner', 'mfa_required': False,
        'permissions': sorted({s for e in CONTRACT if e['method'] == 'GET' for s in e['scopes']})}
    views = {}

    async def save(path):
        response = await invoke(api, who, 'GET', path)
        if response.status_code == 404: return None
        if response.status_code != 200: raise ValueError('Company read projection is unavailable.')
        value = response.json()
        views[path] = value
        return value

    for name in ['customers', 'sources', 'datasets', 'forecasts', 'runs']:
        rows = []
        for offset in range(0, RECORD_LIMIT + 1, 1000):
            query = f'?limit=1000&offset={offset}&include_archived=true'
            response = await invoke(api, who, 'GET', '/' + name + query)
            if response.status_code != 200: raise ValueError('Company list projection is unavailable.')
            value = response.json()
            rows.extend(value[name])
            if len(rows) > RECORD_LIMIT: raise ValueError('Company projection capacity exceeded.')
            if len(rows) >= value['total']: break
        views['/' + name] = {name: rows, 'total': len(rows)}
        for row in rows:
            key = row.get('id', row.get('run_id'))
            await save('/' + name + '/' + key)
            if name == 'customers': await save('/customers/' + key + '/products')
            if name == 'datasets':
                await save('/datasets/' + key + '/orders')
                await save('/datasets/' + key + '/factors')
            if name == 'runs' and row.get('sales_input_snapshot_id'):
                await save('/runs/' + key + '/demand')
    await save('/orders/schema')
    await save('/factors')
    for row in workspace.factors.list(): await save('/factors/' + row['id'])
    # Review snapshots may precede any calculation; retain both dataset-bound
    # reviews and subsequent run-bound reviews, through the existing store API.
    for key in ['inputs:' + r['id'] for r in views['/datasets']['datasets']] + [r['run_id'] for r in views['/runs']['runs']]:
        for row in workspace.sales.list(key): await save('/order-snapshots/' + row['id'])
    for frequency in ['monthly', 'weekly', 'daily']:
        for profile in ['fast', 'deep']:
            await save(f'/forecast-methods?frequency={frequency}&profile={profile}')
    encoded = json.dumps({'company_id': company, 'views': views}, ensure_ascii=False).encode()
    if len(encoded) > VIEW_LIMIT: raise ValueError('Company read projection is too large.')
    return encoded


def operate(source, root, company, attempt, command, body_path):
    company_id(company)
    entry = route(command['method'], command['path'])
    if entry['method'] == 'GET': raise ValueError('Saved reads must not wake the engine.')
    who = command['principal']
    if (who.get('company_id') != company or who.get('issuer') != 'https://forecast.vrolen.com'
            or who.get('mfa_required') is not False or who.get('role') not in {'admin', 'planner', 'approver', 'viewer'}
            or not isinstance(who.get('subject'), str) or not who['subject']
            or who.get('auth_kind') not in {'session', 'api_key'}
            or not all(scope in who.get('permissions', []) for scope in entry['scopes'])):
        raise ValueError('Company authorization is unavailable.')
    if source.stat().st_size: restore(source, root, company)
    workspaces = CompanyWorkspaces(root / 'data/companies')
    try:
        workspace = workspaces.for_principal(who)
        from .platform_api import create_platform_api
        from .company_jobs import execute_company_job
        api = create_platform_api(None, workspaces, dispatcher=execute_company_job)
        response = asyncio.run(invoke(api, who, command['method'], command['path'], body_path.read_bytes(),
            command['content_type']))
        # Failed validation or permissions never promote a scratch checkpoint,
        # even if a route wrote temporary review material before failing.
        status = response.status_code
        if status >= 500: raise ValueError('Company operation unavailable.')
        value = response.json()
        result = {'job_id': attempt, 'company_id': company, 'run_id': attempt,
            'api_status': status, 'artifacts': ['api-response.json']}
        output = source.parent / 'api-output'
        output.mkdir()
        (output / 'api-response.json').write_text(json.dumps(value, ensure_ascii=False))
        if 200 <= status < 300:
            (output / 'company-view.json').write_bytes(asyncio.run(projection(api, workspace, company)))
            result['artifacts'].append('company-view.json')
            workspaces.close()
            capture(root, company, source.parent / 'completed.zip')
        return result
    finally:
        workspaces.close()
