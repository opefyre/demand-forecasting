"""Apprise adapters inside a bounded child process; no SDK logging in the app."""
import json
import os
from pathlib import Path
import subprocess
import sys


class IsolatedSender:
    def send(self,config,secret,text,link):
        # Secrets use stdin, never command arguments, files or inherited credentials.
        payload=dict(config=config,secret=secret,text=text,link=link)
        env={k:v for k,v in os.environ.items() if k in {'PATH','SYSTEMROOT','WINDIR','LANG'}}
        try:
            result=subprocess.run([sys.executable,'-m','app.notification_sender'],
                cwd=Path(__file__).resolve().parents[1],env=env,input=json.dumps(payload).encode(),
                stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=35,check=False)
            answer=json.loads(result.stdout) if result.returncode==0 and len(result.stdout)<500 else {}
            return answer.get('state','unknown')
        except (subprocess.TimeoutExpired,ValueError,OSError):return 'unknown'


class PinnedRequests:
    """Small requests/httpx bridge. Apprise still builds and validates messages."""
    def __init__(self,host,*,policy=None,transport=None):
        from .business_connections import TargetPolicy
        self.host=host;self.policy=policy or TargetPolicy();self.transport=transport
        self.codes=[]

    def request(self,method,url,**kwargs):
        import httpx
        import requests
        import time
        from urllib.parse import urlsplit
        parsed=urlsplit(url)
        if (method.upper()!='POST' or parsed.scheme!='https' or parsed.hostname!=self.host or
                parsed.port not in {None,443} or parsed.username or parsed.password or parsed.fragment or
                kwargs.get('files') or kwargs.get('allow_redirects') or kwargs.get('verify') is False):
            raise requests.RequestException('Blocked notification request.')
        # Exactly one destination and one POST per attempt, no retry/split/lookup.
        if self.codes:raise requests.RequestException('Notification attempt already used.')
        address=self.policy.resolve(self.host,443)[4][0]
        ip='['+address+']' if ':' in address else address
        endpoint='https://'+ip+(parsed.path or '/')+('?' + parsed.query if parsed.query else '')
        headers={**kwargs.get('headers',{}),'Host':self.host}
        try:
            with httpx.Client(timeout=httpx.Timeout(15,connect=5),trust_env=False,follow_redirects=False,transport=self.transport) as client:
                with client.stream('POST',endpoint,headers=headers,params=kwargs.get('params'),
                        content=kwargs.get('data'),json=kwargs.get('json'),extensions={'sni_hostname':self.host}) as response:
                    self.codes.append(response.status_code);content=bytearray();deadline=time.monotonic()+20
                    for chunk in response.iter_bytes(chunk_size=4096):
                        content.extend(chunk)
                        if len(content)>65536 or time.monotonic()>deadline:raise requests.RequestException('Notification response limit exceeded.')
                    result=requests.Response();result.status_code=response.status_code;result._content=bytes(content)
                    result.headers.update(response.headers)
                    return result
        except httpx.HTTPError:raise requests.RequestException('Notification network error.') from None

    def post(self,url,**kwargs):return self.request('POST',url,**kwargs)


def deliver(payload,transport_factory=PinnedRequests):
    """Called only in the isolated child (or isolated tests), never app threads."""
    from apprise import Apprise,AppriseAsset,NotifyFormat
    from unittest.mock import patch
    from urllib.parse import quote,urlsplit
    config,secret=payload['config'],payload['secret']
    text=payload['text']+'\n'+payload['link'];provider=config['provider']
    options='format=text&verify=yes&redirect=no&retry=0&overflow=upstream&cto=5&rto=15'
    if provider=='slack':
        url='slack://'+secret['webhook'].split('/services/',1)[1]+'?'+options+'&image=no&footer=no&blocks=no'
        host='hooks.slack.com'
    elif provider=='telegram':
        url='tgram://'+quote(secret['token'],safe=':')+'/'+secret['recipient']+'?'+options+'&image=no&detect=no&preview=no'
        host='api.telegram.org'
    elif provider=='whatsapp':
        url='whatsapp://'+config['template']+':'+quote(secret['token'],safe='')+'@'+secret['sender_id']+'/'+secret['recipient']+'?'+options+'&lang='+config['template_language']+'&:body=1'
        host='graph.facebook.com'
    elif provider=='teams':
        # Apprise's card builder is reused; the exact current Power Platform URL
        # is preserved (the SDK's native URL parser still assumes legacy routes).
        from apprise.plugins.workflows import NotifyWorkflows
        host=urlsplit(secret['webhook']).hostname
        sender=transport_factory(host)
        card=NotifyWorkflows(host=host,workflow='status',signature='status',include_image=False,wrap=True)
        response=sender.post(secret['webhook'],json=card.gen_payload(body=text,title='DemandLab'),verify=True,allow_redirects=False)
        return 'accepted' if response.status_code in {200,202} else 'rejected' if 400<=response.status_code<500 else 'unknown'
    else:return 'rejected'
    sender=transport_factory(host)
    apprise=Apprise(asset=AppriseAsset(app_id='DemandLab',app_desc='DemandLab',async_mode=False))
    if not apprise.add(url):return 'rejected'
    # Scope requests adaptation to this single-use process; no mutation of the
    # shared application's HTTP stack, environment, SDK files or provider code.
    with patch('requests.request',sender.request),patch('requests.post',sender.post):
        accepted=apprise.notify(body=text,title='',body_format=NotifyFormat.TEXT)
    if bool(accepted):return 'accepted'
    return 'rejected' if sender.codes and 400<=sender.codes[-1]<500 else 'unknown'


if __name__=='__main__':
    import logging
    logging.disable(logging.CRITICAL)
    try:
        raw=sys.stdin.buffer.read(12000)
        if len(raw)>=12000:raise ValueError()
        state=deliver(json.loads(raw))
    except Exception:state='unknown'
    sys.stdout.write(json.dumps({'state':state}))
