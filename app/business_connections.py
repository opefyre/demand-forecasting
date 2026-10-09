"""Company-scoped read-only pulls; immutable captures require input review."""
from contextlib import contextmanager
import hashlib
import io
import ipaddress
import json
from pathlib import PurePosixPath
import re
import socket
import sqlite3
import time
from urllib.parse import urlsplit
import uuid
import zipfile

import httpx
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from .live_sources import KeyVault

LIMIT = 20 * 1024 * 1024
ROLES = {'history':'inputs', 'future':'factors', 'sales_orders':'orders', 'sales_customers':'customers'}


class ConnectionError(ValueError):
    pass


class ConnectionConflict(ConnectionError):
    pass


class ConnectionInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=120)
    provider: str = Field(pattern=r'^(http|sftp)$')
    role: str = Field(pattern=r'^(history|future)$')
    filename: str = Field(min_length=1, max_length=160)
    url: str = Field(default='', max_length=1000)
    host: str = Field(default='', max_length=253)
    port: int = Field(default=22, ge=1, le=65535, strict=True)
    username: str = Field(default='', max_length=128)
    path: str = Field(default='', max_length=1000)
    host_key: str = Field(default='', max_length=2000)
    credential: SecretStr | None = Field(default=None, max_length=4096)
    template_dataset_id: str | None = Field(default=None, pattern=r'^[a-f0-9]{32}$')
    confirmed_read_access: bool = False

    @model_validator(mode='after')
    def valid(self):
        if not self.confirmed_read_access:
            raise ValueError('Confirm permission to read this source.')
        if self.role=='future' and not self.template_dataset_id:
            raise ValueError('Choose reviewed sales data before connecting future factors.')
        if self.filename != PurePosixPath(self.filename).name or '\\' in self.filename or any(ord(c)<32 for c in self.filename):
            raise ValueError('Use a filename without a folder path.')
        if PurePosixPath(self.filename).suffix.lower() not in {'.csv','.tsv','.json','.xlsx'}:
            raise ValueError('Choose CSV, TSV, JSON or XLSX.')
        if self.provider == 'http':
            parsed = urlsplit(self.url)
            if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                    or parsed.query or parsed.fragment or parsed.port not in {None,443}
                    or any(ord(c)<33 for c in self.url)):
                raise ValueError('Use an HTTPS endpoint without credentials, query parameters or redirects.')
            if self.host or self.username or self.path or self.host_key:
                raise ValueError('SFTP settings do not apply to HTTPS.')
        else:
            if self.url or not self.username or not re.fullmatch(r'[A-Za-z0-9.-]+', self.host):
                raise ValueError('Enter the SFTP host and username.')
            if not self.path.startswith('/') or '..' in PurePosixPath(self.path).parts or any(c in self.path for c in '*?[]\n\r\x00'):
                raise ValueError('Use the exact absolute SFTP file path, without wildcards.')
            try:
                from paramiko.hostkeys import HostKeyEntry
                entry = HostKeyEntry.from_line(self.host + ' ' + self.host_key)
                if entry is None or entry.key is None: raise ValueError()
            except Exception:
                raise ValueError('Provide the public SSH host key from your administrator.') from None
        return self

    def public_config(self):
        return self.model_dump(exclude={'credential','confirmed_read_access'})


class ConnectorVault(KeyVault):
    def __init__(self, root):
        super().__init__(root)
        self.service = self.service.replace('live-sources', 'business-connections')

    def get(self, identifier):
        try: return self.backend().get_password(self.service, identifier)
        except Exception:
            raise ConnectionError('Secure credential storage is unavailable. Unlock Keychain and try again.') from None

    def set(self, identifier, value):
        try: self.backend().set_password(self.service, identifier, value)
        except Exception:
            raise ConnectionError('Secure credential storage is unavailable. Unlock Keychain and try again.') from None


class TargetPolicy:
    """Only the operator may approve an exact private host:port, not an API caller."""
    def __init__(self, private_hosts=()):
        self.private_hosts = frozenset(private_hosts)

    def resolve(self, host, port):
        try: addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        except OSError:
            raise ConnectionError('The source address could not be resolved.') from None
        if not addresses: raise ConnectionError('The source address could not be resolved.')
        for _,_,_,_,target in addresses:
            address = ipaddress.ip_address(target[0])
            if getattr(address, 'ipv4_mapped', None): address = address.ipv4_mapped
            if (address.is_loopback or address.is_link_local or address.is_unspecified or address.is_multicast
                    or address.is_reserved or (not address.is_global and f'{host.lower()}:{port}' not in self.private_hosts)):
                raise ConnectionError('This network address is not allowed. Ask your administrator to approve the source.')
        return addresses[0]


