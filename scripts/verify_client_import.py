"""Import a declared client scope and run it locally; never alters the workbook."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.main import DATASET_STORE, SavedRunConfig, run_saved


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workbook', type=Path)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--exclude', action='append', default=[])
    parser.add_argument('--horizon', type=int, default=3)
    args = parser.parse_args()
    source = DATASET_STORE.upload(args.workbook.name, args.workbook.read_bytes(), 'history')
    settings = {'date_col': 'date', 'target_col': 'demand', 'item_col': 'series_id',
                'sku_col': 'sku', 'customer_col': 'customer', 'category_col': 'category',
                'unit': args.unit, 'unit_filter': args.unit, 'excluded_items': args.exclude,
                'frequency': 'monthly', 'horizon': args.horizon, 'profile': 'fast',
                'method_selection': 'recommended', 'drivers': [], 'outlier_strategy': 'none',
                'missing_strategy': 'auto', 'future_driver_policy': 'require',
                'calendar_country': 'IR', 'weekend_days': [4], 'shutdown_dates': []}
    dataset = DATASET_STORE.save(f'Client diagnostic · {args.unit} · {len(args.exclude)} items excluded',
                                 {'history': source['id']}, settings, accept_warnings=True)
    result = await run_saved(SavedRunConfig(dataset_id=dataset['id']))
    print(json.dumps({'dataset_id': dataset['id'], 'run_id': result['run_id'],
                      'unit': result['unit'], 'summary': result['summary'], 'metrics': result['metrics'],
                      'excluded_items': args.exclude, 'warnings': result['warnings']}, indent=2))


if __name__ == '__main__':
    asyncio.run(main())
