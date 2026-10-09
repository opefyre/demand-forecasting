"""Owned reviews of evidence-backed decisions, separate from forecast quantities."""
from contextlib import contextmanager
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False).encode()).hexdigest()


class DecisionConflict(ValueError): pass


class DecisionStore:
    def __init__(self, path):
        self.path=Path(path)
        self.path.parent.mkdir(parents=True,exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS decisions (scope TEXT NOT NULL, id TEXT NOT NULL, record TEXT NOT NULL, PRIMARY KEY(scope,id))')
            db.execute('CREATE TABLE IF NOT EXISTS decision_requests (id TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, response TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db=sqlite3.connect(self.path,timeout=30)
        try:
            with db: yield db
        finally: db.close()

    def context(self, today):
        context=today.get('context')
        if not context: raise ValueError('Choose a saved forecast before assigning a review.')
        return {'site_id':today['site']['id'], **{key:context.get(key) for key in
            ('run_id','plan_id','unit','frequency','source_classification')}}

    def token(self, today, decision):
        return digest({'context':self.context(today),'evidence':{k:v for k,v in decision.items() if k not in {'tracking','evidence_token'}}})

    def decorate(self, today):
        if not today.get('context'): return today
        scope=digest(self.context(today))
        with self.connect() as db:
            records={key:json.loads(record) for key,record in db.execute('SELECT id,record FROM decisions WHERE scope=?',(scope,))}
        for decision in today['decisions']:
            token=self.token(today,decision)
            record=records.get(decision['id'])
            changed=bool(record and record['evidence_token']!=token)
            tracking=dict(record or {'version':0,'owner':'','due_date':'','status':'open','history':[]})
            if changed: tracking['status']='open'
            tracking['evidence_changed']=changed
            tracking['overdue']=bool(tracking['due_date'] and tracking['due_date']<today['date'] and tracking['status']!='reviewed')
            decision.update(evidence_token=token,tracking=tracking)
        return today

    def update(self, today, decision_id, *, evidence_token, version, owner, due_date, status, note, request_id, identity=None):
        context=self.context(today)
        decision=next((d for d in today['decisions'] if d['id']==decision_id),None)
        if not decision: raise DecisionConflict('This issue is no longer in the selected evidence. Refresh the queue.')
        if self.token(today,decision)!=evidence_token:
            raise DecisionConflict('The evidence changed. Refresh the queue before recording a decision.')
        if type(version) is not int or version<0: raise ValueError('Invalid review version.')
        if not isinstance(owner,str) or not 1<=len(owner.strip())<=120: raise ValueError('Enter an owner name (up to 120 characters).')
        try:
            if date.fromisoformat(due_date).isoformat()!=due_date: raise ValueError()
        except (TypeError,ValueError): raise ValueError('Choose a valid due date.') from None
        if not isinstance(status,str) or status not in {'open','in_progress','reviewed'}: raise ValueError('Choose To do, In progress or Reviewed.')
        if not isinstance(note,str) or not 3<=len(note.strip())<=2000: raise ValueError('Record a short action or decision (3–2,000 characters).')
        if not isinstance(request_id,str) or not 1<=len(request_id)<=200: raise ValueError('A save request identifier is required.')
        actor={**identity,'basis':'company_sign_in'} if identity else {'name':'Local session','basis':'local_session'}
        change=dict(context=context,decision_id=decision_id,evidence_token=evidence_token,version=version,
            owner=owner.strip(),due_date=due_date,status=status,note=note.strip(),actor=actor)
        fingerprint=digest(change); scope=digest(context)
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            prior=db.execute('SELECT fingerprint,response FROM decision_requests WHERE id=?',(request_id,)).fetchone()
            if prior:
                if prior[0]!=fingerprint: raise DecisionConflict('This save request was used for a different change.')
                return json.loads(prior[1])
            row=db.execute('SELECT record FROM decisions WHERE scope=? AND id=?',(scope,decision_id)).fetchone()
            previous=json.loads(row[0]) if row else None
            if (previous['version'] if previous else 0)!=version:
                raise DecisionConflict('Another planner updated this review. Refresh before saving your changes.')
            event=dict(at=datetime.now(timezone.utc).isoformat(),owner=owner.strip(),due_date=due_date,status=status,
                note=note.strip(),actor=actor,evidence_token=evidence_token,
                evidence={k:v for k,v in decision.items() if k not in {'tracking','evidence_token'}})
            record=dict(context=context,decision_id=decision_id,version=version+1,evidence_token=evidence_token,
                evidence={k:v for k,v in decision.items() if k not in {'tracking','evidence_token'}},
                owner=owner.strip(),due_date=due_date,status=status,history=(previous['history'] if previous else [])+[event])
            db.execute('INSERT INTO decisions VALUES (?,?,?) ON CONFLICT(scope,id) DO UPDATE SET record=excluded.record',
                       (scope,decision_id,json.dumps(record)))
            db.execute('INSERT INTO decision_requests VALUES (?,?,?)',(request_id,fingerprint,json.dumps(record)))
        return record