def check_payload(payload, filename):
    if not payload or len(payload)>LIMIT:
        raise ConnectionError('The source is empty or exceeds the 20 MB input limit.')
    if filename.lower().endswith('.xlsx'):
        try:
            with zipfile.ZipFile(io.BytesIO(payload)) as archive:
                rows = archive.infolist()
                if len(rows)>2000 or sum(r.file_size for r in rows)>LIMIT*3:
                    raise ConnectionError('The expanded spreadsheet exceeds the input limit.')
        except zipfile.BadZipFile:
            raise ConnectionError('The source is not a valid XLSX file.') from None
    if filename.lower().endswith('.json'):
        try: data = json.loads(payload)
        except (ValueError, UnicodeError):
            raise ConnectionError('The source is not valid JSON.') from None
        if isinstance(data, dict) and any(data.get(k) for k in ('next','next_page','next_cursor','has_more')):
            raise ConnectionError('This endpoint is paginated. Connect a complete export instead.')
    return payload


class InputFetcher:
    def __init__(self, policy=None, transport=None, socket_factory=None):
        self.policy, self.transport = policy or TargetPolicy(), transport
        self.socket_factory = socket_factory or socket.socket

    def fetch(self, config, credential):
        try:
            data = self.http(config, credential) if config['provider']=='http' else self.sftp(config, credential)
            return check_payload(data, config['filename'])
        except ConnectionError: raise
        except Exception:
            # Remote exceptions may contain credentials or full URLs. Never forward them.
            raise ConnectionError('The source could not be read. Check access and connection settings.') from None

    def http(self, config, credential):
        parsed = urlsplit(config['url'])
        address = self.policy.resolve(parsed.hostname,443)[4][0]
        ip = f'[{address}]' if ':' in address else address
        endpoint = f'https://{ip}{parsed.path or "/"}'
        headers = {'Host':parsed.hostname, 'Accept':'application/json,text/csv,text/tab-separated-values,application/octet-stream'}
        if credential:
            if '\n' in credential or '\r' in credential: raise ConnectionError('The source credential is invalid.')
            headers['Authorization'] = 'Bearer ' + credential
        with httpx.Client(timeout=httpx.Timeout(20,connect=5),follow_redirects=False,trust_env=False,transport=self.transport) as client:
            # Pin DNS; retain the original hostname for TLS verification and SNI.
            with client.stream('GET',endpoint,headers=headers,extensions={'sni_hostname':parsed.hostname}) as response:
                if response.status_code!=200:
                    raise ConnectionError('The source did not return a complete export. Check the endpoint and read access.')
                if re.search(r'rel\s*=\s*["\']?next',response.headers.get('link',''),re.I):
                    raise ConnectionError('This endpoint is paginated. Connect a complete export instead.')
                chunks, size, deadline = [],0,time.monotonic()+30
                for chunk in response.iter_bytes(chunk_size=65536):
                    size += len(chunk)
                    if size>LIMIT or time.monotonic()>deadline:
                        raise ConnectionError('The source exceeds the input size or time limit.')
                    chunks.append(chunk)
                return b''.join(chunks)

    def sftp(self, config, credential):
        import paramiko
        from paramiko.hostkeys import HostKeyEntry
        if not credential: raise ConnectionError('Add the read-only SFTP password before fetching.')
        family,kind,proto,_,address = self.policy.resolve(config['host'],config['port'])
        with self.socket_factory(family,kind,proto) as sock:
            sock.settimeout(20); sock.connect(address)
            with paramiko.SSHClient() as client:
                entry = HostKeyEntry.from_line(config['host']+' '+config['host_key'])
                name = config['host'] if config['port']==22 else f'[{config["host"]}]:{config["port"]}'
                client.get_host_keys().add(name,entry.key.get_name(),entry.key)
                client.set_missing_host_key_policy(paramiko.RejectPolicy())
                client.connect(config['host'],port=config['port'],username=config['username'],password=credential,
                    sock=sock,timeout=10,banner_timeout=10,auth_timeout=10,channel_timeout=10,allow_agent=False,look_for_keys=False)
                with client.open_sftp() as sftp:
                    sftp.get_channel().settimeout(20)
                    before = sftp.stat(config['path'])
                    if before.st_size is None or before.st_size>LIMIT:
                        raise ConnectionError('The source exceeds the 20 MB input limit.')
                    chunks,size,deadline = [],0,time.monotonic()+30
                    with sftp.open(config['path'],'rb') as stream:
                        while True:
                            chunk = stream.read(65536)
                            if not chunk: break
                            size += len(chunk)
                            if size>LIMIT or time.monotonic()>deadline:
                                raise ConnectionError('The source exceeds the input size or time limit.')
                            chunks.append(chunk)
                    payload = b''.join(chunks)
                    after = sftp.stat(config['path'])
                    if (before.st_size,before.st_mtime)!=(after.st_size,after.st_mtime) or len(payload)!=before.st_size:
                        raise ConnectionError('The remote file changed while reading. Fetch it again after the export finishes.')
                    return payload


