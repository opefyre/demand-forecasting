from copy import deepcopy
from pathlib import Path
import tempfile
import unittest
import pandas as pd
from app.operations import calculate_operations
from app.production_mapping import production_schema
from app.units import UnitStore
from app.routing import route_workload


def sample():
    run = {'unit': 'KBlank', 'source_classification': 'synthetic_sample',
           'metadata': {'A-1': {'sku': 'A'}, 'A-2': {'sku': 'A'}, 'B-1': {'sku': 'B'}},
           'series': {key: {'forecast': [{'timestamp': '2026-09-01', 'mean': qty}]}
                      for key, qty in [('A-1', 100), ('A-2', 50), ('B-1', 40)]}}
    sheets = {
        'bom': pd.DataFrame([{'sku': 'A', 'product_unit': 'KBlank', 'material_id': 'M', 'material_unit': 'kg', 'quantity_per_unit': .5}, {'sku': 'B', 'product_unit': 'KBlank', 'material_id': 'M', 'material_unit': 'g', 'quantity_per_unit': 100}]),
        'materials': pd.DataFrame([{'material_id': 'M', 'material_name': 'Board', 'unit': 'kg', 'inventory_on_hand': 100, 'quality_hold_qty': 10, 'safety_stock': 20, 'lead_time_days': 5, 'moq': 10}]),
        'capacity': pd.DataFrame([{'production_line': 'Cutter', 'period': '2026-09-01', 'available_hours': 50, 'planned_downtime_hours': 10, 'oee_target': .8}, {'production_line': 'Press', 'period': '2026-09-01', 'available_hours': 20, 'planned_downtime_hours': 5, 'oee_target': .8}]),
        'routing': pd.DataFrame([{'sku': sku, 'sequence': step, 'stage': name, 'production_line': machine, 'product_unit': 'KBlank', 'hours_per_unit': rate, 'batch_size': 100, 'setup_hours_per_batch': setup, 'valid_from': '2026-01-01'} for sku,step,name,machine,rate,setup in [('A',1,'Cut','Cutter',.2,2),('A',2,'Print','Press',.1,1),('B',1,'Cut','Cutter',.5,1)]])}
    sheets['materials'].attrs['stock_as_of'] = '2026-08-31'
    return run, sheets


