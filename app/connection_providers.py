"""Read-only provider adapters; shared network policy, official Google auth, httpx.

No provider write methods, user-supplied RPC/model names or implicit date/unit fixes.
"""
import csv
import io
import json
import time
from datetime import datetime,timezone
from decimal import Decimal
from zoneinfo import ZoneInfo
from types import SimpleNamespace
from urllib.parse import quote,urlsplit
import httpx
from .business_connections import ConnectionError,LIMIT


def request(fetcher,url,method='GET',body=None,headers=None):
    parsed=urlsplit(url)
    if parsed.scheme!='https' or parsed.port not in {None,443} or parsed.username or parsed.password:
        raise ConnectionError('Provider address is invalid.')
    address=fetcher.policy.resolve(parsed.hostname,443)[4][0]
    host=f'[{address}]' if ':' in address else address
    endpoint=f'https://{host}{parsed.path or "/"}'+('?' + parsed.query if parsed.query else '')
    supplied=dict(headers or {});supplied['Host']=parsed.hostname
    with httpx.Client(timeout=httpx.Timeout(20,connect=5),follow_redirects=False,trust_env=False,transport=fetcher.transport) as client:
        with client.stream(method,endpoint,headers=supplied,content=body,extensions={'sni_hostname':parsed.hostname}) as response:
            if response.status_code!=200:raise ConnectionError('Provider access failed. Check the account, API access and read permissions.')
            chunks,size,deadline=[],0,time.monotonic()+30
            for chunk in response.iter_bytes(chunk_size=65536):
                size+=len(chunk)
                if size>LIMIT or time.monotonic()>deadline:raise ConnectionError('The source exceeds the input size or time limit.')
                chunks.append(chunk)
            return b''.join(chunks),dict(response.headers)


