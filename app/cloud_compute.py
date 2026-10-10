"""Private stateless forecast engine. No UI, login, public routes or schedulers.

The Cloudflare Durable Object is the ONLY caller. It supplies a company-bound
checkpoint and reviewed job, then durably saves the returned checkpoint/results.
This module never reads the local demo workspace or starts background schedules.
"""
import json
from pathlib import Path
import tempfile
from threading import Lock

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse
from starlette.concurrency import run_in_threadpool

from .cloud_state import MAX_COMPRESSED, capture, restore, company_id
from .company_workspace import CompanyWorkspaces

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_busy = Lock()
_outputs = {}  # Scratch artifacts only; never the authoritative job ledger.
_requests = {}  # Bounded one-attempt request bodies, never credentials.


@app.get('/network/{attempt}/next')
def next_request(attempt: str):
    from .cloud_network import active_bridge
    try: return {'request':active_bridge(attempt).next()}
    except ValueError: return {'request':None}


@app.put('/network/{attempt}/{key}')
async def answer_request(attempt: str, key: str, request: Request):
    from .cloud_network import active_bridge
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>28*1024*1024: raise HTTPException(413,'Private response is too large.')
    try: active_bridge(attempt).answer(key,json.loads(raw))
    except (ValueError, UnicodeDecodeError):raise HTTPException(400,'Private request is unavailable.') from None
    return {'saved':True}


@app.post('/network/{attempt}/exchange')
async def child_request(attempt: str, request: Request):
    from .cloud_network import active_bridge
    raw=bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw)>1024*1024:raise HTTPException(413,'Private request is too large.')
    try:return await run_in_threadpool(active_bridge(attempt).exchange,json.loads(raw))
    except ValueError:raise HTTPException(400,'Private request is unavailable.') from None


@app.put('/request/{job}')
async def stage_request(job: str, request: Request):
    if len(job) != 32 or any(c not in '0123456789abcdef' for c in job): raise HTTPException(400, 'Invalid attempt.')
    if not _busy.acquire(blocking=False): raise HTTPException(409, 'Engine is busy.')
    temporary = None
    try:
        if _requests or job in _outputs: raise HTTPException(409, 'Attempt already staged.')
        temporary = tempfile.TemporaryDirectory(prefix='forecast-request-')
        path = Path(temporary.name) / 'body'
        size = 0
        with path.open('xb') as output:
            path.chmod(0o600)
            async for chunk in request.stream():
                size += len(chunk)
                if size > 51 * 1024 * 1024: raise HTTPException(413, 'Request is too large.')
                output.write(chunk)
        _requests[job] = (temporary, path)
        temporary = None
        return {'staged': True}
    finally:
        if temporary: temporary.cleanup()
        _busy.release()


@app.get('/ready')
def ready():
    return {'ready': True}


def calculate(source, root, company, outer_job, payload):
    restore(source, root, company)
    workspaces = CompanyWorkspaces(root / 'data/companies')
    try:
        workspace = workspaces.for_principal({'company_id': company})
        from .company_jobs import execute_company_job
        from .main import SavedRunConfig
        # Same validation and mathematical engine as the local app. No AI call,
        # remapping, simplified dummy formula or hidden order replacement.
        checked = SavedRunConfig.model_validate(payload).model_dump(mode='json')
        job = workspace.jobs.create(checked, 'Cloud forecast', 'cloud:' + outer_job)
        execute_company_job(workspace, job['id'])
        finished = workspace.jobs.get(job['id'])
        if finished['state'] != 'succeeded':
            raise ValueError('Forecast calculation did not complete.')
        run = workspace.load_run(finished['run_id'])
        metadata = {'job_id': outer_job, 'run_id': run['run_id'], 'company_id': company}
        folder = workspace.runs / run['run_id']
        metadata['artifacts'] = sorted(p.name for p in folder.iterdir() if p.is_file())
        if any('/' in name or '\\' in name for name in metadata['artifacts']): raise ValueError()
        workspaces.close()
        capture(root, company, source.parent / 'completed.zip')
        return metadata
    finally:
        workspaces.close()


@app.post('/api-operation')
@app.post('/forecast')
async def forecast(request: Request):
    if not _busy.acquire(blocking=False): raise HTTPException(409, 'Engine is busy.')
    temporary = None
    try:
        # A job token is not an identity credential. It fences a single attempt.
        metadata = request.headers.get('x-forecast-job', '')
        if len(metadata) > 16384: raise ValueError()
        values = json.loads(metadata)
        company = company_id(values['company_id'])
        job_id, payload = values['job_id'], values['payload']
        if not isinstance(job_id, str) or len(job_id) != 32 or any(c not in '0123456789abcdef' for c in job_id): raise ValueError()
        if job_id in _outputs: raise HTTPException(409, 'Attempt already has an output.')
        temporary = tempfile.TemporaryDirectory(prefix='forecast-cloud-')
        folder = Path(temporary.name)
        source = folder / 'input.zip'
        size = 0
        with source.open('xb') as output:
            source.chmod(0o600)
            async for chunk in request.stream():
                size += len(chunk)
                if size > MAX_COMPRESSED: raise HTTPException(413, 'Checkpoint is too large.')
                output.write(chunk)
        if request.url.path == '/api-operation':
            from .cloud_api import operate
            if job_id not in _requests: raise ValueError()
            from .cloud_network import bind_bridge
            with bind_bridge(job_id, payload.get('_cloud_ai')):
                result = await run_in_threadpool(operate, source, folder / 'workspace', company, job_id,
                    payload, _requests[job_id][1])
        else:
            result = await run_in_threadpool(calculate, source, folder / 'workspace', company, job_id, payload)
        _outputs[job_id] = (temporary, result)
        temporary = None
        return result
    except HTTPException:
        raise
    except Exception:
        # Do not return uploaded content, source exceptions, credentials or paths.
        raise HTTPException(422, 'Forecast inputs could not be calculated.') from None
    finally:
        if 'job_id' in locals() and job_id in _requests:
            pending, _ = _requests.pop(job_id)
            pending.cleanup()
        if temporary: temporary.cleanup()
        _busy.release()


def output(job):
    if job not in _outputs: raise HTTPException(404, 'Output not found.')
    temporary, metadata = _outputs[job]
    return Path(temporary.name), metadata


@app.get('/output/{job}/snapshot')
def snapshot(job: str):
    root, _ = output(job)
    if not (root / 'completed.zip').is_file(): raise HTTPException(404, 'Checkpoint not found.')
    return FileResponse(root / 'completed.zip', media_type='application/zip')


@app.get('/output/{job}/artifact/{name}')
def artifact(job: str, name: str):
    root, metadata = output(job)
    if name not in metadata['artifacts']: raise HTTPException(404, 'Output not found.')
    if 'api_status' in metadata:
        return FileResponse(root / 'api-output' / name, media_type='application/octet-stream' if name=='api-download.bin' else 'application/json')
    return FileResponse(root / 'workspace/data/companies' / metadata['company_id'] / 'runs' / metadata['run_id'] / name)


@app.delete('/output/{job}')
def discard(job: str):
    # Called only AFTER the checkpoint and artifacts are saved externally. The exact
    # temporary directory was created by this service; no user paths are deleted.
    if job in _outputs:
        temporary, _ = _outputs.pop(job)
        temporary.cleanup()
    if job in _requests:
        temporary, _ = _requests.pop(job)
        temporary.cleanup()
    return {'removed': True}
