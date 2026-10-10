"""Company-only cloud checkpoints, using the existing verified backup format.

Cloud disk is scratch space. The caller publishes this checkpoint to private R2
and its durable revision ledger BEFORE reporting a successful write or forecast.
"""
from contextlib import closing
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
import zipfile

from .platform_identity import COMPANY_ID
from .recovery import backup, check_database, digest, verified_archive

MAX_COMPRESSED = 64 * 1024**2
MAX_EXPANDED = 256 * 1024**2
MAX_FILES = 10_000


def company_id(value):
    if not isinstance(value, str) or not COMPANY_ID.fullmatch(value):
        raise ValueError('Invalid company identity.')
    return value


def capture(root, company, destination):
    root, company = Path(root).resolve(), company_id(company)
    companies = root / 'data/companies'
    if companies.is_symlink() or not companies.is_dir():
        raise ValueError('A company workspace is required.')
    if [path.name for path in companies.iterdir()] != [company]:
        raise ValueError('A checkpoint must contain exactly one company.')
    # Never transfer globals, source code, local identity stores or local keys.
    if list((root / 'data').iterdir()) != [companies] or (root / 'runs').exists():
        raise ValueError('Global state is not allowed in a company checkpoint.')
    sources = list((companies / company).rglob('*'))
    if len(sources) > MAX_FILES or sum(p.stat().st_size for p in sources if p.is_file()) > MAX_EXPANDED:
        raise ValueError('Company checkpoint is too large.')
    result = backup(root, destination)
    if Path(destination).stat().st_size > MAX_COMPRESSED:
        Path(destination).unlink()  # This function created the exact new file.
        raise ValueError('Company checkpoint is too large.')
    return result


def restore(source, root, company):
    source, root, company = Path(source), Path(root), company_id(company)
    if root.exists() and any(root.iterdir()):
        raise ValueError('Recover into an empty scratch workspace.')
    if source.stat().st_size > MAX_COMPRESSED:
        raise ValueError('Company checkpoint is too large.')
    with zipfile.ZipFile(source) as archive:
        entries = archive.infolist()
        if len(entries) > MAX_FILES + 1 or sum(e.file_size for e in entries) > MAX_EXPANDED:
            raise ValueError('Company checkpoint is too large.')
        manifest = verified_archive(archive)
        prefix = 'data/companies/' + company + '/'
        if any(not row['path'].startswith(prefix) for row in manifest['files']):
            raise ValueError('Checkpoint belongs to another company.')
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for row in manifest['files']:
            target = root / row['path']
            target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            with archive.open(row['path']) as src, target.open('xb') as dst:
                shutil.copyfileobj(src, dst, 1024**2)
            target.chmod(0o600)
            if digest(target) != row['sha256']:
                raise ValueError('Company checkpoint integrity check failed.')
            if row['sqlite']:
                check_database(target)
    # No sanitization: this is an ordinary wake, not an operator disaster restore.
    # Runtime jobs are controlled by the external durable ledger, never replayed
    # by a scheduler or local queue process inside the engine.
    return manifest


def restore_for_review(source, destination, company, expected_sha256):
    """Operator recovery into a NEW directory; never replace a live ledger/head.

    Unlike normal cold wakes, pause all restored execution authority. D1 identity,
    Worker secrets and the external revision ledger require separate recovery.
    """
    from .recovery import restore as offline_restore
    source, company = Path(source), company_id(company)
    if source.stat().st_size > MAX_COMPRESSED:
        raise ValueError('Company checkpoint is too large.')
    if (not isinstance(expected_sha256, str) or len(expected_sha256) != 64 or
            any(c not in '0123456789abcdef' for c in expected_sha256) or
            digest(source) != expected_sha256):
        raise ValueError('Backup checksum does not match the expected archive.')
    with zipfile.ZipFile(source) as archive:
        if len(archive.infolist()) > MAX_FILES + 1 or sum(e.file_size for e in archive.infolist()) > MAX_EXPANDED:
            raise ValueError('Company checkpoint is too large.')
        manifest = verified_archive(archive)
        prefix = 'data/companies/' + company + '/'
        if not manifest['files'] or any(not row['path'].startswith(prefix) for row in manifest['files']):
            raise ValueError('Checkpoint belongs to another company.')
    return offline_restore(source, destination)


class EncryptedCompanyVault:
    """Maintained AES-GCM; credentials bound to company, purpose and identifier.

    Only ciphertext joins the company checkpoint. Key stays in Worker secrets
    and process environment; there is no fallback to a plaintext file.
    """
    def __init__(self, root, company, purpose, key):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        self.root, self.company, self.purpose = Path(root), company_id(company), purpose
        if purpose not in {'sources', 'connections', 'notifications'} or not isinstance(key, str):
            raise ValueError('Secure credential storage is unavailable.')
        try:
            if len(key) != 64: raise ValueError()
            self.cipher = AESGCM(bytes.fromhex(key))
        except ValueError:
            raise ValueError('Secure credential storage is unavailable.') from None

    def binding(self, identifier):
        if not isinstance(identifier, str) or not identifier or len(identifier) > 160:
            raise ValueError('Invalid credential identifier.')
        return json.dumps([self.company, self.purpose, identifier], separators=(',', ':')).encode()

    def path(self, identifier):
        folder = self.root / 'encrypted-credentials'
        if folder.is_symlink(): raise ValueError('Secure credential storage is unavailable.')
        folder.mkdir(mode=0o700, exist_ok=True)
        path = folder / (hashlib.sha256(self.binding(identifier)).hexdigest() + '.sealed')
        if path.is_symlink(): raise ValueError('Secure credential storage is unavailable.')
        return path

    def get(self, identifier='servix'):
        try:
            path = self.path(identifier)
            if not path.exists(): return None
            payload = path.read_bytes()
            return self.cipher.decrypt(payload[:12], payload[12:], self.binding(identifier)).decode()
        except Exception:
            raise ValueError('Secure credential storage is unavailable.') from None

    def set(self, identifier, value=None):
        import os
        # Source KeyVault has set(value); connector vault has set(id,value).
        if value is None: identifier, value = 'servix', identifier
        if not isinstance(value, str) or len(value.encode()) > 32768:
            raise ValueError('Invalid credential value.')
        nonce = os.urandom(12)
        path = self.path(identifier)
        pending = path.with_suffix('.pending')
        if pending.is_symlink(): raise ValueError('Secure credential storage is unavailable.')
        with pending.open('wb') as file:
            pending.chmod(0o600)
            file.write(nonce + self.cipher.encrypt(nonce, value.encode(), self.binding(identifier)))
            file.flush(); os.fsync(file.fileno())
        pending.replace(path)


def cloud_vault(root, company, purpose):
    import os
    if os.getenv('DEMANDLAB_CLOUD_RUNTIME') != 'true': return None
    return EncryptedCompanyVault(root, company, purpose, os.getenv('DEMANDLAB_COMPANY_VAULT_KEY'))