class RoutingTests(unittest.TestCase):
    def test_plan_adjustments_recalculate_steps_and_export_machine_units(self):
        from io import BytesIO
        import openpyxl
        from app.plan_outputs import resolve_plan, plan_workbook
        run, sheets = sample()
        run['run_id'] = 'routing-test'
        plan = {'id': 'sample-plan', 'updated_at': '2026-08-31', 'run_id': 'routing-test', 'name': 'Synthetic plan', 'status': 'approved', 'owner': 'Tester',
                'overrides': [{'item_id': 'A-1', 'period': '2026-09-01', 'value': 200, 'reason': 'Synthetic test'}]}
        resolved, quantities = resolve_plan(run, plan)
        result = calculate_operations(resolved, sheets)
        # A now totals 250 units: 3 batches, 56 cutter hours plus B's 21.
        self.assertEqual(result['capacity'][0]['required_quantity'], 77)
        self.assertEqual(result['capacity'][1]['required_quantity'], 28)
        book = openpyxl.load_workbook(BytesIO(plan_workbook(plan, quantities, result)), data_only=True)
        rows = list(book['Capacity'].values)
        first = dict(zip(rows[0], rows[1]))
        self.assertEqual(first['required_quantity'], 77)
        self.assertEqual(first['capacity_unit'], 'hours')
        self.assertEqual(book['Production steps'].max_row, 4)
        self.assertEqual(run['series']['A-1']['forecast'][0]['mean'], 100)

    def test_generic_units_batching_shared_machines_and_materials(self):
        run, sheets = sample()
        result = calculate_operations(run, sheets)
        material = result['materials'][0]
        self.assertEqual((material['gross_requirement'], material['opening'], material['projected_balance'], material['recommended_order']), (79, 90, 11, 10))
        cutter, press = result['capacity']
        self.assertEqual((cutter['required_quantity'], cutter['available_quantity'], cutter['gap_quantity']), (55, 50, -5))
        self.assertEqual(press['required_quantity'], 17)
        self.assertEqual(cutter['capacity_unit'], 'hours')
        self.assertNotIn('forecast_tonnes', cutter)
        self.assertEqual(result['workload_details'][0]['batches'], 2)
        self.assertEqual(len(result['workload_details']), 3)
        self.assertEqual(run['series']['A-1']['forecast'][0]['mean'], 100)

    def test_missing_steps_months_machine_capacity_and_units_block(self):
        for change, message in [('route', 'missing products'), ('date', 'incomplete production'), ('machine', 'missing forecast'), ('unit', 'confirm')]:
            run, sheets = sample()
            if change == 'route': sheets['routing'] = sheets['routing'][sheets['routing'].sku == 'A']
            if change == 'date': sheets['routing'].loc[0, 'valid_from'] = '2026-10-01'
            if change == 'machine': sheets['capacity'] = sheets['capacity'][sheets['capacity'].production_line == 'Cutter']
            if change == 'unit': sheets['routing'].loc[0, 'product_unit'] = 'BOB'
            with self.assertRaisesRegex(ValueError, message): calculate_operations(run, sheets)

    def test_overlapping_routes_not_silently_added(self):
        run, sheets = sample()
        sheets['routing'] = pd.concat([sheets['routing'], sheets['routing'].iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, 'overlapping'):
            calculate_operations(run, sheets)

    def test_monthly_effective_dates_and_whole_step_numbers(self):
        for field, value in [('valid_from','2026-01-15'), ('valid_from',0), ('valid_from','01/02/2026'), ('valid_to','2026-09-15'), ('sequence',1.5), ('hours_per_unit',-1), ('hours_per_unit',float('inf')), ('batch_size',0)]:
            run, sheets = sample()
            sheets['routing'][field] = sheets['routing'].get(field, pd.Series('', index=sheets['routing'].index)).astype(object)
            sheets['routing'].loc[0,field] = value
            with self.assertRaises(ValueError, msg=field): calculate_operations(run, sheets)

    def test_dated_machine_change_and_no_double_downtime(self):
        run, sheets = sample()
        routes = sheets['routing'].copy()
        routes.loc[0,'valid_to'] = '2026-08-31'
        next_rate = routes.iloc[[0]].copy()
        next_rate['valid_from'], next_rate['valid_to'], next_rate['hours_per_unit'] = '2026-09-01', '', .3
        sheets['routing'] = pd.concat([routes,next_rate],ignore_index=True)
        result = calculate_operations(run,sheets)
        self.assertEqual(result['capacity'][0]['required_quantity'],70)
        self.assertEqual(result['capacity'][0]['available_quantity'],50)

    def test_zero_demand_has_no_setups_and_setup_pair_required(self):
        run, sheets = sample()
        for series in run['series'].values(): series['forecast'][0]['mean'] = 0
        self.assertEqual(calculate_operations(run,sheets)['capacity'][0]['required_quantity'],0)
        sheets['routing'] = sheets['routing'].drop(columns=['batch_size'])
        with self.assertRaisesRegex(ValueError,'together'): calculate_operations(run,sheets)

    def test_reviewed_product_conversion_and_sample_isolation(self):
        run,sheets = sample()
        run['unit'] = 'KBLANK'
        with tempfile.TemporaryDirectory() as folder:
            store = UnitStore(Path(folder)/'units.sqlite3')
            version = store.save({'name':'Sample exact labels','classification':'synthetic_sample','reviewer':'Tester','reviewed':True,'rules':[{'sku':sku,'from_unit':'KBLANK','to_unit':'KBlank','factor':1,'valid_from':'2026-01-01','source':'Synthetic only'} for sku in ['A','B']]})
            sheets['bom'].attrs['unit_version'] = version
            self.assertEqual(calculate_operations(run,sheets)['materials'][0]['gross_requirement'],79)
            run['source_classification'] = 'user_provided'
            with self.assertRaisesRegex(ValueError,'both be real'): calculate_operations(run,sheets)
            store.engine.dispose()

    def test_schema_and_unavailable_material_conversion(self):
        self.assertIn('routing',production_schema('routed'))
        self.assertIn('quantity_per_tonne',production_schema()['bom']['required'])
        run,sheets = sample()
        sheets['bom'].loc[0,'material_unit'] = 'L'
        with self.assertRaisesRegex(ValueError,'cannot be converted'): calculate_operations(run,sheets)

    def test_old_tonne_recipe_cannot_be_mixed_with_generic_routes(self):
        run, sheets = sample()
        sheets['bom'] = sheets['bom'].rename(columns={'quantity_per_unit': 'quantity_per_tonne'})
        with self.assertRaisesRegex(ValueError, 'explicit product and material units'):
            calculate_operations(run, sheets)

    def test_invalid_forecasts_are_never_zero(self):
        for value in (None,-1,float('nan')):
            run,sheets = sample()
            run['series']['A-1']['forecast'][0]['mean'] = value
            with self.assertRaisesRegex(ValueError,'forecast quantities'): calculate_operations(run,sheets)
