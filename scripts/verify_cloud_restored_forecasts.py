"""Compare existing restored forecasts to the verified checkpoint, never run jobs."""
import argparse
from io import BytesIO
import json
from pathlib import Path
import sys
import zipfile
from hashlib import sha256
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.cloud_state import restore, digest
from app.company_workspace import CompanyWorkspace
from app.sales_demand import demand_outlook, export_demand, run_today


def check(source, reviewed, company, expected):
    if digest(source) != expected:
        raise ValueError('Checkpoint hash mismatch.')
    # Unmodified reference exists only in a temporary private folder. No worker,
    # scheduler, server, provider or notification sender is started.
    with TemporaryDirectory(prefix='reference-', dir=reviewed.parent) as folder:
        root = Path(folder).resolve()
        restore(source, root, company)
        original = CompanyWorkspace(root / 'data/companies' / company, company)
        recovered = CompanyWorkspace((reviewed / 'data/companies' / company).resolve(), company)
        before = original.list_runs()
        after = recovered.list_runs()
        assert {r['run_id'] for r in before} == {r['run_id'] for r in after}
        receipts = []
        for run in before:
            identifier = run['run_id']
            copy = recovered.load_run(identifier)
            assert run == copy, 'Forecast numbers or calculation evidence changed.'
            inputs = original.sales.list(identifier)
            assert inputs == recovered.sales.list(identifier), 'Customer/order inputs changed.'
            for saved in inputs:
                prior = demand_outlook(saved['inputs'], run, today=run_today(run))
                result = demand_outlook(saved['inputs'], copy, today=run_today(run))
                assert prior == result
                exports = []
                for mode in ['remaining_forecast', 'combined_demand']:
                    for kind in ['csv', 'json', 'xlsx']:
                        first, mime = export_demand(prior, mode, kind)
                        second, copy_mime = export_demand(result, mode, kind)
                        assert mime == copy_mime
                        if kind == 'xlsx':
                            # Workbook creation timestamps are not business data.
                            with zipfile.ZipFile(BytesIO(first)) as a, zipfile.ZipFile(BytesIO(second)) as b:
                                assert a.namelist() == b.namelist()
                                for name in a.namelist():
                                    if name != 'docProps/core.xml':
                                        assert a.read(name) == b.read(name)
                        else:
                            assert first == second
                        exports.append(mode + ':' + kind)
                receipts.append({'run_id': identifier, 'rows': len(result['rows']),
                    'total_demand': sum(row['total'] for row in result['rows']),
                    'confirmed_open': sum(row['booked'] for row in result['rows']),
                    'expected': sum(row['remaining'] for row in result['rows']),
                    'exports_verified': exports,
                    'result_sha256': sha256(json.dumps(copy, sort_keys=True).encode()).hexdigest()})
        if not receipts:
            raise ValueError('No restored forecasts were verified.')
        return {'verified': True, 'forecasts': receipts, 'engine_calls': 0, 'provider_calls': 0}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('reviewed', type=Path)
    parser.add_argument('--company', required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    print(json.dumps(check(args.source, args.reviewed, args.company, args.sha256), indent=2))
