"""Reviewed customer/order captures using existing directory, order and table tools."""
import json
from datetime import date
from typing import Literal
from pydantic import Field
from .platform_sales_api import StrictInput
from .customers import parse_customers,Customer,CustomerStore,name_key
from .inventory import raw_table,text_value
from .sales_demand import import_rows,revise_orders,validate_inputs
from .order_books import BookRequest
from .input_review import digest
from .business_connections import ConnectionError,ConnectionConflict


class RowReview(StrictInput):
    mapping:dict[str,str]=Field(default_factory=dict,max_length=20)
    sheet:str|None=Field(default=None,max_length=200)
    header_row:int=Field(default=1,ge=1,le=200,strict=True)
    calendar:Literal['gregorian','jalali']='gregorian'
    order_mode:Literal['changes','replace']='changes'
    as_of:date|None=None
    valid_until:date|None=None
    order_feed:Literal['unknown','complete_snapshot']='unknown'
    confirm_empty:bool=False
    reviewed:bool=False
    review_token:str|None=Field(default=None,pattern=r'^[a-f0-9]{64}$')


def request_hash(body):
    return digest(body.model_dump(mode='json',exclude={'reviewed','review_token'}))


def rows_preview(workspace,candidate,body):
    sources=workspace.datasets
    source,content=sources.source(candidate['source_id'])
    table=raw_table(source['name'],content,body.sheet,body.header_row)
    directory=workspace.customers.list()
    proof={'connection_id':candidate['connection_id'],'connection_version':candidate['version'],
           'candidate_id':candidate['id'],'source_id':source['id'],'source_sha256':source['sha256'],
           'mapping':body.mapping,'sheet':table['sheet'],'header_row':body.header_row,'calendar':body.calendar}
    expected=CustomerStore.directory_hash(directory)
    if candidate['role']=='sales_customers':
        allowed={'customer','sku','unit','external_id','aliases','active'}
        cols={r['id'] for r in table['columns']}
        selected=[v for v in body.mapping.values() if v]
        if set(body.mapping)-allowed or any(v not in cols for v in selected) or len(set(selected))!=len(selected) or not body.mapping.get('customer'):
            raise ConnectionError('Map customer fields to distinct source columns.')
        if table['formulas']:raise ConnectionError('Export values, not formulas, before reviewing customers.')
        records=[{k:text_value(row['values'].get(v)) for k,v in body.mapping.items() if v} for row in table['rows']]
        customers=parse_customers(records).customers
        if len(records)>20000:raise ConnectionError('Use at most 20,000 customer product rows.')
        for c in customers:
            matches=[r for r in records if r.get('customer')==c.customer]
            if body.mapping.get('active'):
                values={r.get('active','').strip().casefold() for r in matches}
                if len(values)!=1 or not values.issubset({'true','false','1','0'}):raise ConnectionError('Customer active status must be true/false or 1/0 and consistent.')
                c.active=values.pop() in {'true','1'}
        rows=[c.model_dump(mode='json') for c in customers]
        target={'directory_hash':expected}
        result={'kind':'customers','rows':rows,'count':len(rows),'target':target,'provenance':proof}
    elif candidate['role']=='sales_orders':
        dataset_id=candidate['parent_dataset_id']
        if not dataset_id:raise ConnectionError('Choose sales data before connecting orders.')
        config={**body.model_dump(mode='json'),'source_id':source['id']}
        identities={name_key(n):r['customer'] for r in directory for n in [r['customer'],*r.get('aliases',[]),r.get('external_id','')] if n}
        customer_col=body.mapping.get('customer')
        config['customer_matches']={text_value(r['values'].get(customer_col)):identities[name_key(text_value(r['values'].get(customer_col)))]
            for r in table['rows'] if name_key(text_value(r['values'].get(customer_col))) in identities}
        rows,evidence=import_rows(sources,'orders',config)
        book=workspace.order_books.get(dataset_id)
        if not body.as_of or not body.valid_until:raise ConnectionError('Review the order source date and review-again date.')
        if not rows and body.order_mode=='replace' and not body.confirm_empty:raise ConnectionError('Confirm an empty full order book before replacing saved orders.')
        if body.order_mode=='changes' and body.order_feed!='unknown':raise ConnectionError('Changed lines do not establish complete order coverage.')
        merged,changes=revise_orders(book['inputs']['orders'],rows,body.order_mode,body.as_of)
        values=dict(version=book['version'],as_of=str(body.as_of),valid_until=str(body.valid_until),order_feed=body.order_feed,orders=merged)
        validate_inputs({**book['inputs'],**{k:v for k,v in values.items() if k!='version'},'reviewed':True,'note':'Connected order export reviewed.'},book['context'])
        target={'dataset_id':dataset_id,'book_version':book['version'],'directory_hash':expected}
        proof['order_evidence']=evidence
        result={'kind':'orders','rows':rows,'count':len(rows),'changes':changes,'target':target,'provenance':proof,'book':values}
    else:raise ConnectionError('Use the sales-data review for this input type.')
    result['review_token']=digest({'candidate':candidate['id'],'source_sha256':source['sha256'],'target':target,
                                 'request':request_hash(body),'rows':result['rows']})
    return result


def accept_rows(workspace,candidate,body):
    if not body.reviewed or not body.review_token:raise ConnectionError('Review the captured rows before saving.')
    store=workspace.customers if candidate['role']=='sales_customers' else workspace.order_books
    prior=store.import_receipt(candidate['id'])
    fingerprint=request_hash(body)
    if prior:
        if prior['request_hash']!=fingerprint:raise ConnectionConflict('This import was already saved with different review settings.')
        result=prior
    else:
        report=rows_preview(workspace,candidate,body)
        if report['review_token']!=body.review_token:raise ConnectionConflict('Inputs changed. Review this import again.')
        if report['kind']=='customers':
            result=store.import_connected([Customer(**r) for r in report['rows']],candidate['id'],report['target']['directory_hash'],
                report['provenance'],fingerprint,bool(body.mapping.get('active')))
        else:
            if CustomerStore.directory_hash(workspace.customers.list())!=report['target']['directory_hash']:
                raise ConnectionConflict('Customers changed. Review this import again.')
            result=store.save(candidate['parent_dataset_id'],BookRequest(**report['book']),receipt_id=candidate['id'],
                provenance=report['provenance'],request_hash=fingerprint)
    with workspace.connections.db() as db:
        db.execute('INSERT OR IGNORE INTO import_acceptance VALUES (?,?)',(candidate['id'],json.dumps(result,ensure_ascii=False)))
    return result
