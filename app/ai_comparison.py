"""Read/propose adapter around the existing, deterministic order comparison."""
from .demand_comparison import compare_orders
from .sales_demand import month_basis


def summarize(report, customer='', sku=''):
    rows = report['rows']
    customers = sorted({r['customer'] for r in rows})
    skus = sorted({r['sku'] for r in rows if not customer or r['customer'] == customer})
    if customer and customer not in customers:
        raise ValueError('Customer not found in this comparison. Use an exact customer name.')
    if sku and sku not in skus:
        raise ValueError('SKU not found for this customer. Use an exact SKU.')
    rows = [r for r in rows if (not customer or r['customer'] == customer) and (not sku or r['sku'] == sku)]
    fields = ('booked', 'fulfilled', 'before_remaining', 'after_remaining', 'before_total', 'after_total', 'difference')
    grouped = {}
    for row in rows:
        group = grouped.setdefault((row['period'], row['unit']), {'period':row['period'], 'unit':row['unit'], **{f:0 for f in fields}})
        for field in fields:
            group[field] = None if group[field] is None or row[field] is None else group[field] + row[field]
    totals = {}
    for row in grouped.values():
        total = totals.setdefault(row['unit'], {'unit':row['unit'], **{f:0 for f in fields}})
        for field in fields:
            total[field] = None if total[field] is None or row[field] is None else total[field] + row[field]
    return {'months':[grouped[k] for k in sorted(grouped)], 'totals':list(totals.values()), 'matched_rows':len(rows),
            'customer':customer or None, 'sku':sku or None,
            'customer_count':len({r['customer'] for r in rows}), 'sku_count':len({r['sku'] for r in rows}),
            'warnings':report['warnings'], 'can_save':report['can_save'], 'classification':report['classification'],
            'as_of':report['as_of'], 'valid_until':report['valid_until'],
            'scope':'Filtered preview only' if customer or sku else 'All customers and SKUs',
            'note':'Total includes delivered quantities; exports exclude deliveries. Unknown totals are not zero.'}


class AssistantComparisons:
    def __init__(self, store, load_run, list_runs, run, outlook):
        self.store, self.load_run, self.list_runs = store, load_run, list_runs
        self.run, self.outlook = run, outlook

    def choices(self):
        if not self.outlook or not self.outlook.get('snapshot_id'):
            raise ValueError('Select a reviewed customer-order version for the baseline first.')
        if self.run.get('base_run_id'):
            raise ValueError('Open the original baseline in Forecast, then ask to compare its scenarios.')
        rows = []
        for item in self.list_runs()['runs']:
            if item.get('base_run_id') != self.run['run_id']:
                continue
            target = self.load_run(item['run_id'])
            if target.get('scenario', {}).get('type') == 'factor_link':
                rows.append({'run_id':target['run_id'], 'name':item['name']})
        return rows

    def preview(self, target_id):
        if target_id not in {r['run_id'] for r in self.choices()}:
            raise ValueError('Choose an exact linked-factor scenario from this baseline. Do not guess a scenario.')
        return compare_orders(self.store, self.load_run, target_id, self.outlook['snapshot_id'])[0]

    def proposal(self, target_id):
        report = self.preview(target_id)
        if not report['can_save']:
            raise ValueError('Orders are expired, incomplete or have unknown totals. Review them before preparing a save.')
        target = self.load_run(target_id)
        return {'kind':'order_scenario', 'target_run_id':target_id, 'base_run_id':self.run['run_id'],
                'month_basis':month_basis(target),
                'snapshot_id':report['source_snapshot_id'], 'review_token':report['review_token'],
                'name':target.get('scenario_name') or target.get('dataset_name') or target_id,
                'preview':summarize(report)}
