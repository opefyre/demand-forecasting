import json
import unittest
from agents.tool_context import ToolContext
from app.ai_workspace import build_agent, forecast_month_totals
from tests.test_sales_demand import fixture, demand_outlook


class CompleteMonthsTests(unittest.IsolatedAsyncioTestCase):
    async def test_truncated_detail_has_full_selected_order_month_totals(self):
        run, inputs = fixture()
        outlook = {**demand_outlook(inputs, run), 'snapshot_id':'selected-orders'}
        outlook['rows'] *= 50
        agent = build_agent('query', 'test', run, outlook, [])
        tool = next(t for t in agent.tools if t.name == 'inspect_forecast')
        result = await tool.on_invoke_tool(ToolContext(context=None, tool_name=tool.name,
            tool_call_id='test', tool_arguments='{}'), json.dumps({'customer':''}))
        self.assertEqual(len(result['rows']), 120)
        self.assertEqual(result['total_rows'], 150)
        self.assertTrue(result['truncated'])
        self.assertTrue(result['monthly_totals_complete'])
        self.assertEqual(result['months'][0]['total'], 23 * 50)
        self.assertEqual(result['snapshot_id'], 'selected-orders')
        self.assertIn('ALREADY deducted', result['quantity_meanings']['booked'])
        self.assertIn('those orders are already applied', agent.instructions)

    async def test_baseline_totals_are_not_taken_from_detail_limit(self):
        run, _ = fixture()
        for series in run['series'].values():
            series['forecast'] *= 50
        agent = build_agent('query', 'test', run, None, [])
        tool = next(t for t in agent.tools if t.name == 'inspect_forecast')
        result = await tool.on_invoke_tool(ToolContext(context=None, tool_name=tool.name,
            tool_call_id='test', tool_arguments='{}'), json.dumps({'customer':''}))
        self.assertEqual(result['months'][0]['quantity'], 23 * 50)
        self.assertTrue(result['truncated'])

    def test_unknowns_and_mixed_units_remain_separate(self):
        rows = [dict(period='2026-10-01', unit='tonnes', quantity=10),
                dict(period='2026-10-01', unit='tonnes', quantity=None),
                dict(period='2026-10-01', unit='kg', quantity=1000)]
        groups = forecast_month_totals(rows, ('quantity',))
        by_unit = {r['unit']:r for r in groups}
        self.assertIsNone(by_unit['tonnes']['quantity'])
        self.assertEqual(by_unit['kg']['quantity'], 1000)


if __name__ == '__main__':
    unittest.main()
