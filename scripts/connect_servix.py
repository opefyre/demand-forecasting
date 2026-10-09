"""Load the user-provided private file without exposing it to terminal output."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.factors import FactorStore
from app.live_sources import LiveSources, SourceError


def connect():
    folder = ROOT / 'secrets'
    path = folder / 'servix-api.txt'
    if folder.is_symlink() or path.is_symlink() or not path.is_file() or path.stat().st_size > 8192:
        raise SourceError('Use a regular, small servix-api.txt file inside the project secrets folder.')
    key = path.read_text(encoding='utf-8-sig').strip()
    if key.startswith(('SERVIX_API_KEY=', 'SERVIX_API_KEY =')):
        key = key.split('=', 1)[1].strip().strip('"\'')
    store = LiveSources(ROOT / 'data' / 'live-sources.sqlite3', FactorStore(ROOT / 'data' / 'factors'))
    result = store.setup_key(key)
    key = None
    store.configure('servix', True)
    print('Servix key verified and stored in macOS Keychain. Automatic source refresh enabled.', flush=True)
    return result


if __name__ == '__main__':
    try:
        connect()
    except SourceError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print('Secure setup could not complete. No credential details were printed.', file=sys.stderr)
        sys.exit(1)
