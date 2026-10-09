from copy import deepcopy
from unittest.mock import patch
import uuid

from tests.test_factor_links import FactorLinkTests
from app.forecast_inputs import input_context, factor_options, preview_inputs, save_inputs


class ForecastInputTests(FactorLinkTests):
    def test_stale_live_sources_are_disabled_and_cannot_be_previewed(self):
        options={'snapshots':[{'id':self.snapshot['id'],'live_what_if':True,'public_vintage':False}]}
        live=type('Live',(),{'listing':lambda _: {'sources':[{'id':'servix','refresh_overdue':True,'series':[{'id':self.snapshot['id']}]}]}})()
        with patch('app.forecast_inputs.choices',return_value=deepcopy(options)):
            result=factor_options(self.store,self.factors,self.dataset['id'],live)
            self.assertFalse(result['snapshots'][0]['can_use'])
            with self.assertRaisesRegex(ValueError,'Refresh the source'):
                preview_inputs(self.store,self.factors,self.dataset['id'],self.payload,live)

    def test_context_has_identity_and_dates_not_predictions(self):
        with patch('app.forecast_engine._fit_full_models_and_predict', side_effect=AssertionError('No model fitting')):
            context = input_context(self.store, self.dataset['id'])
            self.assertTrue(context['input_context_only'])
            self.assertEqual(context['metadata']['A'], {'sku':'SKU','customer':'A'})
            self.assertEqual(context['series']['A']['forecast'], [{'timestamp':'2026-01-01'}, {'timestamp':'2026-02-01'}])
            self.assertNotIn('metrics', context)
            self.assertEqual(len(factor_options(self.store, self.factors, self.dataset['id'])['snapshots']),1)

    def test_factor_inputs_are_reviewed_immutable_and_not_a_scenario(self):
        original = deepcopy(self.dataset)
        payload = {**self.payload,'method':'model:Ridge + drivers'}
        review = preview_inputs(self.store,self.factors,self.dataset['id'],payload)
        body = {**payload,'reviewed':True,'review_token':review['review_token'],'request_id':str(uuid.uuid4())}
        saved = save_inputs(self.store,self.factors,self.dataset['id'],body)
        self.assertNotIn('scenario_provenance',saved)
        self.assertEqual(saved['import_provenance']['type'],'forecast_factors')
        self.assertNotIn('base_run_id',saved['import_provenance'])
        self.assertEqual(saved['parent_dataset_id'],original['id'])
        self.assertEqual(self.store.get(original['id']),original)
        self.assertEqual(save_inputs(self.store,self.factors,self.dataset['id'],body),saved)
        self.assertEqual(saved['settings']['factor_definitions'][review['column']]['name'],'Index')
        with self.assertRaises(ValueError):
            save_inputs(self.store,self.factors,self.dataset['id'],{**body,'future_value':900})

    def test_missing_history_and_unsupported_scope_cannot_be_approved(self):
        for change in ({'lag_months':1},{'series_ids':['A']},{'preparation':{}}):
            with self.subTest(change=change):
                payload={**self.payload,**change}
                try:
                    report=preview_inputs(self.store,self.factors,self.dataset['id'],payload)
                except ValueError:
                    continue
                self.assertGreater(report['missing'],0)
                with self.assertRaises(ValueError):
                    save_inputs(self.store,self.factors,self.dataset['id'],{**payload,'review_token':report['review_token'],'reviewed':True,'request_id':str(uuid.uuid4())})

    def test_api_uses_dataset_identifier_and_existing_error_contract(self):
        from fastapi.testclient import TestClient
        from app import main
        client=TestClient(main.app)
        with patch.object(main,'DATASET_STORE',self.store),patch.object(main,'FACTOR_STORE',self.factors):
            path='/api/datasets/'+self.dataset['id']+'/forecast-factors'
            self.assertEqual(client.get(path).status_code,200)
            response=client.post(path+'/preview',json=self.payload)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(client.post(path,json=self.payload).status_code,400)
            self.assertEqual(client.get('/api/datasets/invalid/forecast-factors').status_code,400)
