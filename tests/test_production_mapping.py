from copy import deepcopy
from pathlib import Path
import tempfile
import hashlib
import unittest
from unittest.mock import patch
import pandas as pd
from fastapi.testclient import TestClient
import app.main as main
from app.datasets import DatasetStore
from app.operations import operations_preview, read_operations_workbook, calculate_operations
from app.production_mapping import mapped_operations

ROOT = Path(__file__).resolve().parents[1]


class ProductionMappingTests(unittest.TestCase):
    def setUp(self):
        self.content = (ROOT / 'sample_data/iran_operations_master.xlsx').read_bytes()
        self.preview = operations_preview('operations.xlsx', self.content)
        self.config = {**deepcopy(self.preview['suggested_mapping']), 'stock_as_of': '2026-08-31', 'reviewed': True}
        self.run = {'metadata': {'A': {'sku': 'PKG-KRAFT-120', 'production_line': 'Paper line A'}},
                    'series': {'A': {'forecast': [{'timestamp': '2026-09-01', 'mean': 250.0}]}}}

    def test_suggested_mapping_requires_confirmation_and_preserves_lineage(self):
        with self.assertRaisesRegex(ValueError, 'confirm'):
            read_operations_workbook('operations.xlsx', self.content, self.preview['suggested_mapping'])
        sheets = read_operations_workbook('operations.xlsx', self.content, self.config)
        old = read_operations_workbook('operations.xlsx', self.content)
        result = calculate_operations(self.run, sheets)
        self.assertEqual(result['materials'], calculate_operations(self.run, old)['materials'])
        self.assertTrue(result['input_lineage']['bom']['source_cells'][0]['sku'].endswith('!A2'))
        self.assertEqual(sheets['materials'].attrs['stock_as_of'], '2026-08-31')

    def test_required_cells_columns_and_dates_are_not_guessed(self):
        for update in ({'stock_as_of': ''}, {'reviewed': False}):
            with self.assertRaises(ValueError):
                mapped_operations('operations.xlsx', self.content, {**self.config, **update})
        config = deepcopy(self.config)
        config['tables']['bom']['columns']['sku'] = 'ZZ'
        with self.assertRaisesRegex(ValueError, 'required'):
            mapped_operations('operations.xlsx', self.content, config)
        config = deepcopy(self.config)
        config['tables']['bom']['columns']['sku'] = config['tables']['bom']['columns']['material_id']
        with self.assertRaisesRegex(ValueError, 'different'):
            mapped_operations('operations.xlsx', self.content, config)

    def test_arbitrary_headings_row_and_text_identifiers(self):
        table = {'columns': [{'id': 'C', 'label': 'Code'}, {'id': 'D', 'label': 'Component'}, {'id': 'F', 'label': 'Usage'}],
                 'rows': [{'source_row': 8, 'values': {'C': '001', 'D': '032', 'F': 2}}], 'formulas': {}}
        config = deepcopy(self.config)
        config['tables']['bom'] = {'sheet': 'Factory recipes', 'header_row': 7, 'columns': {'sku': 'C', 'material_id': 'D', 'quantity_per_tonne': 'F'}}
        from app.production_mapping import raw_table
        def read(name, content, sheet, header):
            return table if sheet == 'Factory recipes' else raw_table(name, content, sheet, header)
        with patch('app.production_mapping.raw_table', side_effect=read):
            sheets = mapped_operations('operations.xlsx', self.content, config)
        self.assertEqual(sheets['bom'].sku.iloc[0], '001')
        self.assertEqual(sheets['bom'].material_id.iloc[0], '032')
        self.assertEqual(sheets['bom'].attrs['source_cells'][0]['quantity_per_tonne'], 'Factory recipes!F8')

    def test_stock_date_and_overdue_deliveries_block(self):
        sheets = read_operations_workbook('operations.xlsx', self.content, self.config)
        sheets['materials'].attrs['stock_as_of'] = '2026-08-30'
        with self.assertRaisesRegex(ValueError, 'closing stock'):
            calculate_operations(self.run, sheets)
        sheets['materials'].attrs['stock_as_of'] = '2026-08-31'
        sheets['open_pos'].loc[0, 'due_date'] = pd.Timestamp('2026-08-31')
        with self.assertRaisesRegex(ValueError, 'already included'):
            calculate_operations(self.run, sheets)

    def test_unknown_status_optional_numbers_and_holds_rejected(self):
        for kind, field, value, message in [('open_pos', 'status', 'maybe', 'status'), ('bom', 'scrap_pct', 'bad', 'invalid'), ('materials', 'quality_hold_qty', 1e9, 'exceed'), ('capacity', 'oee_target', 80, 'between')]:
            sheets = read_operations_workbook('operations.xlsx', self.content, self.config)
            sheets[kind][field] = sheets[kind].get(field, pd.Series(0, index=sheets[kind].index)).astype(object)
            sheets[kind].loc[0, field] = value
            with self.assertRaisesRegex(ValueError, message):
                calculate_operations(self.run, sheets)

    def test_deliveries_outside_horizon_do_not_change_projection(self):
        sheets = read_operations_workbook('operations.xlsx', self.content, self.config)
        baseline = calculate_operations(self.run, sheets)
        extra = sheets['open_pos'].iloc[0].copy()
        extra['due_date'] = pd.Timestamp('2030-01-01')
        extra['quantity'] = 1e8
        sheets['open_pos'] = pd.concat([sheets['open_pos'], pd.DataFrame([extra])], ignore_index=True)
        self.assertEqual(baseline['materials'], calculate_operations(self.run, sheets)['materials'])

    def test_api_preview_has_positional_columns_and_role_guard(self):
        with tempfile.TemporaryDirectory() as folder:
            store = DatasetStore(Path(folder))
            source = store.upload('operations.xlsx', self.content, 'operations')
            with patch.object(main, 'DATASET_STORE', store), TestClient(main.app) as client:
                self.assertEqual(client.get('/api/production/schema').status_code, 200)
                response = client.post(f'/api/production/sources/{source["id"]}/preview', json={'sheet': self.config['tables']['bom']['sheet']})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['columns'][0]['id'], 'A')
                self.assertEqual(client.post(f'/api/production/sources/{source["id"]}/preview', json={'header_row': 0}).status_code, 400)

    def test_approved_supply_uses_exact_saved_mapping(self):
        run = {**self.run, 'run_id': 'r1', 'unit': 'tonnes', 'run_settings': {'frequency': 'monthly'},
               'input_manifest': {'settings': {'operations_mapping': self.config}, 'sources': [{'id': 'source', 'role': 'operations', 'sha256': hashlib.sha256(self.content).hexdigest()}]}}
        plan = {'id': 'p1', 'run_id': 'r1', 'name': 'Sample', 'status': 'approved', 'updated_at': '2026-08-01', 'overrides': []}
        with patch.object(main, '_load_run', return_value=run), patch.object(main.PLAN_STORE, 'get', return_value=plan), patch.object(main.DATASET_STORE, 'source', return_value=({'name': 'sample.xlsx'}, self.content)):
            _, _, supply = main._plan_output('p1', supply=True)
            self.assertEqual(supply['input_lineage']['materials']['stock_as_of'], '2026-08-31')
            run['input_manifest']['settings']['operations_mapping'] = {**self.config, 'stock_as_of': '2026-08-30'}
            with self.assertRaisesRegex(ValueError, 'closing stock'):
                main._plan_output('p1', supply=True)
