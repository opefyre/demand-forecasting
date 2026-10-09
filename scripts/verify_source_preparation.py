"""Record a read-only check of retained sources; never refresh or change a run."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import main
from app.factor_preparation import prepare_sources


def main_check():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = prepare_sources(main._load_run(args.run_id), main.DATASET_STORE,
                             main.FACTOR_STORE, main.LIVE_SOURCES,
                             {'currency_exposure': True, 'global_supply': True,
                              'hormuz_route': True, 'materials': ['aluminum']})
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'run_id': args.run_id, 'sources': [
        {'name': row['name'], 'status': row['status'], 'can_prepare': row['can_prepare']}
        for row in report['recommendations']], 'output': str(args.output)}))


if __name__ == '__main__':
    main_check()
