"""Reusable order books connected to a sales-history lineage, not a calculation."""
from contextlib import closing
from datetime import timedelta
import json
import sqlite3
from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .sales_demand import SalesOrder, validate_inputs, run_today
from .forecast_orders import starter


def lineage(store, identifier):
    seen = set()
    while identifier not in seen:
        seen.add(identifier)
        dataset = store.get(identifier)
        if not dataset.get('parent_dataset_id'):
            return identifier
        identifier = dataset['parent_dataset_id']
    raise ValueError('Sales history lineage is invalid.')


def directory_inputs(data, customers):
    inputs = data['inputs']
    # Unattributed history remains explicitly unattributed, never allocated to
    # named buyers without customer-level evidence.
    for row in inputs['customers']:
        row['customer'] = row['customer'] or 'Unassigned demand'
        row['sku'] = row['sku'] or row['series_id']
    existing = {(c['customer'], c['sku'], c['unit']) for c in inputs['customers']}
    products={c['sku'] for c in inputs['customers']}
    for customer in customers:
        if not customer['active']:
            continue
        for product in customer['products']:
            key = (customer['customer'], product['sku'], product['unit'])
            if key not in existing and product['sku'] in products and product['unit'] == data['context']['unit']:
                inputs['customers'].append(dict(customer=key[0],sku=key[1],unit=key[2],series_id=''))
                existing.add(key)
    return data


class BookRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=0, strict=True)
    as_of: str
    valid_until: str
    order_feed: str
    orders: list[SalesOrder] = Field(max_length=50000)


class OrderBooks:
    def __init__(self, path, datasets, customers):
        self.path,self.datasets,self.customers = path,datasets,customers
        with closing(sqlite3.connect(path)) as con:
            con.execute('CREATE TABLE IF NOT EXISTS order_books (id TEXT PRIMARY KEY, version INTEGER, payload TEXT)')
            con.commit()

    def get(self, identifier):
        data = directory_inputs(starter(self.datasets,identifier), self.customers.list())
        with closing(sqlite3.connect(self.path)) as con:
            row=con.execute('SELECT version,payload FROM order_books WHERE id=?',(lineage(self.datasets,identifier),)).fetchone()
        if row:
            data['inputs'].update(json.loads(row[1]))
        else:
            data['inputs']['valid_until']=str(run_today(data['context'])+timedelta(days=30))
        data['version']=row[0] if row else 0
        return data

    def save(self, identifier, payload):
        data=self.get(identifier)
        inputs={**data['inputs'],**payload.model_dump(mode='json',exclude={'version'}),
                'reviewed':True,'note':'Order book reviewed and saved by the planner.'}
        checked=validate_inputs(inputs,data['context']).model_dump(mode='json')
        keep={key:checked[key] for key in ('as_of','valid_until','order_feed','orders')}
        with closing(sqlite3.connect(self.path,timeout=30)) as con:
            con.execute('BEGIN IMMEDIATE')
            key=lineage(self.datasets,identifier)
            current=con.execute('SELECT version FROM order_books WHERE id=?',(key,)).fetchone()
            if (current[0] if current else 0)!=payload.version:
                raise ValueError('Orders changed. Reload the order book before saving.')
            con.execute('INSERT OR REPLACE INTO order_books VALUES (?,?,?)',(key,payload.version+1,json.dumps(keep)))
            con.commit()
        return self.get(identifier)


def install_order_books(app,store):
    @app.get('/api/order-books/{dataset_id}')
    def get_book(dataset_id:str):
        try:return store.get(dataset_id)
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc

    @app.put('/api/order-books/{dataset_id}')
    def save_book(dataset_id:str,payload:BookRequest):
        try:return store.save(dataset_id,payload)
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
