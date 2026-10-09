"""Review and freeze order-aware demand for a named receiving-system policy.

Reuses the demand ledger/engine/exporter. No external transmission or order edits.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import sqlite3

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

from .demand_comparison import digest
from .sales_demand import demand_outlook, export_demand, month, month_basis, run_today


class ReleaseConflict(ValueError):pass


def identity(principal):
    return ({'issuer':principal['issuer'],'subject':principal['subject'],'basis':'company_sign_in'}
            if principal else {'basis':'local_demo','subject':'local'})


def contract(payload):
    receiver=payload.get('receiver')
    if not isinstance(receiver,str) or not 1<=len(receiver.strip())<=120:
        raise ValueError('Name the receiving planning system (up to 120 characters).')
    mode=payload.get('mode')
    if mode not in {'remaining_forecast','combined_demand'}:
        raise ValueError('Confirm whether the receiving system already includes these orders.')
    return {'receiver':receiver.strip(),'mode':mode}


def monthly(outlook,mode):
    groups={}
    for r in outlook['rows']:
        key=(r['period'],r['unit'])
        group=groups.setdefault(key,{'period':r['period'],'period_label':r.get('period_label',r['period'][:7]),'unit':r['unit'],
            'booked':Decimal(0),'fulfilled':Decimal(0),'remaining':Decimal(0),'quantity':Decimal(0)})
        for name in ('booked','fulfilled','remaining'):
            group[name]+=Decimal(str(r[name]))
        group['quantity']+=Decimal(str(r['remaining'] if mode=='remaining_forecast' else r['still_to_serve']))
    return [{k:float(v) if isinstance(v,Decimal) else v for k,v in groups[key].items()} for key in sorted(groups)]


class DemandReleases:
    def __init__(self,orders,load_run):
        self.orders,self.load_run=orders,load_run
        # Shared ledger makes source-version guards atomic with order imports.
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS demand_releases (id TEXT PRIMARY KEY, scope TEXT NOT NULL, version INTEGER NOT NULL, record TEXT NOT NULL, UNIQUE(scope,version))')
            db.execute('CREATE TABLE IF NOT EXISTS demand_release_requests (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, release_id TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.orders.path,timeout=30)
        try:
            with db:yield db
        finally:db.close()

    def get(self,key):
        with self.connect() as db:
            row=db.execute('SELECT record FROM demand_releases WHERE id=?',(key,)).fetchone()
        if not row:raise ValueError('Demand release not found.')
        return json.loads(row[0])

    def list(self,run_id=None):
        with self.connect() as db:
            rows=[json.loads(r[0]) for r in db.execute('SELECT record FROM demand_releases ORDER BY rowid DESC')]
        return [{k:r[k] for k in ('id','version','snapshot_id','run_id','contract','state','created_at','demo_only')}
                for r in rows if not run_id or r['run_id']==run_id]

    def check(self,snapshot_id):
        snapshot=self.orders.get(snapshot_id);run=self.load_run(snapshot['inputs']['run_id'])
        versions=self.orders.list(run['run_id'])
        if not versions or versions[0]['id']!=snapshot_id:
            raise ReleaseConflict('A newer order review exists. Prepare the release from the latest version.')
        proof=next((e['run_sha256'] for e in snapshot['evidence'] if 'run_sha256' in e),None)
        if proof!=digest(run):
            raise ReleaseConflict('The forecast changed. Review its orders again.')
        outlook=demand_outlook(snapshot['inputs'],run)
        current_month=month(run_today(run),month_basis(run))
        if any(r['period']<current_month for r in outlook['rows']):
            raise ReleaseConflict('The source date includes a closed month. Refresh current orders before planning handoff.')
        # Unlike exploratory drafts, handoff requires all exceptions resolved,
        # including expired complete commitments and outside-horizon orders.
        issues=list(outlook['warnings'])+[r['issue'] for r in outlook['rows'] if r['issue']]
        if not outlook['can_export'] or issues:
            raise ReleaseConflict('Resolve demand inputs before sign-off. '+' '.join(dict.fromkeys(issues)))
        outlook['snapshot_id']=snapshot_id
        return snapshot,run,outlook

    def preview(self,payload):
        selected=contract(payload)
        snapshot,run,outlook=self.check(payload.get('snapshot_id',''))
        report={'snapshot_id':snapshot['id'],'snapshot_sha256':snapshot['sha256'],
            'run_id':run['run_id'],'run_sha256':digest(run),'contract':selected,
            'as_of':outlook['as_of'],'valid_until':outlook['valid_until'],
            'classification':outlook['classification'],'rows':len(outlook['rows']),
            'customers':len({r['customer'] for r in outlook['rows']}),
            'months':monthly(outlook,selected['mode']),
            'checked_on':run_today(run).isoformat(),
            'quantity_rule':'remaining' if selected['mode']=='remaining_forecast' else 'open_orders_plus_remaining',
            'fulfilled_excluded':True}
        report['review_token']=digest({'report':report,'outlook':outlook})
        return report,outlook,run

    def request(self,payload,actor):
        request_id=payload.get('request_id')
        if not isinstance(request_id,str) or not 8<=len(request_id)<=100:
            raise ValueError('A retry identifier is required.')
        if payload.get('reviewed') is not True:raise ValueError('Review all customers, products and months before submitting.')
        selected=contract(payload)
        fingerprint=digest({'snapshot_id':payload.get('snapshot_id'),'contract':selected,
                            'review_token':payload.get('review_token'),'actor':actor})
        key=hashlib.sha256(('demand-release:'+request_id).encode()).hexdigest()[:32]
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT fingerprint,release_id FROM demand_release_requests WHERE id=?',(request_id,)).fetchone()
            if prior:
                if prior[0]!=fingerprint:raise ReleaseConflict('This retry identifier was used for different release inputs.')
                return self.get(prior[1])
            report,outlook,run=self.preview(payload)
            if payload.get('review_token')!=report['review_token']:
                raise ReleaseConflict('Inputs changed. Review the release quantities again.')
            scope=digest({'run_id':run['run_id'],'receiver':selected['receiver']})
            version=db.execute('SELECT COALESCE(MAX(version),0)+1 FROM demand_releases WHERE scope=?',(scope,)).fetchone()[0]
            record={'id':key,'version':version,'scope':scope,'state':'awaiting_review',
                'snapshot_id':report['snapshot_id'],'snapshot_sha256':report['snapshot_sha256'],
                'run_id':run['run_id'],'run_sha256':report['run_sha256'],'contract':selected,
                'created_at':datetime.now(timezone.utc).isoformat(),'submitted_by':actor,
                'demo_only':actor['basis']=='local_demo','report':report,'outlook':outlook,
                'method':run.get('method_selection'), 'engine':run.get('engine'),
                'dataset_id':run.get('dataset_id'),'factor_evidence':run.get('scenario') if run.get('scenario',{}).get('type')=='factor_link' else None}
            db.execute('INSERT INTO demand_releases VALUES (?,?,?,?)',(key,scope,version,json.dumps(record,allow_nan=False)))
            db.execute('INSERT INTO demand_release_requests VALUES (?,?,?)',(request_id,fingerprint,key))
        return record

    def ready(self,record):
        snapshot,run,outlook=self.check(record['snapshot_id'])
        if snapshot['sha256']!=record['snapshot_sha256'] or digest(run)!=record['run_sha256']:
            raise ReleaseConflict('The approved inputs changed. Prepare a new release.')
        # Expiry or policy changes must not silently alter frozen approved numbers.
        fields=('rows','orders','as_of','valid_until','classification','policy')
        if digest({k:outlook[k] for k in fields})!=digest({k:record['outlook'][k] for k in fields}):
            raise ReleaseConflict('Demand changed since submission. Prepare a new release.')

    def detail(self,key,actor,role):
        record=self.get(key);blocked=''
        try:self.ready(record)
        except ValueError as exc:blocked=str(exc)
        with self.connect() as db:
            approved=[json.loads(r[0]) for r in db.execute('SELECT record FROM demand_releases WHERE scope=? ORDER BY version DESC',(record['scope'],))]
        latest=next((r for r in approved if r['state']=='approved'),None)
        superseded=bool(latest and latest['version']>record['version'])
        can_approve=(not blocked and not superseded and record['state']=='awaiting_review' and
            ((actor['basis']=='local_demo' and record['demo_only']) or
             (role in {'reviewer','approver','admin'} and actor!=record['submitted_by'] and not record['demo_only'])))
        return {**record,'blocked':blocked,'superseded':superseded,'can_approve':can_approve,
            'can_export':record['state']=='approved' and not blocked and not superseded}

    def approve(self,key,payload,actor,role):
        if payload.get('reviewed') is not True:raise ValueError('Review the complete demand plan before approval.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            record=self.get(key)
            if actor['basis']=='local_demo':
                if not record['demo_only'] or payload.get('demo_confirmed') is not True:
                    raise ValueError('Confirm this is a local demo approval, not company sign-off.')
            elif role not in {'reviewer','approver','admin'} or actor==record['submitted_by'] or record['demo_only']:
                raise PermissionError('A different company reviewer must approve this demand release.')
            if payload.get('review_token')!=record['report']['review_token']:
                raise ReleaseConflict('Review this exact demand release before approval.')
            if record['state']=='approved':
                if record['approved_by']!=actor:raise ReleaseConflict('This release was already approved by another reviewer.')
                return record
            self.ready(record)
            newer=[json.loads(r[0]) for r in db.execute('SELECT record FROM demand_releases WHERE scope=? AND version>?',(record['scope'],record['version']))]
            if any(r['state']=='approved' for r in newer):
                raise ReleaseConflict('A newer version is already approved. This older draft cannot replace it.')
            record.update(state='approved',approved_by=actor,approved_at=datetime.now(timezone.utc).isoformat())
            db.execute('UPDATE demand_releases SET record=? WHERE id=?',(json.dumps(record,allow_nan=False),key))
        return record

    def export(self,key,kind):
        record=self.get(key)
        if record['state']!='approved':raise ReleaseConflict('This demand release is awaiting review.')
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            self.ready(record)
            newer=[json.loads(r[0]) for r in db.execute('SELECT record FROM demand_releases WHERE scope=? AND version>?',(record['scope'],record['version']))]
            if any(r['state']=='approved' for r in newer):
                raise ReleaseConflict('A newer approved version replaced this release. Download that version instead.')
            metadata={'release_id':record['id'],'release_version':record['version'],
                'receiver':record['contract']['receiver'],'approval':'demo_approved' if record['demo_only'] else 'approved',
                'approved_at':record['approved_at'],'approved_by':json.dumps(record['approved_by'],ensure_ascii=False),
                'input_sha256':record['snapshot_sha256'],'run_sha256':record['run_sha256'],
                'dataset_id':record['dataset_id'],'method':record['method'],
                'engine_versions':json.dumps(record['engine'],ensure_ascii=False)}
            content,mime=export_demand(record['outlook'],record['contract']['mode'],kind,release_metadata=metadata)
        return content,mime,record


def install_demand_releases(app,store):
    router=APIRouter(prefix='/api/sales/releases')
    def actor(request):return identity(request.state.principal)
    def role(request):return (request.state.principal or {}).get('role','local')
    def call(fn):
        try:return fn()
        except PermissionError as exc:raise HTTPException(403,str(exc)) from exc
        except ReleaseConflict as exc:raise HTTPException(409,str(exc)) from exc
        except (ValueError,KeyError,TypeError) as exc:raise HTTPException(400,str(exc)) from exc

    @router.get('')
    def listing(request:Request,run_id:str=''):
        rows=store.list(run_id)
        # The review inbox must reflect current readiness, not just saved state.
        for row in rows:
            current=call(lambda:store.detail(row['id'],actor(request),role(request)))
            row.update({key:current[key] for key in ('blocked','superseded','can_approve','can_export')})
        return {'releases':rows}
    @router.post('/preview')
    def preview(payload:dict):return call(lambda:store.preview(payload)[0])
    @router.post('')
    def submit(payload:dict,request:Request):return call(lambda:store.request(payload,actor(request)))
    @router.get('/{key}')
    def detail(key:str,request:Request):return call(lambda:store.detail(key,actor(request),role(request)))
    @router.post('/{key}/approve')
    def approve(key:str,payload:dict,request:Request):return call(lambda:store.approve(key,payload,actor(request),role(request)))
    @router.get('/{key}/export')
    def export(key:str,kind:str='xlsx'):
        content,mime,record=call(lambda:store.export(key,kind))
        return Response(content,media_type=mime,headers={'Content-Disposition':f'attachment; filename="demand-release-{key}-v{record["version"]}.{kind}"'})
    app.include_router(router)
