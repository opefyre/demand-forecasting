"""Local, role-protected input snapshots and demand export endpoints."""
from datetime import datetime, timedelta, timezone
from io import StringIO
import csv
import hashlib
import json
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from .sales_demand import SCHEMAS, demand_outlook, import_rows, export_demand, revise_orders, StaleOrderRevision, run_today, month, month_basis
from .inventory import inventory_preview


def template_customers(run):
    return [{'customer': str(meta.get('customer') or ''), 'sku': str(meta.get('sku') or ''),
             'unit': run.get('unit', ''), 'series_id': key}
            for key, meta in run.get('metadata', {}).items()
            if key in run.get('series', {}) and key != '__all__']


def run_hash(run):
    return hashlib.sha256(json.dumps(run, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def prepare_sales_inputs(store, sources, load_run, payload):
    inputs = dict(payload.get('inputs', {}))
    evidence = []
    for role, config in payload.get('imports', {}).items():
        if role not in SCHEMAS:
            raise ValueError('Unknown sales input role.')
        inputs[role], proof = import_rows(sources, role, config)
        evidence.append(proof)
    run = load_run(inputs.get('run_id', ''))
    refresh_source=payload.get('order_refresh_source')
    refresh_changes=None
    if refresh_source:
        from .order_reuse import compatible
        source=store.get(refresh_source.get('snapshot_id',''))
        source_run=load_run(source['inputs']['run_id'])
        latest=store.list(source['inputs']['run_id'])
        if not latest or latest[0]['id']!=source['id'] or refresh_source.get('sha256')!=source['sha256']:
            raise StaleOrderRevision('Source orders changed. Refresh and review again.')
        if (next((e.get('run_sha256') for e in source['evidence'] if 'run_sha256' in e),None)!=run_hash(source_run)
                or (source_run['run_id']!=run['run_id'] and not compatible(source_run,run))):
            raise ValueError('The order source does not match this forecast.')
        target=store.list(run['run_id'])
        if (target[0]['id'] if target else None)!=payload.get('base_snapshot_id'):
            raise StaleOrderRevision('Target orders changed. Refresh and review again.')
        if inputs.get('as_of','')<source['inputs']['as_of']:
            raise ValueError('An order refresh cannot have an earlier source date.')
        if source_run['run_id']!=run['run_id'] and not payload.get('base_snapshot_id'):
            inputs['orders'],refresh_changes=revise_orders(source['inputs']['orders'],inputs.get('orders',[]),'replace',inputs.get('as_of',''))
        evidence.append({'type':'connected_order_refresh','source_snapshot_id':source['id'],
            'source_sha256':source['sha256'],
            'request_sha256':hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'guard':{'source_id':source['id'],
                'source_sha256':source['sha256'],'target_latest_id':target[0]['id'] if target else None}})
    base_id = payload.get('base_snapshot_id')
    mode = payload.get('order_mode', 'replace')
    changes = refresh_changes
    if base_id:
        base = store.get(base_id)
        if base['inputs']['run_id'] != inputs.get('run_id'):
            raise ValueError('This order version belongs to another forecast.')
        digest = next((e['run_sha256'] for e in base['evidence'] if 'run_sha256' in e), None)
        if digest != run_hash(run):
            raise ValueError('The baseline changed. Create and review a new order book for this forecast.')
        if inputs.get('as_of', '') < base['inputs']['as_of']:
            raise ValueError('An order update cannot have an earlier source date than the saved version.')
        if mode == 'changes' and base['inputs']['order_feed'] != 'complete_snapshot':
            raise ValueError('Import a full order book first. Changed lines cannot fill gaps in an incomplete source.')
        inputs['orders'], changes = revise_orders(base['inputs']['orders'], inputs.get('orders', []), mode, inputs.get('as_of', ''))
        evidence.append({'base_snapshot_id': base_id, 'base_sha256': base['sha256'], 'order_mode': mode,
                         'order_changes': changes})
    elif mode != 'replace':
        raise ValueError('Changed lines need a saved complete order book to update.')
    evidence.append({'run_sha256': run_hash(run)})
    outlook = demand_outlook(inputs, run)
    for proof in evidence:
        if proof.get('customer_matches'):
            outlook['warnings'].append('Reviewed customer matches: '+', '.join(f'{old} → {new}' for old,new in proof['customer_matches'].items()))
    if changes is not None:
        outlook['order_changes'] = changes
    return inputs, run, evidence, outlook


def install_sales_routes(app, store, sources, load_run, list_runs=None):
    router = APIRouter(prefix='/api/sales')

    def prepare(payload):
        return prepare_sales_inputs(store,sources,load_run,payload)

    def stored_outlook(key):
        saved = store.get(key)
        run = load_run(saved['inputs']['run_id'])
        digest = next((e['run_sha256'] for e in saved['evidence'] if 'run_sha256' in e), None)
        if digest != run_hash(run):
            raise ValueError('The baseline changed since this snapshot. Review and save new inputs.')
        return {**demand_outlook(saved['inputs'], run), 'snapshot_id': key,
                'created_at': saved['created_at'], 'actor': saved['actor'], 'evidence': saved['evidence']}

    @router.get('/schema')
    def schema():
        return {key: {name: {'required': field.is_required()} for name, field in model.model_fields.items()}
                for key, model in SCHEMAS.items()}

    @router.get('/runs/{run_id}/order-reuse/choices')
    def reuse_choices(run_id: str):
        from .order_reuse import compatible
        target=load_run(run_id); choices=[]
        for row in (list_runs()['runs'] if list_runs else []):
            base=load_run(row['run_id'])
            if compatible(base,target):
                versions=store.list(base['run_id'])
                if versions:
                    source=versions[0]
                    choices.append({'id':source['id'],'name':row['name'],'as_of':source['inputs']['as_of']})
        return {'sources':choices}

    @router.post('/runs/{run_id}/order-reuse/preview')
    def reuse_preview(run_id: str,payload: dict):
        from .order_reuse import preview_reuse
        try:return preview_reuse(store,load_run,run_id,payload.get('snapshot_id',''))[0]
        except StaleOrderRevision as exc:raise HTTPException(409,str(exc)) from exc
        except (ValueError,KeyError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/runs/{run_id}/order-reuse')
    def reuse_save(run_id: str,payload: dict,request: Request):
        from .order_reuse import save_reuse
        try:
            principal=request.state.principal
            actor=json.dumps([principal.get('issuer'),principal.get('subject')]) if principal else 'Local session'
            return save_reuse(store,load_run,run_id,payload,actor)
        except StaleOrderRevision as exc:raise HTTPException(409,str(exc)) from exc
        except (ValueError,KeyError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/runs/{run_id}/order-comparison/preview')
    def compare(run_id: str, payload: dict):
        from .demand_comparison import compare_orders
        try:
            return compare_orders(store, load_run, run_id, payload.get('snapshot_id',''))[0]
        except StaleOrderRevision as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post('/runs/{run_id}/order-comparison')
    def reuse_orders(run_id: str, payload: dict, request: Request):
        from .demand_comparison import save_comparison
        try:
            principal=request.state.principal
            actor=json.dumps([principal.get('issuer'),principal.get('subject')]) if principal else 'Local session'
            return save_comparison(store,load_run,run_id,payload,actor)
        except StaleOrderRevision as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post('/sources')
    async def upload(file: UploadFile = File(...), role: str = Form(...)):
        if role not in SCHEMAS:
            raise HTTPException(400, 'Choose customers, orders or commitments.')
        content = await file.read(10 * 1024 * 1024 + 1)
        if len(content) > 10 * 1024 * 1024:
            raise HTTPException(400, 'Use a file smaller than 10 MB.')
        try:
            return sources.upload(file.filename, content, 'sales_' + role)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post('/sources/{key}/preview')
    def preview(key: str, payload: dict):
        try:
            source, content = sources.source(key)
            if not source['role'].startswith('sales_'):
                raise ValueError('Select a sales input file.')
            return inventory_preview(source['name'], content, payload.get('sheet'), payload.get('header_row', 1))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get('/runs/{run_id}/inputs')
    def saved_inputs(run_id: str):
        load_run(run_id)
        return {'snapshots': [{'id': s['id'], 'name': s['inputs']['name'], 'as_of': s['inputs']['as_of'],
                               'created_at': s['created_at']} for s in store.list(run_id)]}

    @router.get('/runs/{run_id}/template/{role}')
    def template(run_id: str, role: str):
        if role not in SCHEMAS:
            raise HTTPException(400, 'Unknown template.')
        run = load_run(run_id)
        output = StringIO(); writer = csv.DictWriter(output, fieldnames=list(SCHEMAS[role].model_fields))
        writer.writeheader()
        if role == 'customers':
            # Actual source labels, not parsed display identifiers.
            for row in template_customers(run):
                writer.writerow({k: "'"+v if v.lstrip().startswith(('=', '+', '-', '@')) else v for k,v in row.items()})
        return Response(output.getvalue(), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{role}.csv"'})

    @router.get('/runs/{run_id}/starter')
    def starter(run_id: str):
        run = load_run(run_id)
        today = run_today(run)
        return {'name': 'Customer demand plan', 'run_id': run_id, 'as_of': str(today),
                'valid_until': str(today), 'classification': run.get('source_classification', 'user_provided'),
                'order_feed': 'unknown', 'customers': template_customers(run), 'orders': [],
                'commitments': [], 'reviewed': False, 'note': ''}

    @router.get('/runs/{run_id}/sample')
    def sample(run_id: str):
        data = starter(run_id)
        run = load_run(run_id)
        if data['classification'] != 'synthetic_sample':
            raise HTTPException(400, 'Sample orders can only be used with a sample forecast.')
        data.update(name='Sample · orders and expected demand', order_feed='complete_snapshot',
                    note='Synthetic orders only. Review customer matching before saving.',
                    valid_until=str(run_today(run) + timedelta(days=7)))
        current_month = month(data['as_of'], month_basis(run))
        for i, row in enumerate(data['customers']):
            future = [f for f in run['series'][row['series_id']]['forecast'] if str(f['timestamp'])[:10] >= current_month]
            if i % 3 == 1 or not future:
                continue
            forecast = future[0]
            qty = round(float(forecast['mean']) * (1.2 if i % 3 == 0 else .5), 3)
            data['orders'].append({'reference': f'SAMPLE-SO-{i+1}/1', 'customer': row['customer'],
                'sku': row['sku'], 'unit': row['unit'], 'due_date': str(forecast['timestamp'])[:7]+'-28',
                'ordered': qty, 'fulfilled': 0, 'cancelled': 0, 'status': 'confirmed'})
        return data

    @router.post('/validate')
    def validate(payload: dict):
        try:
            return prepare(payload)[3]
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.post('/inputs')
    def save(payload: dict, request: Request):
        try:
            if payload.get('order_refresh_source') and isinstance(payload.get('request_id'),str):
                try:old=store.get(hashlib.sha256(payload['request_id'].encode()).hexdigest()[:32])
                except ValueError:old=None
                if old:
                    proof=next((e for e in old['evidence'] if e.get('type')=='connected_order_refresh'),{})
                    digest=hashlib.sha256(json.dumps(payload,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    if proof.get('request_sha256')!=digest:
                        raise ValueError('This retry identifier was already used for different inputs.')
                    return old
            inputs, run, evidence, _ = prepare(payload)
            principal = request.state.principal
            actor = json.dumps([principal.get('issuer'), principal.get('subject')]) if principal else 'Local session'
            guard=next((e['guard'] for e in evidence if e.get('type')=='connected_order_refresh'),None)
            return store.save(inputs, run, payload.get('request_id'), actor, evidence, payload.get('base_snapshot_id'),comparison_guard=guard)
        except StaleOrderRevision as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, KeyError, TypeError) as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get('/inputs/{key}')
    def get_inputs(key: str):
        try:
            return store.get(key)
        except ValueError as exc:
            raise HTTPException(404, str(exc)) from exc

    @router.get('/inputs/{key}/outlook')
    def outlook(key: str):
        try:
            return stored_outlook(key)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.get('/inputs/{key}/export')
    def export(key: str, mode: str, kind: str = 'xlsx'):
        try:
            content, mime = export_demand(stored_outlook(key), mode, kind)
            return Response(content, media_type=mime, headers={'Content-Disposition': f'attachment; filename="draft-demand-{mode}.{kind}"'})
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    app.include_router(router)
    return stored_outlook
