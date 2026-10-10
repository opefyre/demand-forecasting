"""Reuse the existing company API inside isolated, offline cloud scratch space.

Only the private Worker supplies validated principals. No external HTTP, login,
background schedulers or alternate business/calculation implementation is used.
"""
import asyncio
import json
import re
from urllib.parse import urlsplit, parse_qsl
from datetime import datetime, timezone
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
    parsed = urlsplit(path)
    if parsed.scheme or parsed.netloc: raise ValueError('Unsupported company operation.')
    for entry in CONTRACT:
        pattern = re.escape(entry['path']).replace(r'\{id\}', r'[a-zA-Z0-9_-]{1,128}').replace(r'\{index\}', r'[0-9]{1,3}')
        if method == entry['method'] and re.fullmatch(pattern, parsed.path):
            query = parse_qsl(parsed.query, keep_blank_values=True)
            if parsed.fragment or any(k not in entry.get('query', []) for k, _ in query) or len({k for k, _ in query}) != len(query):
                raise ValueError('Unsupported company query.')
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
        if response.status_code in {400, 404, 409}: return None
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
            if name == 'customers': await save('/customers/' + key + '/factor-profiles')
            if name == 'datasets':
                await save('/datasets/' + key + '/orders')
                await save('/datasets/' + key + '/factors')
            if name == 'runs' and row.get('sales_input_snapshot_id'):
                await save('/runs/' + key + '/demand')
            if name == 'runs':
                await save('/runs/' + key + '/orders/starter')
                await save('/runs/' + key + '/order-snapshots')
                evaluations = await save('/runs/' + key + '/actuals')
                for item in (evaluations or {}).get('evaluations', []): await save('/actuals/' + item['id'])
            if name != 'customers':
                for suffix in ['metadata', 'revisions']: await save('/' + name + '/' + key + '/' + suffix)
    await save('/orders/schema')
    await save('/factors')
    for row in workspace.factors.list(): await save('/factors/' + row['id'])
    # Review snapshots may precede any calculation; retain both dataset-bound
    # reviews and subsequent run-bound reviews, through the existing store API.
    for key in ['inputs:' + r['id'] for r in views['/datasets']['datasets']] + [r['run_id'] for r in views['/runs']['runs']]:
        for row in workspace.sales.list(key):
            await save('/order-snapshots/' + row['id'])
            if not key.startswith('inputs:'): await save('/order-snapshots/' + row['id'] + '/demand')
    for frequency in ['monthly', 'weekly', 'daily']:
        for profile in ['fast', 'deep']:
            await save(f'/forecast-methods?frequency={frequency}&profile={profile}')
    for path in ['/workspace', '/units', '/jobs', '/releases']: await save(path)
    for item in views['/jobs']['jobs']: await save('/jobs/' + item['id'])
    for item in views['/releases']['releases']: await save('/releases/' + item['id'])
    # Build approved-only variants THROUGH the original report permission gates.
    # Never filter a draft payload after giving it to a Viewer.
    report_views = {}
    viewer = dict(who, role='viewer', permissions=['reports:read','reports:export'])
    paths = ['/runs?limit=1000&include_archived=true'] + [p for p in views if
        p.startswith(('/runs/', '/releases', '/actuals/', '/order-snapshots/')) and not
        p.endswith(('/orders/starter', '/demand'))]
    paths += [p for p in views if p.startswith('/order-snapshots/') and p.endswith('/demand')]
    approved_rows = []
    for offset in range(0, RECORD_LIMIT + 1, 1000):
        value = await invoke(api, viewer, 'GET', f'/runs?limit=1000&offset={offset}&include_archived=true')
        if value.status_code != 200: raise ValueError('Approved reports unavailable.')
        page = value.json(); approved_rows.extend(page['runs'])
        if len(approved_rows) > RECORD_LIMIT: raise ValueError('Approved report capacity exceeded.')
        if len(approved_rows) >= page['total']: break
    report_views['/runs'] = {'runs':approved_rows,'total':len(approved_rows)}
    for path in paths[1:]:
        value = await invoke(api, viewer, 'GET', path)
        if value.status_code == 200: report_views[path] = value.json()
    encoded = json.dumps({'company_id': company, 'views': views, 'report_views':report_views,
        'checked_at':datetime.now(timezone.utc).isoformat(), 'timezone':workspace.site['timezone']}, ensure_ascii=False).encode()
    if len(encoded) > VIEW_LIMIT: raise ValueError('Company read projection is too large.')
    return encoded


