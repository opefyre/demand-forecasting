"""Offline state backup/restore. Application code and secrets are managed separately."""
import argparse
from pathlib import Path
import json
import sys
import sqlite3
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.recovery import backup, restore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    save = commands.add_parser('backup', help='Stop app and workers first; choose a new ZIP file.')
    save.add_argument('destination', type=Path)
    recover = commands.add_parser('restore', help='Verify into a NEW directory; does not replace live data.')
    recover.add_argument('source', type=Path)
    recover.add_argument('destination', type=Path)
    args = parser.parse_args()
    try:
        result = backup(ROOT, args.destination) if args.command == 'backup' else restore(args.source, args.destination)
    except (ValueError, RuntimeError, OSError, KeyError, TypeError, sqlite3.DatabaseError, zipfile.BadZipFile) as exc:
        parser.exit(1, f'{exc}\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__': main()
