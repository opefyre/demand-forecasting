"""Create a consistent, non-overwriting snapshot of the local plan database."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.planning import PlanStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path, help='New .sqlite3 backup file; parent folder must exist.')
    args = parser.parse_args()
    if args.destination.suffix != '.sqlite3':
        parser.error('Use a .sqlite3 file so the backup is recognizable.')
    store = PlanStore(ROOT / 'data' / 'plans.json')
    print(store.storage.backup(args.destination.resolve()))


if __name__ == '__main__':
    main()
