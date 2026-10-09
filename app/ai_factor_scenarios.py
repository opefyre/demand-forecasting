"""Assistant proposals reuse the existing factor alignment and save gates."""
from copy import deepcopy
from pydantic import BaseModel, ConfigDict, Field

from .factor_links import choices, preview_link
from .live_factor_alignment import FACTOR_METHODS
from .factor_preparation import tested_methods


class MonthlyFactorValue(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    period: str = Field(pattern=r'^\d{4}-\d{2}-\d{2}$')
    value: float = Field(allow_inf_nan=False)


class FactorAssumption(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    snapshot_id: str = Field(min_length=32, max_length=32)
    lag_months: int = Field(ge=1, le=12)
    future_value: float | None = Field(default=None, allow_inf_nan=False)
    future_values: list[MonthlyFactorValue] | None = Field(default=None, max_length=24)


class AssistantFactorScenarios:
    def __init__(self, run, datasets, factors):
        self.run, self.datasets, self.factors = run, datasets, factors

    def choices(self):
        if self.run.get('scenario_name') or self.run.get('base_run_id'):
            raise ValueError('Choose the original forecast before preparing another factor scenario.')
        result = choices(self.run, self.datasets, self.factors)
        # Live sources only: assistant must not revive old manually imported factors.
        result['snapshots'] = [s for s in result['snapshots'] if s['public_vintage'] or s['live_what_if']]
        result['methods'] = [f"model:{name}" for name in tested_methods(self.run) if name in FACTOR_METHODS]
        return result

    def preview(self, links, method, customer='', sku=''):
        options = self.choices()
        known = {s['id']: s for s in options['snapshots']}
        if not 1 <= len(links) <= 8:
            raise ValueError('Choose one to eight connected factors.')
        if method not in options['methods']:
            raise ValueError('Choose an exact factor-aware method returned by inspect_factor_sources.')
        payload = {'links': [], 'method': method}
        for supplied in links:
            link = FactorAssumption.model_validate(supplied).model_dump(exclude_none=True)
            if 'future_values' in link:
                rows = link['future_values']
                if len({r['period'] for r in rows}) != len(rows):
                    raise ValueError('Provide each future month only once.')
                link['future_values'] = {r['period']:r['value'] for r in rows}
            source = known.get(link['snapshot_id'])
            if not source:
                raise ValueError('Choose an exact connected source returned by inspect_factor_sources.')
            link['availability_policy'] = 'reviewed_what_if' if source['live_what_if'] else 'vintage_month_end'
            if source.get('calendar') == 'jalali':
                link['period_alignment'] = 'last_completed_jalali_month'
            payload['links'].append(link)
        if customer or sku:
            selected = [s['id'] for s in options['series']
                        if (not customer or s['customer'] == customer) and (not sku or s['sku'] == sku)]
            if not selected:
                raise ValueError('Choose an exact customer/product from inspect_factor_sources. No fuzzy matching.')
            payload['series_ids'] = selected
        report = preview_link(self.run, self.datasets, self.factors, payload)
        summary = {k: report[k] for k in ('factor_count', 'factor', 'scope', 'series_count', 'missing',
                                         'method', 'retrospective', 'warnings', 'policy')}
        summary['future_rows'] = [r for r in report['rows'] if r['kind'] == 'future']
        summary['missing_rows'] = [r for r in report['rows'] if r['value'] is None][:24]
        summary['factors'] = [{k: r.get(k) for k in ('factor', 'provider', 'unit', 'geography', 'lag_months',
                               'period_alignment', 'policy', 'source_url', 'license_url', 'source_quality')}
                              for r in report['factors']]
        summary['approval_note'] = 'Preview only. Source timing, locations and explicit future assumptions need human review. Orders are unchanged.'
        return payload, report, summary

    def proposal(self, links, method, customer='', sku=''):
        payload, report, summary = self.preview(links, method, customer, sku)
        if report['missing']:
            raise ValueError('Required observations are missing. Inspect the preview; do not invent past values or assume future values.')
        return {'kind': 'factor_scenario', 'base_run_id': self.run['run_id'],
                'payload': deepcopy(payload), 'review_token': report['review_token'], 'preview': summary}