def sheets(fetcher,config,credential):
    if not credential:raise ConnectionError('Add the Google service account before fetching.')
    from google.oauth2 import service_account
    info=json.loads(credential)
    # Never trust token URLs, delegation or universe domains inside an uploaded key.
    if info.get('type')!='service_account' or not str(info.get('client_email','')).endswith('.iam.gserviceaccount.com'):
        raise ConnectionError('Use a Google service-account key shared with this spreadsheet.')
    safe={k:info[k] for k in ('client_email','private_key','private_key_id','client_id') if k in info}
    safe['token_uri']='https://oauth2.googleapis.com/token'
    auth=service_account.Credentials.from_service_account_info(safe,scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
    def token_request(url,method='GET',body=None,headers=None,**kwargs):
        if url!='https://oauth2.googleapis.com/token':raise ConnectionError('Google authentication destination is invalid.')
        data,response_headers=request(fetcher,url,method,body,headers)
        return SimpleNamespace(status=200,data=data,headers=response_headers)
    auth.refresh(token_request)
    worksheet="'"+config['sheet_range'].replace("'","''")+"'"
    url=f'https://sheets.googleapis.com/v4/spreadsheets/{config["spreadsheet_id"]}/values/{quote(worksheet,safe="")}?majorDimension=ROWS&valueRenderOption=FORMATTED_VALUE'
    payload,_=request(fetcher,url,headers={'Authorization':'Bearer '+auth.token})
    data=json.loads(payload)
    values=data.get('values')
    if not isinstance(values,list) or not values or any(not isinstance(r,list) for r in values):
        raise ConnectionError('The Google worksheet is empty or invalid.')
    width=max(map(len,values))
    if width>500 or len(values)*width>1000000:raise ConnectionError('The Google worksheet exceeds the input limit.')
    output=io.StringIO();writer=csv.writer(output)
    for row in values:writer.writerow(row+['']*(width-len(row)))
    return output.getvalue().encode('utf-8')


class OdooReader:
    def __init__(self,fetcher,config,credential):
        if not credential:raise ConnectionError('Add the read-only Odoo API key before fetching.')
        if any(c in credential for c in '\r\n'):raise ConnectionError('The source credential is invalid.')
        self.fetcher,self.config,self.credential=fetcher,config,credential
        self.uid=None;self.deadline=time.monotonic()+120
        if config['provider']=='odoo18':
            self.uid=self.rpc('common','authenticate',[config['database'],config['username'],credential,{}])
            if type(self.uid)!=int or self.uid<1:raise ConnectionError('Odoo authentication failed.')

    def rpc(self,service,method,args):
        body=json.dumps({'jsonrpc':'2.0','method':'call','params':{'service':service,'method':method,'args':args},'id':1}).encode()
        raw,_=request(self.fetcher,self.config['url'].rstrip('/')+'/jsonrpc','POST',body,{'Content-Type':'application/json'})
        result=json.loads(raw)
        if result.get('error') or 'result' not in result:raise ConnectionError('Odoo read failed. Check API access, installed Sales fields and permissions.')
        return result['result']

    def page(self,model,domain,fields):
        if time.monotonic()>self.deadline:raise ConnectionError('Odoo export exceeded the time limit. Use a complete server export instead.')
        kw={'domain':domain,'fields':fields,'limit':1000,'order':'id asc',
            'context':{'allowed_company_ids':[self.config['odoo_company_id']],'lang':'en_US','active_test':False}}
        if self.config['provider']=='odoo18':
            return self.rpc('object','execute_kw',[self.config['database'],self.uid,self.credential,model,'search_read',[],kw])
        headers={'Content-Type':'application/json','Authorization':'Bearer '+self.credential,'X-Odoo-Database':self.config['database']}
        raw,_=request(self.fetcher,self.config['url'].rstrip('/')+'/json/2/'+model+'/search_read','POST',json.dumps(kw).encode(),headers)
        data=json.loads(raw)
        if not isinstance(data,list):raise ConnectionError('Odoo did not return a complete record list.')
        return data

    def records(self,model,domain,fields):
        rows=[];last=0
        while True:
            page=self.page(model,[*domain,['id','>',last]],fields)
            if not isinstance(page,list) or len(page)>1000:raise ConnectionError('Odoo pagination is invalid.')
            for r in page:
                if not isinstance(r,dict) or type(r.get('id'))!=int or r['id']<=last:raise ConnectionError('Odoo pagination is invalid.')
                last=r['id'];rows.append(r)
            if len(rows)>50000:raise ConnectionError('Odoo export exceeds 50,000 records. Use a complete server export instead.')
            if len(page)<1000:break
        return rows

    def snapshot(self):
        company=self.config['odoo_company_id']
        if self.config['role']=='sales_customers':
            partners=self.records('res.partner',[['customer_rank','>',0],'|',['company_id','=',False],['company_id','=',company]],
                                  ['id','name','active','write_date'])
            return {'partners':partners}
        orders=self.records('sale.order',[['company_id','=',company]],['id','name','partner_id','commitment_date','state','write_date'])
        ids=[r['id'] for r in orders]
        lines=self.records('sale.order.line',[['order_id','in',ids],['display_type','=',False]],
            ['id','order_id','product_id','product_uom_id' if self.config['provider']=='odoo19' else 'product_uom',
             'product_uom_qty','qty_delivered','write_date']) if ids else []
        # Order partners may include delivery contacts that have no customer_rank.
        partner_ids=sorted({r['partner_id'][0] for r in orders if r.get('partner_id')})
        partners=self.records('res.partner',[['id','in',partner_ids]],['id','name','active','write_date']) if partner_ids else []
        product_ids=sorted({r['product_id'][0] for r in lines if r.get('product_id')})
        products=self.records('product.product',[['id','in',product_ids]],['id','default_code','write_date']) if product_ids else []
        uom='product_uom_id' if self.config['provider']=='odoo19' else 'product_uom'
        unit_ids=sorted({r[uom][0] for r in lines if r.get(uom)})
        units=self.records('uom.uom',[['id','in',unit_ids]],['id','name','write_date']) if unit_ids else []
        return {'partners':partners,'orders':orders,'lines':lines,'products':products,'units':units}


def odoo(fetcher,config,credential):
    reader=OdooReader(fetcher,config,credential)
    snapshot=reader.snapshot()
    # No transaction spans multiple external calls. Compare all values a second
    # time; reject moving exports instead of claiming an atomic remote snapshot.
    if snapshot!=reader.snapshot():raise ConnectionError('Odoo records changed while reading. Fetch again after the update finishes.')
    company=config['odoo_company_id']
    def code(identifier):return f'odoo:{company}:{identifier}'
    if config['role']=='sales_customers':
        rows=[{'customer':r['name'],'external_id':code(r['id']),'active':r['active']} for r in snapshot['partners']]
    else:
        orders={r['id']:r for r in snapshot['orders']};partners={r['id']:r for r in snapshot['partners']}
        products={r['id']:r for r in snapshot['products']};units={r['id']:r for r in snapshot['units']};rows=[]
        codes=[str(r.get('default_code') or '').strip() for r in products.values()]
        if any(not c for c in codes) or len(set(codes))!=len(codes):
            raise ConnectionError('Odoo products need unique SKU codes before import.')
        uom='product_uom_id' if config['provider']=='odoo19' else 'product_uom'
        for line in snapshot['lines']:
            order=orders[line['order_id'][0]]
            if not order.get('commitment_date'):raise ConnectionError('Odoo orders need confirmed delivery dates. No dates were guessed.')
            product=products[line['product_id'][0]];partner=partners[order['partner_id'][0]]
            if not product.get('default_code'):raise ConnectionError('Odoo products need unique SKU codes before import.')
            ordered,fulfilled=line['product_uom_qty'],line['qty_delivered']
            delivery=datetime.fromisoformat(order['commitment_date']).replace(tzinfo=timezone.utc).astimezone(ZoneInfo(config['timezone'])).date().isoformat()
            state=order['state'];status='cancelled' if state=='cancel' else 'unconfirmed' if state in {'draft','sent'} else 'confirmed' if state in {'sale','done'} else None
            if status is None:raise ConnectionError('Odoo order status is not supported. Review the source status mapping.')
            rows.append(dict(reference=f'odoo:{company}:{order["id"]}:{line["id"]}',customer=code(partner['id']),sku=product['default_code'],
                unit=units[line[uom][0]]['name'],due_date=delivery,ordered=ordered,fulfilled=fulfilled,
                cancelled=str(Decimal(str(ordered))-Decimal(str(fulfilled))) if state=='cancel' else '0',status=status))
    # A JSON array is a complete captured table, not a provider pagination wrapper.
    return json.dumps(rows,ensure_ascii=False,allow_nan=False).encode()


def provider_fetch(fetcher,config,credential):
    return sheets(fetcher,config,credential) if config['provider']=='sheets' else odoo(fetcher,config,credential)
