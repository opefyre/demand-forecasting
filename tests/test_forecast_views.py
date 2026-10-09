from pathlib import Path
import tempfile
import unittest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from app.forecast_views import ViewStore, SavedView, install_view_routes


class ForecastViewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.store=ViewStore(Path(self.tmp.name)/'sales.sqlite3')
        self.payload={'name':'Export customers','run_id':'run1','snapshot_id':'orders1','settings':{'unit':'tonnes','customer':'A','display':'pivot','measure':'remaining'}}

    def test_persists_exact_scope_and_isolates_users_and_runs(self):
        saved=self.store.save('alice',SavedView(**self.payload))
        self.assertEqual(self.store.list('alice','run1')[0],saved)
        self.assertEqual(self.store.list('bob','run1'),[])
        self.assertEqual(self.store.list('alice','other'),[])
        self.assertEqual(ViewStore(self.store.path).list('alice','run1')[0]['snapshot_id'],'orders1')

    def test_route_uses_identity_and_checks_snapshot_ownership(self):
        app=FastAPI()
        @app.middleware('http')
        async def identity(request:Request,call_next):
            request.state.principal={'issuer':'company','subject':request.headers.get('actor','alice')}
            return await call_next(request)
        install_view_routes(app,self.store,lambda _: {},lambda _: {'inputs':{'run_id':'run1'}})
        client=TestClient(app)
        self.assertEqual(client.post('/api/sales/views',json=self.payload).status_code,200)
        self.assertEqual(len(client.get('/api/sales/views?run_id=run1').json()['views']),1)
        self.assertEqual(client.get('/api/sales/views?run_id=run1',headers={'actor':'bob'}).json()['views'],[])
        self.assertEqual(client.post('/api/sales/views',json={**self.payload,'run_id':'other'}).status_code,400)
        self.assertEqual(client.post('/api/sales/views',json={**self.payload,'name':' '}).status_code,422)

    def test_invalid_display_not_accepted(self):
        with self.assertRaises(ValueError):
            SavedView(**{**self.payload,'settings':{'unit':'kg','display':'invented'}})
