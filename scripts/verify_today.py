"""Read-only reconciliation of the Today queue with the saved sample plan."""
import httpx


with httpx.Client(base_url='http://127.0.0.1:8010', timeout=30) as client:
    def read(path, **params):
        response = client.get(path, params=params)
        response.raise_for_status()
        return response.json()
    today = read('/api/today', run_id='431fed798551', plan_id='e2379cd021')
    supply = read('/api/plans/e2379cd021/supply')
    run = read('/api/runs/431fed798551')
    assert today['context']['plan_id'] == supply['quantity_basis']['id']
    assert today['context']['source_classification'] == 'synthetic_sample'
    assert today['metrics']['historical_error_pct'] == run['metrics']['wape_pct']
    assert today['context']['last_actual_period'] == run['summary']['end']
    for kind, key, status, metric in [('materials','material_id','shortage','materials_at_risk'),
                                     ('capacity','production_line','bottleneck','constrained_lines')]:
        flagged = [row for row in supply[kind] if row['status'] == status]
        identifiers = {row[key] for row in flagged}
        assert today['metrics'][metric] == len(identifiers)
        decisions = [row for row in today['decisions'] if row['kind'] == kind]
        assert len(decisions) == len(identifiers)
        for decision in decisions:
            identifier = decision['id'].split(':',1)[1]
            matching = sorted([row for row in flagged if row[key] == identifier], key=lambda row:row['period'])
            assert decision['affected_periods'] == len(matching)
            assert decision['action']['period'] == matching[0]['period']
            assert decision['action']['tab'] == kind
            quantity = matching[0]['shortage'] if kind == 'materials' else -matching[0]['gap_quantity']
            assert f'{quantity:,.1f}' in decision['detail']
    print({'plan':'e2379cd021', 'queue':len(today['decisions']), **today['metrics'], 'supply_actions_reconciled':True})
