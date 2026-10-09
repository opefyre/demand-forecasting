"""Bounded physical conversions and explicitly selected, immutable factory rules."""
from datetime import date, datetime, timezone
import hashlib
import json
import math
import uuid

import pint
from sqlalchemy import Column, JSON, MetaData, String, Table, create_engine, select

REGISTRY = pint.UnitRegistry()
# Exact labels only: no guesses about ton, currency, packaging or local aliases.
STANDARD = {
    'kg': 'kilogram', 'kilogram': 'kilogram', 'kilograms': 'kilogram',
    'g': 'gram', 'gram': 'gram', 'grams': 'gram',
    'tonne': 'metric_ton', 'tonnes': 'metric_ton',
    'mm': 'millimeter', 'cm': 'centimeter', 'm': 'meter',
    'meter': 'meter', 'meters': 'meter',
    'ml': 'milliliter', 'mL': 'milliliter', 'L': 'liter',
    'liter': 'liter', 'liters': 'liter',
}


def standard_factor(source, target):
    if source not in STANDARD or target not in STANDARD:
        return None
    try:
        return float(REGISTRY.Quantity(1, STANDARD[source]).to(STANDARD[target]).magnitude)
    except pint.DimensionalityError:
        return None


def validate_rules(payload):
    if payload.get('classification') not in {'user_provided', 'synthetic_sample'}:
        raise ValueError('Identify these definitions as real or sample data.')
    if payload.get('reviewed') is not True or not str(payload.get('reviewer', '')).strip():
        raise ValueError('Record who checked the definitions and confirm the review.')
    if not str(payload.get('name', '')).strip():
        raise ValueError('Name this set of unit definitions.')
    rules = payload.get('rules')
    if not isinstance(rules, list) or not 1 <= len(rules) <= 1000:
        raise ValueError('Provide between 1 and 1,000 unit definitions.')
    clean = []
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError('Each definition must be a record.')
        row = {key: str(rule.get(key, '')).strip() for key in
               ('sku', 'from_unit', 'to_unit', 'valid_from', 'valid_to', 'source')}
        if any(not row[key] or len(row[key]) > 500 for key in ('sku', 'from_unit', 'to_unit', 'source')):
            raise ValueError('Provide product code, both units and a reference for every definition.')
        if row['from_unit'] == row['to_unit'] or standard_factor(row['from_unit'], row['to_unit']) is not None:
            raise ValueError('Identical units and standard physical conversions do not need a factory definition.')
        try:
            factor = float(rule['factor'])
            if isinstance(rule['factor'], bool) or not math.isfinite(factor) or factor <= 0:
                raise ValueError()
            start = date.fromisoformat(row['valid_from'])
            end = date.fromisoformat(row['valid_to']) if row['valid_to'] else date.max
            if end < start:
                raise ValueError()
        except (ValueError, TypeError, KeyError):
            raise ValueError('Use a positive conversion quantity and valid start/end dates.')
        row['factor'] = factor
        for prior in clean:
            if all(prior[key] == row[key] for key in ('sku', 'from_unit', 'to_unit')):
                if row['valid_from'] <= (prior['valid_to'] or '9999-12-31') and prior['valid_from'] <= (row['valid_to'] or '9999-12-31'):
                    raise ValueError('Definitions for the same product and unit direction cannot overlap in time.')
        clean.append(row)
    return clean


class UnitStore:
    def __init__(self, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f'sqlite:///{path}')
        metadata = MetaData()
        self.table = Table('unit_versions', metadata, Column('id', String, primary_key=True),
                           Column('created_at', String), Column('payload', JSON))
        metadata.create_all(self.engine)

    def save(self, payload):
        rules = validate_rules(payload)
        parent = payload.get('parent_id')
        if parent:
            old = self.get(parent)
            if old['classification'] != payload['classification']:
                raise ValueError('A revision must retain its real/sample classification.')
        canonical = json.dumps(rules, ensure_ascii=False, sort_keys=True, allow_nan=False)
        result = {'id': uuid.uuid4().hex, 'created_at': datetime.now(timezone.utc).isoformat(),
                  'name': str(payload['name']).strip(), 'reviewer': str(payload['reviewer']).strip(),
                  'classification': payload['classification'], 'parent_id': parent,
                  'rules': rules, 'sha256': hashlib.sha256(canonical.encode()).hexdigest(),
                  'engine': f'Pint {pint.__version__}'}
        with self.engine.begin() as conn:
            conn.execute(self.table.insert().values(id=result['id'], created_at=result['created_at'], payload=result))
        return result

    def get(self, key):
        with self.engine.connect() as conn:
            value = conn.execute(select(self.table.c.payload).where(self.table.c.id == key)).scalar()
        if value is None:
            raise ValueError('Unit definition version not found.')
        return value

    def list(self):
        with self.engine.connect() as conn:
            return list(conn.execute(select(self.table.c.payload).order_by(self.table.c.created_at.desc())).scalars())


def convert_stock(row, target, as_of, version=None):
    source = row['unit']
    factor = 1.0 if source == target else standard_factor(source, target)
    method = 'Unchanged' if source == target else 'Standard physical unit'
    rule = None
    if factor is None:
        matches = [r for r in (version or {}).get('rules', [])
                   if r['sku'] == row['sku'] and r['from_unit'] == source and r['to_unit'] == target
                   and r['valid_from'] <= as_of <= (r['valid_to'] or '9999-12-31')]
        if len(matches) != 1:
            raise ValueError(f"{row['sku']}: confirm {source} → {target} for {as_of}.")
        rule = matches[0]
        factor, method = rule['factor'], 'Reviewed product definition'
    quantity = row['quantity'] * factor
    if not math.isfinite(quantity):
        raise ValueError('The converted quantity is too large.')
    evidence = {'sku': row['sku'], 'source_row': row['source_row'],
                'source_quantity': row['quantity'], 'from_unit': source, 'to_unit': target,
                'quantity': quantity, 'factor': factor, 'method': method,
                'stock_status': row['quality'], 'engine': f'Pint {pint.__version__}',
                'reference': rule['source'] if rule else None,
                'version_id': version['id'] if rule else None}
    return {**row, 'quantity': quantity, 'unit': target}, evidence
