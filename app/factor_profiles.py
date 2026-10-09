"""Versioned customer/product defaults. Never changes forecasts or orders."""
import json
from datetime import datetime, timezone
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .commodity_prices import SERIES
from .factor_context import FactorContext


class ProfileChange(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, str_strip_whitespace=True)
    sku: str = Field(default='', max_length=200)
    unit: str = Field(default='', max_length=80)
    expected_revision: int = Field(ge=0)
    context: FactorContext | None


class FactorProfiles:
    def __init__(self, customers):
        self.customers = customers
        with customers.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS factor_profiles '
                       '(customer_id TEXT, sku TEXT, unit TEXT, revision INTEGER, payload TEXT, updated_at TEXT, '
                       'PRIMARY KEY(customer_id,sku,unit,revision))')

    def customer(self, identifier):
        found=next((c for c in self.customers.list() if c['id']==identifier),None)
        if not found: raise ValueError('Customer not found.')
        return found

    def rows(self, identifier):
        with self.customers.connect() as db:
            return [dict(customer_id=r['customer_id'],sku=r['sku'],unit=r['unit'],
                         revision=r['revision'],updated_at=r['updated_at'],context=json.loads(r['payload']))
                    for r in db.execute('SELECT p.* FROM factor_profiles p WHERE customer_id=? '
                        'AND revision=(SELECT MAX(revision) FROM factor_profiles q WHERE '
                        'q.customer_id=p.customer_id AND q.sku=p.sku AND q.unit=p.unit) ORDER BY sku,unit',(identifier,))]

    def listing(self, identifier):
        return {'customer':self.customer(identifier),'profiles':self.rows(identifier),
                'materials':[[key,name] for key,(name,_) in SERIES.items()]}

    def save(self, identifier, payload):
        value=ProfileChange.model_validate(payload)
        customer=self.customer(identifier)
        if not customer['active']:raise ValueError('Activate this customer before changing factor profiles.')
        if bool(value.sku)!=bool(value.unit):raise ValueError('A product profile needs both SKU and unit.')
        if value.sku and {'sku':value.sku,'unit':value.unit} not in customer['products']:
            raise ValueError('Choose a product and unit linked to this customer.')
        with self.customers.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            current=db.execute('SELECT MAX(revision) FROM factor_profiles WHERE customer_id=? AND sku=? AND unit=?',
                               (identifier,value.sku,value.unit)).fetchone()[0] or 0
            if current!=value.expected_revision:
                raise HTTPException(409,'This profile changed. Reopen it before saving.')
            db.execute('INSERT INTO factor_profiles VALUES (?,?,?,?,?,?)',
                (identifier,value.sku,value.unit,current+1,
                 json.dumps(value.context.model_dump() if value.context is not None else None),
                 datetime.now(timezone.utc).isoformat()))
        return next(r for r in self.rows(identifier) if (r['sku'],r['unit'])==(value.sku,value.unit))

    def for_run(self, run):
        result=[]
        by_customer={}
        for series_id in sorted(set(run.get('series',{}))-{'__all__'}):
            meta=run.get('metadata',{}).get(series_id,{})
            by_customer.setdefault(meta.get('customer'),[]).append((series_id,meta))
        for c in self.customers.list():
            if not c['active'] or c['customer'] not in by_customer:continue
            profiles=self.rows(c['id'])
            default=next((r for r in profiles if not r['sku'] and r['context'] is not None),None)
            for series_id,meta in by_customer[c['customer']]:
                # Only the reviewed canonical name matches. No fuzzy aliases or unit conversion.
                if meta.get('customer')!=c['customer']:continue
                sku=meta.get('sku','');unit=run.get('unit','')
                if not sku or not unit:continue
                product=next((r for r in profiles if r['sku']==sku and r['unit']==unit
                              and {'sku':sku,'unit':unit} in c['products'] and r['context'] is not None),None)
                chosen=product or default
                if chosen:
                    result.append({**chosen,'series_id':series_id,'customer':c['customer'],
                                   'target_sku':sku,'target_unit':unit,
                                   'inherited':product is None,'customer_updated_at':c['updated_at']})
        return {'profiles':result,'note':'Exact canonical customer, SKU and unit only. Product profiles replace customer defaults. No factors or orders are changed.'}


def install_profile_routes(app, profiles):
    @app.get('/api/customers/{customer_id}/factor-profiles')
    def list_profiles(customer_id: str):
        try:return profiles.listing(customer_id)
        except ValueError as exc:raise HTTPException(404,str(exc)) from exc

    @app.put('/api/customers/{customer_id}/factor-profiles')
    def save_profile(customer_id: str, body: ProfileChange):
        try:return profiles.save(customer_id,body.model_dump())
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
