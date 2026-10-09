"""Reusable customer directory; changes never rewrite saved demand snapshots."""
import csv
import io
import json
import sqlite3
import uuid
import unicodedata
from contextlib import contextmanager, nullcontext
import hashlib
from zipfile import BadZipFile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Product(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    sku: str = Field(min_length=1, max_length=200)
    unit: str = Field(min_length=1, max_length=80)


class Customer(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra='forbid')
    customer: str = Field(min_length=1, max_length=200)
    products: list[Product] = Field(default_factory=list, max_length=2000)
    active: bool = True
    external_id: str = Field(default='', max_length=160)
    aliases: list[str] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def unique_products(self):
        pairs = [(p.sku, p.unit) for p in self.products]
        if len(pairs) != len(set(pairs)):
            raise ValueError('Each product and unit should appear only once.')
        self.aliases = [a.strip() for a in self.aliases]
        if any(len(a)>200 for a in self.aliases):
            raise ValueError('Each alternative customer name must be at most 200 characters.')
        names=[name_key(n) for n in [self.customer,*self.aliases]]
        if any(not n for n in names) or len(names)!=len(set(names)):
            raise ValueError('Aliases must be nonempty, distinct and different from the customer name.')
        return self


def name_key(value):
    return unicodedata.normalize('NFKC',value).strip().casefold()


class CustomerBatch(BaseModel):
    customers: list[Customer] = Field(min_length=1, max_length=5000)


class CustomerStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS customers (id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, payload TEXT NOT NULL, updated_at TEXT NOT NULL)')
            db.execute('CREATE TABLE IF NOT EXISTS customer_import_receipts(id TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def list(self):
        with self.connect() as db:
            return [dict(id=r['id'], updated_at=r['updated_at'], **json.loads(r['payload'])) for r in db.execute('SELECT * FROM customers ORDER BY name COLLATE NOCASE')]

    def save(self, customers, customer_id=None, *, _db=None):
        ids = []
        try:
            with (nullcontext(_db) if _db is not None else self.connect()) as db:
                if _db is None:db.execute('BEGIN IMMEDIATE')
                if customer_id and not db.execute('SELECT 1 FROM customers WHERE id=?', (customer_id,)).fetchone():
                    raise HTTPException(404, 'Customer not found.')
                identities={};codes={}
                for row in db.execute('SELECT id,payload FROM customers'):
                    if row['id']==customer_id:continue
                    saved=json.loads(row['payload'])
                    for name in [saved['customer'],*saved.get('aliases',[])]:
                        identities[name_key(name)]=row['id']
                    if saved.get('external_id'):codes[saved['external_id']]=row['id']
                for customer in customers:
                    id_ = customer_id or uuid.uuid4().hex
                    for name in [customer.customer,*customer.aliases]:
                        key=name_key(name)
                        if key in identities:
                            raise HTTPException(409,'This name or alias belongs to another customer. No changes were saved.')
                        identities[key]=id_
                    if customer.external_id:
                        if customer.external_id in codes:
                            raise HTTPException(409,'This external customer ID already exists. No changes were saved.')
                        codes[customer.external_id]=id_
                    values = (customer.customer, customer.model_dump_json(), datetime.now(timezone.utc).isoformat(), id_)
                    if customer_id:
                        db.execute('UPDATE customers SET name=?,payload=?,updated_at=? WHERE id=?', values)
                    else:
                        db.execute('INSERT INTO customers(name,payload,updated_at,id) VALUES (?,?,?,?)', values)
                    ids.append(id_)
                for code, owner in codes.items():
                    if name_key(code) in identities and identities[name_key(code)] != owner:
                        raise HTTPException(409,'This external ID is another customer’s name or alias. No changes were saved.')
        except sqlite3.IntegrityError:
            raise HTTPException(409, 'A customer with that name already exists. Edit the existing customer; no changes were saved.')
        return {'ids': ids}

    @staticmethod
    def directory_hash(rows):
        return hashlib.sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest()

    def import_receipt(self,key):
        with self.connect() as db:row=db.execute('SELECT payload FROM customer_import_receipts WHERE id=?',(key,)).fetchone()
        return json.loads(row[0]) if row else None

    def import_connected(self,customers,key,expected_hash,provenance,request_hash,active_mapped=False):
        # Directory mutations and their receipt commit together. A retry after a
        # connection-receipt interruption cannot create/update the buyers twice.
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            receipt=db.execute('SELECT payload FROM customer_import_receipts WHERE id=?',(key,)).fetchone()
            if receipt:
                saved=json.loads(receipt[0])
                if saved['request_hash']!=request_hash:raise ValueError('This import was already saved with different review settings.')
                return saved
            existing=[dict(id=r['id'],updated_at=r['updated_at'],**json.loads(r['payload'])) for r in db.execute('SELECT * FROM customers ORDER BY name COLLATE NOCASE')]
            if self.directory_hash(existing)!=expected_hash:raise ValueError('Customers changed. Review this import again.')
            codes={r['external_id']:r for r in existing if r.get('external_id')}
            names={name_key(n):r for r in existing for n in [r['customer'],*r.get('aliases',[])]}
            ids=[]
            for incoming in customers:
                values=incoming.model_dump();old=codes.get(incoming.external_id) or names.get(name_key(incoming.customer))
                if old:
                    if incoming.external_id and old.get('external_id') and incoming.external_id!=old['external_id']:
                        raise ValueError('A source customer ID conflicts with the saved customer. Review the identity first.')
                    aliases=list(dict.fromkeys([*old.get('aliases',[]),*incoming.aliases,*([incoming.customer] if name_key(incoming.customer)!=name_key(old['customer']) else [])]))
                    products=list({(p['sku'],p['unit']):p for p in [*old['products'],*values['products']]}.values())
                    values.update(customer=old['customer'],aliases=aliases,products=products,external_id=incoming.external_id or old.get('external_id',''))
                    if not active_mapped:values['active']=old['active']
                result=self.save([Customer(**values)],old['id'] if old else None,_db=db)
                ids+=result['ids']
                # Source duplicates resolving to one saved identity are unsafe.
                if len(ids)!=len(set(ids)):raise ValueError('Multiple source customers match the same saved customer.')
            result=dict(kind='customers',ids=ids,count=len(ids),request_hash=request_hash,provenance=provenance)
            db.execute('INSERT INTO customer_import_receipts VALUES (?,?)',(key,json.dumps(result,ensure_ascii=False)))
            return result


def parse_customers(rows):
    grouped = {}
    for index, row in enumerate(rows, 2):
        customer = str(row.get('customer') or '').strip()
        sku, unit = str(row.get('sku') or '').strip(), str(row.get('unit') or '').strip()
        if not any((customer, sku, unit)):
            continue
        if not customer or bool(sku) != bool(unit):
            raise ValueError(f'Row {index}: customer is required; each product needs both sku and unit.')
        code=str(row.get('external_id') or '').strip()
        aliases=[v.strip() for v in str(row.get('aliases') or '').split('|') if v.strip()]
        entry = grouped.setdefault(customer, {'customer': customer, 'products': [],'external_id':code,'aliases':aliases})
        if entry['external_id']!=code or entry['aliases']!=aliases:
            raise ValueError(f'Row {index}: repeat the same external ID and aliases for this customer.')
        product = {'sku': sku, 'unit': unit}
        if sku and product not in entry['products']:
            entry['products'].append(product)
    return CustomerBatch(customers=list(grouped.values()))


def install_customer_routes(app: FastAPI, store: CustomerStore):
    @app.get('/api/customers')
    def list_customers():
        return {'customers': store.list()}

    @app.post('/api/customers')
    def add_customers(body: CustomerBatch):
        return store.save(body.customers)

    @app.put('/api/customers/{customer_id}')
    def edit_customer(customer_id: str, body: Customer):
        return store.save([body], customer_id)

    @app.post('/api/customers/preview')
    async def preview_customers(file: UploadFile = File(...)):
        raw = await file.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise HTTPException(413, 'Use a customer file smaller than 5 MB.')
        try:
            suffix = Path(file.filename or '').suffix.lower()
            if suffix == '.csv':
                rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
            elif suffix == '.xlsx':
                import pandas as pd
                rows = pd.read_excel(io.BytesIO(raw), dtype=str, keep_default_na=False, nrows=20001).to_dict('records')
            else:
                raise ValueError('Choose a CSV or XLSX file.')
            if len(rows) > 20000:
                raise ValueError('Use at most 20,000 product rows per file.')
            rows = [{str(k).strip().lower(): v for k, v in row.items()} for row in rows]
            return parse_customers(rows).model_dump()
        except (ValueError, UnicodeError, OSError, BadZipFile, EOFError) as exc:
            raise HTTPException(422, str(exc))