def operate(source, root, company, attempt, command, body_path):
    company_id(company)
    entry = route(command['method'], command['path'])
    if entry['method'] == 'GET' and not (entry.get('queued') or entry.get('fresh')): raise ValueError('Saved reads must not wake the engine.')
    who = command['principal']
    if (who.get('company_id') != company or who.get('issuer') != 'https://forecast.vrolen.com'
            or who.get('mfa_required') is not False or who.get('role') not in {'admin', 'planner', 'approver', 'viewer'}
            or not isinstance(who.get('subject'), str) or not who['subject']
            or who.get('auth_kind') not in {'session', 'api_key'}
            or not all(scope in who.get('permissions', []) for scope in entry['scopes'])):
        raise ValueError('Company authorization is unavailable.')
    if entry.get('interactive') and who['auth_kind'] != 'session' or entry.get('admin') and who['role'] != 'admin':
        raise ValueError('Interactive administrator authorization is unavailable.')
    if source.stat().st_size: restore(source, root, company)
    workspaces = CompanyWorkspaces(root / 'data/companies')
    try:
        workspace = workspaces.for_principal(who)
        from .platform_api import create_platform_api
        from .company_jobs import execute_company_job
        from .cloud_network import current_bridge, CloudIdentityService
        bridge = current_bridge()
        service = CloudIdentityService(bridge, company) if bridge else None
        api = create_platform_api(service, workspaces, dispatcher=execute_company_job)
        body = body_path.read_bytes()
        if command.get('sealed'):
            import os
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            binding=json.dumps([company,'api-request',command['body_hash']],separators=(',',':')).encode()
            body=AESGCM(bytes.fromhex(os.environ['DEMANDLAB_COMPANY_VAULT_KEY'])).decrypt(body[:12],body[12:],binding)
        response = asyncio.run(invoke(api, who, command['method'], command['path'], body,
            command['content_type']))
        # Failed validation or permissions never promote a scratch checkpoint,
        # even if a route wrote temporary review material before failing.
        status = response.status_code
        if status >= 500 and not entry.get('network'): raise ValueError('Company operation unavailable.')
        result = {'job_id': attempt, 'company_id': company, 'run_id': attempt,
            'api_status': status, 'artifacts': ['api-response.json']}
        output = source.parent / 'api-output'
        output.mkdir()
        if entry.get('download') and 200 <= status < 300:
            value = {'checked_at':datetime.now(timezone.utc).isoformat(), 'timezone':workspace.site['timezone'],
                'download':{'content_type':response.headers.get('content-type','application/octet-stream'),
                'disposition':response.headers.get('content-disposition','attachment')}}
            (output / 'api-download.bin').write_bytes(response.content)
            result['artifacts'].append('api-download.bin')
        else: value = response.json()
        (output / 'api-response.json').write_text(json.dumps(value, ensure_ascii=False))
        if 200 <= status < 300 and entry['method'] == 'GET' and entry.get('fresh'):
            (output / 'company-view.json').write_bytes(asyncio.run(projection(api, workspace, company)))
            result['artifacts'].append('company-view.json')
        if entry['method'] != 'GET' and (200 <= status < 300 or entry.get('network')):
            from .cloud_schedules import record_source_owner, descriptors, metadata, save_metadata, event_hash
            record_source_owner(workspace,who,command['method'],command['path'])
            if command['path']=='/notifications/check':
                timers=metadata(workspace);timers['events']=event_hash(workspace);save_metadata(workspace,timers)
            (output / 'company-view.json').write_bytes(asyncio.run(projection(api, workspace, company)))
            result['artifacts'].append('company-view.json')
            (output / 'company-schedules.json').write_text(json.dumps(descriptors(workspace)))
            result['artifacts'].append('company-schedules.json')
            workspaces.close()
            capture(root, company, source.parent / 'completed.zip')
            result['committed'] = True
        return result
    finally:
        workspaces.close()
