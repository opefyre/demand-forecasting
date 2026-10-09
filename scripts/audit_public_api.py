"""Read-only route inventory: parse source, never import the live application."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
METHODS = {'get', 'post', 'put', 'patch', 'delete', 'api_route'}


def routes(source, filename):
    tree = ast.parse(source)
    prefixes = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
            if isinstance(node.value.func, ast.Name) and node.value.func.id == 'APIRouter':
                prefix = next((k.value.value for k in node.value.keywords
                    if k.arg == 'prefix' and isinstance(k.value, ast.Constant)), '')
                for target in node.targets:
                    if isinstance(target, ast.Name): prefixes[target.id] = prefix
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)): continue
        for call in node.decorator_list:
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name) and call.func.attr in METHODS
                    and call.args and isinstance(call.args[0], ast.Constant)
                    and isinstance(call.args[0].value, str)): continue
            prefix = '/api/v1' if filename == 'app/platform_api.py' else prefixes.get(call.func.value.id, '')
            path = prefix + call.args[0].value
            if not path.startswith('/api/'): continue
            methods = [call.func.attr.upper()]
            if call.func.attr == 'api_route':
                methods = next((ast.literal_eval(k.value) for k in call.keywords if k.arg == 'methods'), ['GET'])
            found.extend((method.upper(), path, filename, call.lineno) for method in methods)
    return sorted(set(found), key=lambda row: (row[1], row[0], row[2]))


def delivery(path):
    if path.startswith('/api/v1/'): return 'Implemented; company-scoped'
    if path.startswith('/api/auth/'): return 'Account bridge; existing OIDC routes also retained'
    if path == '/api/login/{path:path}': return 'Better Auth proxy; identity-service allowlist'
    if path == '/api/health': return 'Health check; not a business API'
    if path.startswith(('/api/inventory', '/api/production', '/api/receipts')) or '/supply' in path:
        return 'Out of sales/demand scope; do not publish'
    if path.startswith('/api/sample/'): return 'Local demo helper; do not publish'
    return 'Pending company-scoped v1 migration; blocked in new auth mode'


def inventory():
    return sorted({row for file in (ROOT / 'app').glob('*.py')
        for row in routes(file.read_text(), file.relative_to(ROOT).as_posix())}, key=lambda row: (row[1], row[0], row[2]))


def markdown():
    records = inventory()
    public = [row for row in records if row[1].startswith('/api/v1/')]
    lines = ['# Public API coverage', '',
        'Generated from source decorators by `scripts/audit_public_api.py`; no application stores are opened.', '',
        f'{len(public)} implemented v1 operations. The rest of the useful business API is not delivered yet.', '',
        'New company authentication deliberately blocks unscoped legacy business routes. Existing local mode remains unchanged.', '',
        'The Better Auth identity service supplies library-managed login, Google callback, verification, recovery and factor endpoints behind `/api/login/*`. These are not business CRUD.', '',
        'Future v1 resources: sales history/sources/datasets, orders/snapshots, factors/live feeds/assumptions, grouped forecasts/jobs/results/exports, releases, actual-vs-forecast checks, personal chats/views, company settings/units, connections/ingestion runs and schedules. Immutable source evidence uses archive/revision rather than destructive overwrite.', '',
        '| Method | Route | Delivery | Source |', '|---|---|---|---|']
    for method, path, file, line in records:
        lines.append(f'| {method} | `{path}` | {delivery(path)} | `{file}:{line}` |')
    return '\n'.join(lines) + '\n'


if __name__ == '__main__':
    print(markdown(), end='')