class BusinessConnections:
    def __init__(self, path, datasets, *, vault=None, fetcher=None):
        self.path, self.datasets = path,datasets
        self.vault, self.fetcher = vault or ConnectorVault(path.parent),fetcher or InputFetcher()
        with self.db() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS connections(id TEXT PRIMARY KEY,config TEXT NOT NULL,
              version INTEGER NOT NULL,archived INTEGER NOT NULL DEFAULT 0,credential INTEGER NOT NULL DEFAULT 0);
            CREATE TABLE IF NOT EXISTS pulls(id TEXT PRIMARY KEY,connection_id TEXT NOT NULL,
              request_id TEXT NOT NULL,version INTEGER NOT NULL,state TEXT NOT NULL,started REAL NOT NULL,
              message TEXT NOT NULL,candidate_id TEXT,UNIQUE(connection_id,request_id));
            CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,connection_id TEXT NOT NULL,
              version INTEGER NOT NULL,digest TEXT NOT NULL,source_id TEXT NOT NULL,data TEXT NOT NULL,
              accepted_dataset_id TEXT,UNIQUE(connection_id,version,digest));
            ''')

    @contextmanager
    def db(self):
        db = sqlite3.connect(self.path,timeout=30); db.row_factory = sqlite3.Row
        try:
            with db: yield db
        finally: db.close()

    def get(self, identifier):
        with self.db() as db:
            row = db.execute('SELECT * FROM connections WHERE id=?',(identifier,)).fetchone()
            if row is None: raise ConnectionError('Connection not found.')
            pulls = [dict(r) for r in db.execute('''SELECT p.*,c.accepted_dataset_id FROM pulls p
                LEFT JOIN candidates c ON c.id=p.candidate_id WHERE p.connection_id=?
                ORDER BY p.started DESC LIMIT 20''',(identifier,))]
        return {'id':row['id'],**json.loads(row['config']),'version':row['version'],
                'archived':bool(row['archived']),'credential_configured':bool(row['credential']),'pulls':pulls}

    def list(self, include_archived=False):
        with self.db() as db:
            ids = [r['id'] for r in db.execute('SELECT id FROM connections WHERE archived=0 OR ? ORDER BY rowid DESC',(include_archived,))]
        return [self.get(key) for key in ids]

    def save(self, body, identifier=None, version=None):
        config = body.public_config()
        if body.template_dataset_id:
            template = self.datasets.get(body.template_dataset_id)
            if 'history' not in template['sources']:
                raise ConnectionError('Choose reviewed data with a matching input type.')
        identifier = identifier or uuid.uuid4().hex
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            old = db.execute('SELECT * FROM connections WHERE id=?',(identifier,)).fetchone()
            if version is not None and (old is None or old['version']!=version):
                raise ConnectionConflict('This connection changed. Reload it before editing.')
            configured = bool(old and old['credential'])
            next_version = (old['version'] if old else 0)+1
            if body.credential is not None:
                secret = body.credential.get_secret_value()
                if not secret: raise ConnectionError('Enter a non-empty credential.')
                self.vault.set(f'{identifier}:{next_version}',secret); configured = True
            elif configured:
                previous = json.loads(old['config'])
                # Never send an existing secret to a newly chosen destination without reconfirmation.
                target = ('provider','url','host','port','username','host_key')
                if any(previous[k]!=config[k] for k in target):
                    raise ConnectionError('Supply a new credential when changing the destination.')
                self.vault.set(f'{identifier}:{next_version}',self.vault.get(f'{identifier}:{old["version"]}'))
            db.execute('INSERT INTO connections VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET config=excluded.config,version=excluded.version,credential=excluded.credential',
                       (identifier,json.dumps(config),next_version,0,configured))
        return self.get(identifier)

    def archive(self, identifier, version, archived):
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('UPDATE connections SET archived=?,version=version+1 WHERE id=? AND version=?',(archived,identifier,version)).rowcount!=1:
                raise ConnectionConflict('This connection changed. Reload it before editing.')
            row = db.execute('SELECT credential FROM connections WHERE id=?',(identifier,)).fetchone()
            if row['credential']:
                self.vault.set(f'{identifier}:{version+1}',self.vault.get(f'{identifier}:{version}'))
        return self.get(identifier)

    def candidate(self, identifier):
        with self.db() as db: row = db.execute('SELECT * FROM candidates WHERE id=?',(identifier,)).fetchone()
        if row is None: raise ConnectionError('Import not found.')
        result = {**dict(row),**json.loads(row['data'])}; result.pop('data',None)
        self.datasets.source(row['source_id'])
        return result

    def pull(self, identifier, request_id):
        started = time.time()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM connections WHERE id=?',(identifier,)).fetchone()
            if row is None or row['archived']: raise ConnectionError('Connection not found or archived.')
            prior = db.execute('SELECT * FROM pulls WHERE connection_id=? AND request_id=?',(identifier,request_id)).fetchone()
            if prior: return dict(prior)
            if db.execute("SELECT 1 FROM pulls WHERE connection_id=? AND state='fetching' AND started>?",(identifier,started-180)).fetchone():
                raise ConnectionConflict('A fetch is already running for this connection.')
            db.execute("UPDATE pulls SET state='failed',message='Fetch interrupted. Try again.' WHERE connection_id=? AND state='fetching'",(identifier,))
            key = uuid.uuid4().hex
            db.execute('INSERT INTO pulls VALUES(?,?,?,?,?,?,?,?)',(key,identifier,request_id,row['version'],'fetching',started,'Fetching inputs…',None))
        try:
            config = json.loads(row['config'])
            secret = self.vault.get(f'{identifier}:{row["version"]}') if row['credential'] else None
            payload = check_payload(self.fetcher.fetch(config,secret),config['filename'])
            digest = hashlib.sha256(payload).hexdigest()
            with self.db() as db:
                db.execute('BEGIN IMMEDIATE')
                current = db.execute('SELECT version,archived FROM connections WHERE id=?',(identifier,)).fetchone()
                if current['version']!=row['version'] or current['archived']:
                    raise ConnectionConflict('Connection changed during fetch. Fetch the current version again.')
                candidate = db.execute('SELECT id FROM candidates WHERE connection_id=? AND version=? AND digest=?',(identifier,row['version'],digest)).fetchone()
                if candidate:
                    candidate_id,message = candidate['id'],'No changes'
                else:
                    candidate_id = uuid.uuid5(uuid.NAMESPACE_URL,f'connection:{identifier}:{row["version"]}:{digest}').hex
                    source = self.datasets.upload(config['filename'],payload,config['role'],identifier=candidate_id)
                    data = {'name':config['name'],'sources':{config['role']:source['id']},'settings':{},
                            'parent_dataset_id':None,'role':config['role'],'classification':'user_provided'}
                    if config['template_dataset_id']:
                        parent = self.datasets.get(config['template_dataset_id'])
                        settings = dict(parent['settings'])
                        if config['role']=='history':
                            settings.pop('history_cell_corrections',None)
                            settings.pop('history_corrections_sha256',None)
                        data.update(sources={**parent['sources'],config['role']:source['id']},settings=settings,parent_dataset_id=parent['id'])
                    db.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?,?)',(candidate_id,identifier,row['version'],digest,source['id'],json.dumps(data),None))
                    message = 'Ready for review'
                db.execute("UPDATE pulls SET state='ready',message=?,candidate_id=? WHERE id=?",(message,candidate_id,key))
        except Exception as exc:
            message = str(exc) if isinstance(exc,ConnectionError) else 'The inputs could not be read. Check the file format and connection settings.'
            with self.db() as db: db.execute("UPDATE pulls SET state='failed',message=? WHERE id=?",(message,key))
        with self.db() as db: return dict(db.execute('SELECT * FROM pulls WHERE id=?',(key,)).fetchone())

    def accept(self, identifier, body):
        candidate = self.candidate(identifier)
        if candidate['role'] not in {'history','future'}:
            raise ConnectionError('Review customer or order rows in their Data tab before using them.')
        if body.sources!=candidate['sources'] or body.parent_dataset_id!=candidate['parent_dataset_id'] or body.classification!='user_provided':
            raise ConnectionError('Review the exact captured inputs. Changed sources cannot use this import receipt.')
        if candidate['accepted_dataset_id']:
            saved = self.datasets.get(candidate['accepted_dataset_id'])
            if saved['name']!=body.name or saved['settings']!=body.settings:
                raise ConnectionConflict('This import was already saved. Create a new revision to change it.')
            return saved
        saved = self.datasets.save(body.name,body.sources,body.settings,'user_provided',body.accept_warnings,
            parent_dataset_id=body.parent_dataset_id,request_id='connection:'+identifier,
            import_provenance={'connection_id':candidate['connection_id'],'candidate_id':identifier,
                               'source_sha256':candidate['digest'],'connection_version':candidate['version']})
        with self.db() as db: db.execute('UPDATE candidates SET accepted_dataset_id=? WHERE id=?',(saved['id'],identifier))
        return saved
