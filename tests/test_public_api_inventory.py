import unittest
from scripts.audit_public_api import routes, inventory, delivery


class PublicApiInventoryTests(unittest.TestCase):
    def test_nested_router_prefix_and_multiple_http_methods(self):
        source = """
def install(app):
    router=APIRouter(prefix='/api/orders')
    @router.get('/{identifier}')
    def get_order(): pass
    @router.api_route('', methods=['POST','PUT'])
    def save(): pass
    @app.get('/data')
    def ui(): pass
"""
        rows = routes(source, 'app/example.py')
        self.assertEqual([(r[0],r[1]) for r in rows], [('POST','/api/orders'),('PUT','/api/orders'),('GET','/api/orders/{identifier}')])

    def test_platform_mount_is_explicit_and_legacy_routes_are_not_called_complete(self):
        rows = inventory()
        self.assertIn(('POST','/api/v1/customers'), {(m,p) for m,p,_,_ in rows})
        self.assertIn(('GET','/api/ai/conversations'), {(m,p) for m,p,_,_ in rows})
        self.assertIn(('GET','/api/v1/ai/conversations'), {(m,p) for m,p,_,_ in rows})
        self.assertIn(('GET','/api/v1/workspace'), {(m,p) for m,p,_,_ in rows})
        self.assertIn(('POST','/api/v1/notifications/destinations/{destination_id}/test'), {(m,p) for m,p,_,_ in rows})
        self.assertIn('Pending', delivery('/api/run-saved'))
        self.assertIn('Out of', delivery('/api/inventory'))
        self.assertIn('Implemented', delivery('/api/v1/api-keys'))


if __name__ == '__main__': unittest.main()
