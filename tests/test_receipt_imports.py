from copy import deepcopy
from io import BytesIO
from datetime import datetime
import json
from unittest.mock import patch
import unittest
from fastapi.testclient import TestClient
import openpyxl

import app.main as main
from tests import test_inventory as fixture
from app.receipt_imports import import_receipts


CONTENT = b'Order,Product,Outstanding,UOM,Usable,Type,State\n0001/1,001,12,pieces,2026-09-15,PO,Open\n0002/1,001,4,pieces,2026-10-01,MO,Hold\n'
MAPPING = dict(reference='A', sku='B', quantity='C', unit='D', due_date='E', kind='F', status='G')


class ReceiptImportTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.InventoryTests(); self.fixture.setUp()
        self.store = self.fixture.store
        self.snapshot = self.store.save(self.fixture.config)
        self.source = self.fixture.sources.upload('receipts.csv', CONTENT, 'receipts')
        self.config = dict(source_id=self.source['id'], header_row=1, mapping=MAPPING,
                           kind_map={'PO':'purchase', 'MO':'production'}, status_map={'Open':'confirmed', 'Hold':'unconfirmed'})
        self.payload = dict(name='Receipt import', reason='Synthetic import check', reviewed=True, request_id='import-1', import_config=self.config)

    def tearDown(self): self.fixture.tearDown()

    def test_mapping_lineage_and_reparse_on_save(self):
        result = import_receipts(self.fixture.sources, self.config)
        self.assertEqual(result['rows'][0]['reference'], '0001/1')
        self.assertEqual(result['rows'][0]['sku'], '001')
        self.assertEqual(result['source_cells'][0]['cells']['quantity'], 'C2')
        saved = self.store.save_receipts(self.snapshot['id'], {**self.payload, 'rows':[{'quantity':999}]})
        self.assertEqual([row['quantity'] for row in saved['rows']], [12,4])
        self.assertEqual(saved['import_evidence']['source']['sha256'], self.source['sha256'])
        self.assertEqual(saved['rows'][1]['status'], 'unconfirmed')
        self.assertEqual(self.store.save_receipts(self.snapshot['id'], self.payload), saved)

    def test_unmapped_status_dates_and_roles_block(self):
        invalid = deepcopy(self.config); invalid['status_map'].pop('Hold')
        with self.assertRaisesRegex(ValueError, 'Row 3.*Hold'): import_receipts(self.fixture.sources, invalid)
        invalid = {**self.config, 'source_id': self.fixture.config['source_id']}
        with self.assertRaisesRegex(ValueError, 'receipt export'): import_receipts(self.fixture.sources, invalid)
        for due in ('09/10/2026', '1405-07-01', '20260915'):
            source = self.fixture.sources.upload('bad.csv', CONTENT.replace(b'2026-09-15', due.encode()), 'receipts')
            with self.assertRaises(ValueError): self.store.save_receipts(self.snapshot['id'], {**self.payload, 'import_config':{**self.config, 'source_id':source['id']}})
        with self.assertRaisesRegex(ValueError, 'wrong role'):
            self.fixture.sources.inspect({'history':self.source['id']}, {})

    def test_file_formats_and_real_excel_dates(self):
        table = [{'Order':'0001/1','Product':'001','Outstanding':12,'UOM':'pieces','Usable':'2026-09-15','Type':'PO','State':'Open'}]
        book = openpyxl.Workbook(); sheet = book.active; sheet.title = 'Deliveries'
        sheet.append(['Report']); sheet.append(list(table[0])); sheet.append(['0001/1','001',12,'pieces',datetime(2026,9,15),'PO','Open'])
        output = BytesIO(); book.save(output); book.close()
        for name, data, options in [('receipts.tsv', CONTENT.replace(b',',b'\t'),{}),
                                    ('receipts.json', json.dumps(table).encode(),{}),
                                    ('receipts.xlsx', output.getvalue(),{'sheet':'Deliveries','header_row':2})]:
            source = self.fixture.sources.upload(name, data, 'receipts')
            result = import_receipts(self.fixture.sources, {**self.config, 'source_id':source['id'], **options})
            self.assertEqual(result['rows'][0]['due_date'], '2026-09-15')
            self.assertEqual(result['rows'][0]['sku'], '001')
            if name.endswith('xlsx'): self.assertEqual(result['source_cells'][0]['cells']['quantity'], 'C3')

    def test_invalid_quantities_duplicates_and_changed_source(self):
        for data in (CONTENT.replace(b',12,',b',-1,'), CONTENT.replace(b'0002/1',b'0001/1'), CONTENT.replace(b',12,',b',,')):
            source = self.fixture.sources.upload('bad.csv', data, 'receipts')
            with self.assertRaises(ValueError): self.store.save_receipts(self.snapshot['id'], {**self.payload, 'import_config':{**self.config,'source_id':source['id']}})
        path = self.fixture.sources.root / (self.source['id'] + '.bin')
        path.write_bytes(CONTENT.replace(b',12,',b',99,'))
        with self.assertRaisesRegex(ValueError, 'changed since import'):
            self.store.save_receipts(self.snapshot['id'], self.payload)

    def test_fixed_fields_are_explicit_and_revision_does_not_change_parent(self):
        config = deepcopy(self.config); config['mapping'] = {k:v for k,v in MAPPING.items() if k not in ('unit','kind','status')}
        config.update(fixed_unit='pieces',fixed_kind='purchase',fixed_status='unconfirmed')
        parent = self.store.save_receipts(self.snapshot['id'], {**self.payload,'import_config':config})
        child = self.store.save_receipts(self.snapshot['id'], {**self.payload,'request_id':'revision','parent_id':parent['id']})
        self.assertEqual(self.store.receipt_version(self.snapshot['id'],parent['id']), parent)
        self.assertEqual(parent['rows'][0]['status'],'unconfirmed')
        self.assertEqual(child['rows'][0]['status'],'confirmed')

    def test_upload_preview_review_save_api(self):
        with patch.object(main,'DATASET_STORE',self.fixture.sources), patch.object(main,'INVENTORY_STORE',self.store), TestClient(main.app) as client:
            upload = client.post('/api/receipts/sources', files={'file':('receipt.csv',CONTENT,'text/csv')})
            self.assertEqual(upload.status_code,200,upload.text)
            config = {**self.config,'source_id':upload.json()['id']}
            preview = client.post(f'/api/receipts/sources/{config["source_id"]}/preview',json={**config,'value_columns':['G']})
            self.assertEqual(preview.json()['values']['G'], ['Hold','Open'])
            endpoint = f'/api/inventory/{self.snapshot["id"]}/receipts'
            checked = client.post(endpoint+'/validate',json={'import_config':config})
            self.assertEqual(checked.status_code,200,checked.text)
            self.assertEqual(checked.json()['row_count'],2)
            self.assertEqual(self.store.receipt_versions(self.snapshot['id']),[])
            saved = client.post(endpoint,json={**self.payload,'import_config':config})
            self.assertEqual(saved.status_code,200,saved.text)
            self.assertEqual(len(saved.json()['rows']),2)


if __name__ == '__main__': unittest.main()
