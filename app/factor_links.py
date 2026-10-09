"""Explicit monthly, lagged factor links with frozen publication-time evidence."""
from copy import deepcopy
from datetime import datetime, timezone, timedelta
import math
import uuid

import pandas as pd

from .assumptions import scenario_inputs
from .data import actual_history, read_table, period_dates
from .factor_imports import digest
from .factors import observations_available_at
from .forecast_engine import _engine_versions
from .supply_pressure import archived_points, is_public_vintage, VINTAGE_POLICY
from .factor_normalization import completed_jalali_month
from .sales_conventions import normalize_history, month_range, shift_month
from .live_factor_alignment import is_live_monthly, monthly_points, WHAT_IF_POLICY, FACTOR_METHODS


POLICY = ('For each historical sales month, use the selected earlier observation only if '
          'published before that month began. Later revisions are excluded. Historical '
          'test predictions hold the last training value constant; future values use '
          'observations available at the forecast start or your explicit assumption. '
          'Uploader publication dates are not independently verified.')


def inputs(base, datasets):
    if base.get('engine') != _engine_versions():
        raise ValueError('Recalculate this baseline with the current engine before linking factors.')
    dataset, settings, future, _, warnings = scenario_inputs(base, datasets, allow_empty_drivers=True)
    if settings.get('frequency', 'monthly') != 'monthly':
        raise ValueError('Factor linking currently supports monthly sales and monthly factors only.')
    if set(dataset['sources']) - {'history', 'future'}:
        raise ValueError('Choose sales-only inputs for factor linking.')
    source, content = datasets.source(dataset['sources']['history'])
    history, _ = actual_history(read_table(source['name'], content, sheet_name=source.get('sheet')),
        unit_filter=settings.get('unit_filter'), excluded_items=settings.get('excluded_items'), item_col=settings.get('item_col'))
    if (settings.get('history_calendar','gregorian') != 'gregorian'
            or settings.get('returns_policy','reject') != 'reject' or settings.get('customer_aliases') or settings.get('history_cell_corrections') or settings.get('series_mode') == 'customer_product'):
        history, _ = normalize_history(history, settings)
    return dataset, settings, history.copy(), future, warnings


def choices(base, datasets, factors):
    dataset, _, history, future, _ = inputs(base, datasets)
    latest = {}
    for row in factors.list():
        latest.setdefault(row['factor_id'], row)
    return {'snapshots': [{**{k: row.get(k) for k in ('id','name','unit','geography','provider','captured_at','summary','calendar','normalization')},
                          'public_vintage': is_public_vintage(row), 'live_what_if': is_live_monthly(row)}
                         for row in latest.values() if is_public_vintage(row) or is_live_monthly(row) or
                         (row.get('kind') == 'imported_observations'
                         and row['frequency'] == 'monthly' and row['classification'] == dataset['classification'])],
            'forecast_periods': sorted(future.timestamp.unique().tolist()), 'policy': POLICY,
            'scope': 'All customer–SKU series in this forecast', 'history_rows': len(history),
            'series': [{'id':key, 'customer':base.get('metadata',{}).get(key,{}).get('customer',''),
                        'sku':base.get('metadata',{}).get(key,{}).get('sku',key)}
                       for key in base['series'] if key != '__all__']}


def _aligned(base, datasets, factors, payload, prepared=None):
    dataset, settings, history, future, warnings = prepared or inputs(base, datasets)
    history, future = history.copy(), future.copy()
    selected = payload.get('series_ids')
    if selected is not None:
        allowed = set(base['series']) - {'__all__'}
        if (not isinstance(selected,list) or not selected or
                any(not isinstance(key,str) for key in selected) or
                len(set(selected)) != len(selected) or set(selected) - allowed):
            raise ValueError('Choose one or more distinct customer/SKU combinations from this forecast.')
        selected = sorted(selected)
    snapshot = factors.get(payload.get('snapshot_id', ''))
    public = is_public_vintage(snapshot)
    live = is_live_monthly(snapshot)
    retrospective = live and payload.get('availability_policy') == 'reviewed_what_if'
    jalali=snapshot.get('calendar')=='jalali'
    if jalali and payload.get('period_alignment')!='last_completed_jalali_month':
        raise ValueError('Approve linking the last complete Persian month at each lag cutoff; it is not a Gregorian monthly observation.')
    if not jalali and payload.get('period_alignment') is not None:
        raise ValueError('Persian month alignment only applies to a Persian-calendar factor.')
    if not public and not live and (snapshot.get('kind') != 'imported_observations' or snapshot['frequency'] != 'monthly'
            or snapshot['classification'] != dataset['classification']):
        raise ValueError('Choose a monthly imported factor with the same real/sample classification.')
    lag = payload.get('lag_months')
    if isinstance(lag, bool) or not isinstance(lag, int) or not 1 <= lag <= 12:
        raise ValueError('Choose an observation lag from 1 to 12 months.')
    value = payload.get('future_value')
    if value is not None and (isinstance(value, bool) or not isinstance(value, (float,int)) or not math.isfinite(value)):
        raise ValueError('The future assumption must be a finite number, not a blank or text.')
    quality = None
    if live:
        if not retrospective:
            raise ValueError('Accept the live-data what-if limitation before previewing. Downloaded history cannot prove past forecast accuracy.')
        points, quality = monthly_points(factors, snapshot)
        warnings = [*warnings, WHAT_IF_POLICY]
        if snapshot.get('quote_basis'):
            warnings.append(snapshot['quote_basis'])
        if quality.get('limitation'):
            warnings.append(quality['limitation'])
        if dataset['classification'] == 'synthetic_sample':
            warnings.append('Real live factors with synthetic sales: demonstration only, not client accuracy evidence.')
    elif public:
        if payload.get('availability_policy') != 'vintage_month_end':
            raise ValueError('Accept the conservative vintage-month timing assumption before previewing this public factor.')
        points = archived_points(factors, snapshot)
        warnings = [*warnings, VINTAGE_POLICY]
        if dataset['classification'] == 'synthetic_sample':
            warnings.append('Real public factor combined with synthetic sales for demonstration only; not evidence of client forecast accuracy.')
    else:
        source, _ = datasets.source(snapshot['source']['id'])
        if source['sha256'] != snapshot['sha256']:
            raise ValueError('The retained factor file no longer matches this snapshot.')
        points = snapshot['points']
    policy = WHAT_IF_POLICY if live else VINTAGE_POLICY if public else POLICY
    if live and quality:
        policy += ' ' + quality['aggregation'] + '. ' + quality['coverage_policy'] + '.'
    if jalali:
        policy += (' At each lagged planning-month cutoff, use the last complete Persian month '
                   'only if that exact month was published before the sales cutoff. '
                   'Persian month values are not averaged or relabelled as Gregorian months.')
    column = f"factor_{snapshot['id'][:12]}_lag{lag}"
    if column in history or column in settings.get('drivers', []):
        raise ValueError('This factor version and lag are already linked.')
    basis=settings.get('month_basis','gregorian')
    dates = period_dates(history[settings['date_col']], 'monthly', basis)
    from .sales_groups import series_column
    item_col = series_column(settings)
    # Prevent existing general-purpose interpolation from filling factor cells in
    # inserted sales months. Such gaps require a separately reviewed history first.
    series = history[item_col].astype(str) if item_col else pd.Series('Total demand', index=history.index)
    for _, group in pd.DataFrame({'item':series, 'period':dates}).groupby('item'):
        expected = month_range(group.period.min(), group.period.max(), basis=basis)
        if len(expected) != group.period.nunique():
            raise ValueError('Sales history has missing months. Review those gaps before linking a factor; factor values will not be interpolated.')
    periods = sorted(pd.Timestamp(day) for day in dates.unique())
    future_periods = sorted(pd.Timestamp(day) for day in future.timestamp.unique())
    curve = payload.get('future_values')
    if curve is not None:
        if not isinstance(curve, dict) or value is not None:
            raise ValueError('Choose either one future value or values by forecast month, not both.')
        allowed = {day.strftime('%Y-%m-%d') for day in future_periods}
        if set(curve) - allowed:
            raise ValueError('Monthly assumptions must match the forecast months shown in the preview.')
        for amount in curve.values():
            if isinstance(amount, bool) or not isinstance(amount, (float, int)) or not math.isfinite(amount):
                raise ValueError('Each monthly assumption must be a finite number. Leave unknown months out.')
    if live:
        amounts = list(curve.values()) if curve is not None else [] if value is None else [value]
        if any(amount < 0 or (snapshot.get('live_source') == 'servix' and amount == 0) for amount in amounts):
            raise ValueError('Live factor assumptions cannot be negative; exchange rates must be greater than zero.')
        if basis == 'jalali':
            policy += (' Persian planning months use the last complete Gregorian source month at each lag cutoff. '
                       'Source averages are not split or relabelled as Persian-month averages.')
    cutoff = future_periods[0]
    points_by_period = {}
    for point in points:
        points_by_period.setdefault(point['period'], []).append(point)
    rows, matched = [], {}
    for kind, target_dates in (('history',periods),('future',future_periods)):
        for target in target_dates:
            cutoff_day=pd.Timestamp(shift_month(target,1-lag,basis).date()-timedelta(days=1))
            # Completed source periods, not averages of overlapping calendars.
            observation = cutoff_day.to_period('M').end_time.normalize().strftime('%Y-%m-%d') if basis=='gregorian' else (cutoff_day.to_period('M').start_time.date()-timedelta(days=1)).isoformat()
            lag_cutoff=observation
            if jalali:
                observation=completed_jalali_month(cutoff_day.date())
            boundary = target if kind == 'history' else cutoff
            release_cutoff = boundary.tz_localize('Asia/Tehran') if live else boundary
            eligible = observations_available_at({'points':points_by_period.get(observation, [])},
                (release_cutoff.to_pydatetime() - timedelta(microseconds=1)).isoformat())
            candidates = eligible[eligible.period.eq(observation)] if not eligible.empty else eligible
            point = candidates.iloc[-1].to_dict() if not candidates.empty else None
            if retrospective and kind == 'history':
                # Explicit retrospective sensitivity, never a point-in-time replay.
                candidates = points_by_period.get(observation, [])
                point = candidates[-1] if candidates and pd.Timestamp(observation) < boundary else None
            assumption = curve.get(target.strftime('%Y-%m-%d')) if curve is not None else value
            chosen = float(point['value']) if point else assumption if kind == 'future' else None
            row = {'kind':kind, 'sales_month':target.strftime('%Y-%m-%d'), 'observation_period':observation,
                   'available_before':boundary.strftime('%Y-%m-%d'), 'value':chosen,
                   'release_cutoff':release_cutoff.isoformat(),
                   'publication_date':point.get('publication_date') if point else None,
                   'availability_date':point.get('availability_date', point.get('publication_date') or point.get('available_at')) if point else None,
                   'vintage_month':point.get('vintage_month') if point else None,
                   'source_row':point.get('source_row') if point else None,
                   'period_start':point.get('period_start') if point else None,
                   'original_period':point.get('original_period') if point else None,
                   'original_value':point.get('original_value') if point else None,
                   'lag_cutoff':lag_cutoff,
                   'observed_days':point.get('observed_days') if point else None,
                   'coverage_pct':point.get('coverage_pct') if point else None,
                   'treatment':('downloaded_history' if retrospective and kind == 'history' else 'saved_observation' if live else 'archived_vintage' if public else 'published_observation') if point else 'planning_assumption' if chosen is not None else 'missing_or_unpublished'}
            rows.append(row); matched[(kind,row['sales_month'])] = chosen
    missing = sum(row['value'] is None for row in rows)
    report = {'base_run_id':base['run_id'], 'snapshot_id':snapshot['id'], 'factor':snapshot['name'],
              'unit':snapshot['unit'], 'geography':snapshot['geography'], 'provider':snapshot['provider'],
              'lag_months':lag, 'future_value':value, 'column':column, 'rows':rows, 'missing':missing,
              'scope':'All customer–SKU series in this forecast', 'series_count':int(series.nunique()),
              'history_rows':len(history), 'history_quantity':float(pd.to_numeric(history[settings['target_col']]).sum()),
              'policy':policy, 'availability_policy':'reviewed_what_if' if live else 'vintage_month_end' if public else 'uploader_release_dates',
              'retrospective':retrospective, 'source_quality':quality,
              'factor_classification':snapshot['classification'],
              'source_url':snapshot.get('source_url'), 'attribution':snapshot.get('attribution'), 'license_url':snapshot.get('license_url'),
              'warnings':warnings, 'method':base.get('method_selection') or settings.get('method_selection','recommended')}
    report['normalization']=snapshot.get('normalization')
    report['period_alignment']='last_completed_jalali_month' if jalali else 'last_completed_gregorian_month' if basis=='jalali' else 'exact_gregorian_month'
    if curve is not None:
        report['future_values'] = curve
    if selected is not None:
        report['series_ids'] = selected
        report['scope'] = f'{len(selected)} selected customer–SKU series; others keep their baseline'
        report['series_count'] = len(selected)
    report['review_token'] = digest({'report':report, 'snapshot':snapshot, 'dataset':dataset,
                                     'baseline_manifest':base['input_manifest']})
    if not missing:
        history[column] = dates.dt.strftime('%Y-%m-%d').map(lambda day:matched[('history',day)])
        future[column] = future.timestamp.map(lambda day:matched[('future',day)])
    return report, dataset, settings, history, future, snapshot


def preview_link(base, datasets, factors, payload, live=None, profiles=None):
    return _scenario_alignment(base,datasets,factors,payload,live,profiles)[0]


def accuracy_comparison(base, candidate):
    if candidate.get('metrics',{}).get('evidence_policy') == 'reviewed_what_if' or candidate.get('scenario',{}).get('alignment',{}).get('retrospective'):
        return {'available':False, 'reason':WHAT_IF_POLICY, 'rows':[]}
    from .scoped_accuracy import scoped_accuracy
    checked=candidate
    if candidate.get('scoped_accuracy',{}).get('available'):
        checked={**candidate,'metrics':{**candidate['metrics'],
            'range_check':{'rows':candidate['scoped_accuracy']['rows']}}}
    evidence=scoped_accuracy(base,checked,set(base['series'])-{'__all__'})
    if not evidence['available']:
        return {'available':False,'reason':evidence['reason'],'rows':[]}
    rows=evidence['rows']
    def score(selected):
        denominator=sum(abs(r['actual']) for r in selected)
        before=100*sum(abs(r['actual']-r['baseline_predicted']) for r in selected)/denominator if denominator else None
        after=100*sum(abs(r['actual']-r['predicted']) for r in selected)/denominator if denominator else None
        return {'baseline_error_pct':before,'scenario_error_pct':after,
                'change_points':after-before if before is not None else None}
    summary=score(rows)
    change=summary['change_points']
    selected=candidate.get('scenario',{}).get('alignment',{}).get('series_ids') or set(base['series'])-{'__all__'}
    mix_changed=any(base.get('series_ensemble_weights',{}).get(key)!=
                    candidate.get('series_ensemble_weights',{}).get(key) for key in selected)
    return {'available':True,'reason':'Same reserved historical observations; future accuracy is not guaranteed.',
            **summary,'outcome':'unavailable' if change is None else 'unchanged' if abs(change)<1e-8 else 'lower_error' if change<0 else 'higher_error',
            'method_changed':base.get('method_selection')!=candidate.get('method_selection') or mix_changed,
            'series':[{'item_id':key,**score([r for r in rows if r['item_id']==key])}
                      for key in sorted(set(r['item_id'] for r in rows))],
            'rows':rows}


def _scenario_alignment(base, datasets, factors, payload, live=None, profiles=None):
    """Compose dated drivers on identical rows; keep the single-link API compatible."""
    links=payload.get('links')
    if links is None:
        report,dataset,settings,history,future,snapshot=_aligned(base,datasets,factors,payload)
        aligned=[report];snapshots=[snapshot]
    else:
        if not isinstance(links,list) or not 1<=len(links)<=8:
            raise ValueError('Choose between one and eight factors.')
        if any(k in payload for k in ('snapshot_id','lag_months','future_value','future_values')):
            raise ValueError('Use a factor list or a single factor, not both.')
        prepared=inputs(base,datasets)
        aligned=[];snapshots=[];seen=set()
        dataset,settings,history,future,_=prepared
        history,future=history.copy(),future.copy()
        for link in links:
            if not isinstance(link,dict) or 'series_ids' in link or 'method' in link:
                raise ValueError('Set customers/products and the method once for the whole scenario.')
            child,dataset,settings,hist,fcst,snapshot=_aligned(base,datasets,factors,
                {**link,**({'series_ids':payload['series_ids']} if 'series_ids' in payload else {})},prepared)
            identity=snapshot.get('factor_id',snapshot['id'])
            if identity in seen:
                raise ValueError('Choose each factor only once; do not combine different versions of the same factor.')
            seen.add(identity);aligned.append(child);snapshots.append(snapshot)
            if not child['missing']:
                history[child['column']]=hist[child['column']]
                future[child['column']]=fcst[child['column']]
        report={k:v for k,v in aligned[0].items() if k not in
                {'snapshot_id','column','lag_months','future_value','future_values','rows','review_token'}}
        report.update(factor=' + '.join(r['factor'] for r in aligned),factors=aligned,
            factor_count=len(aligned),snapshot_ids=[s['id'] for s in snapshots],
            missing=sum(r['missing'] for r in aligned),
            rows=[{**row,'factor':r['factor'],'snapshot_id':r['snapshot_id'],'column':r['column'],
                   'unit':r['unit'],'geography':r['geography']} for r in aligned for row in r['rows']],
            warnings=list(dict.fromkeys(w for r in aligned for w in r['warnings'])))
        report['retrospective']=any(r.get('retrospective') for r in aligned)
        if report['retrospective']:
            report['policy']=WHAT_IF_POLICY
    method=payload.get('method',report['method'])
    # Factor-test variants are not standalone engine method names. A subsequent
    # fixed-method scenario uses the existing model with all its reviewed inputs.
    baseline_methods={r['model'].split(' [',1)[0] if base.get('method_selection')=='factor_test' else r['model']
                      for r in base.get('leaderboard',[])}
    allowed={'recommended','factor_test',report['method'],*[f"model:{name}" for name in baseline_methods]}
    if not isinstance(method,str) or method not in allowed:
        raise ValueError('Choose automatic selection, the baseline method or a method tested on the baseline.')
    if report.get('retrospective') and method not in {'model:' + name for name in FACTOR_METHODS}:
        raise ValueError('For a live-data what-if, choose one factor-aware method. Automatic selection cannot use unverified historical releases.')
    report['method']=method
    if payload.get('preparation') is not None:
        from .factor_preparation import validate_preparation
        report['preparation']=validate_preparation(base,datasets,factors,live,payload,profiles)
    report['review_token']=digest({'alignment':report,'snapshots':snapshots,'dataset':dataset,
                                  'baseline_manifest':base['input_manifest']})
    return report,dataset,settings,history,future,snapshots,aligned


def save_link(base, datasets, factors, payload, live=None, profiles=None, *, forecast_input=False):
    if payload.get('reviewed') is not True:
        raise ValueError('Review and approve the factor alignment before calculating.')
    try:
        request_id = str(uuid.UUID(payload.get('request_id','')))
    except (ValueError, TypeError, AttributeError):
        raise ValueError('Use a valid save request identifier.')
    report, dataset, settings, history, future, snapshots, aligned = _scenario_alignment(base,datasets,factors,payload,live,profiles)
    if report['missing'] or payload.get('review_token') != report['review_token']:
        raise ValueError('Review these exact inputs again and resolve missing or unpublished periods.')
    identifier = uuid.uuid5(uuid.NAMESPACE_URL,'factor-link:'+request_id).hex
    with datasets.lock:
        if datasets._path('dataset',identifier).exists():
            existing = datasets.get(identifier)
            proof = existing.get('import_provenance' if forecast_input else 'scenario_provenance', {})
            if proof.get('review_token') != report['review_token']:
                raise ValueError('This request has already saved different factor inputs.')
            return existing
        settings = deepcopy(settings)
        definitions={}
        driver_roles = dict(settings.get('driver_roles', {}))
        for child,snapshot in zip(aligned,snapshots):
            column=child['column']
            # Generated column IDs carry no meaning. Keep public-source factors
            # labelled external instead of letting name inference call them internal.
            if is_live_monthly(snapshot) or is_public_vintage(snapshot):
                driver_roles[column] = 'external'
            definitions[column]={
            'name':snapshot['name'],
            'unit':snapshot['unit'], 'geography':snapshot['geography'], 'source':snapshot['provider'],
            'snapshot_id':snapshot['id'], 'lag_months':child['lag_months'], 'availability_policy':child['policy'],
            'period_alignment':child['period_alignment'],'normalization':snapshot.get('normalization'),
            'source_url':snapshot.get('source_url'), 'attribution':snapshot.get('attribution'), 'license_url':snapshot.get('license_url')}
        settings['drivers'] = [*settings.get('drivers',[]), *definitions]
        settings['driver_roles'] = driver_roles
        settings['factor_definitions'] = {**settings.get('factor_definitions',{}), **definitions}
        settings['future_date_col'], settings['future_item_col'] = 'timestamp','item_id'
        settings['future_driver_policy'] = 'require'
        if report.get('preparation'):
            settings['factor_context']=report['preparation']['context']
        settings['history_calendar'] = 'gregorian'
        settings['history_grain'] = 'transactions'
        # The derived history already contains the reviewed formatting. Never
        # replay original row-index overlays onto this newly generated file.
        settings.pop('history_cell_corrections',None)
        settings.pop('history_corrections_sha256',None)
        settings['future_calendar'] = 'gregorian'
        settings['method_selection'] = report['method']
        settings['evidence_policy'] = 'reviewed_what_if' if report.get('retrospective') else 'standard'
        sources = dict(dataset['sources'])
        sources['history'] = datasets.upload('linked_factor_history.csv',history.to_csv(index=False).encode(),'history')['id']
        sources['future'] = datasets.upload('linked_factor_future.csv',future.to_csv(index=False).encode(),'future')['id']
        name = snapshots[0]['name'] + ' · linked factor' if len(snapshots)==1 else f'{len(snapshots)} factors · comparison'
        if report.get('retrospective'):
            name += ' · what-if'
        provenance = {'type':'factor_link', 'name':name,'base_run_id':base['run_id'],'base_dataset_id':dataset['id'],
            'owner':'Planner','reason':'Reviewed monthly lagged factor with explicit future assumptions.',
            'recorded_at':datetime.now(timezone.utc).isoformat(),'review_token':report['review_token'],
            'identity_basis':'review_request_not_authenticated_signature', 'orders_changed':False,'refitted':True,
            'changes':[], 'definitions':[{'factor':column,**definition} for column,definition in definitions.items()],
            'alignment':report, 'factor_snapshot_id':snapshots[0]['id'], 'factor_snapshot_sha256':digest(snapshots[0]),
            'factor_snapshots':[{'id':s['id'],'sha256':digest(s)} for s in snapshots],
            'inherited_warnings':report['warnings']+[report['policy']], 'release_dates_verified':False}
        provenance['reviewed_inputs']={key:deepcopy(payload[key]) for key in
            ('links','snapshot_id','lag_months','future_value','future_values','availability_policy',
             'period_alignment','series_ids','method','preparation') if key in payload}
        provenance['baseline_sha256']=digest(base)
        provenance['derived_inputs_sha256']=digest({'sources':sources,'settings':settings})
        if forecast_input:
            provenance['type'] = 'forecast_factors'
            provenance.pop('baseline_sha256', None)
            provenance.pop('base_run_id', None)
            return datasets.save(dataset['name'] + ' · forecast factors',sources,settings,dataset['classification'],True,
                identifier=identifier,parent_dataset_id=dataset['id'],import_provenance=provenance)
        return datasets.save(name,sources,settings,dataset['classification'],True,
            identifier=identifier,parent_dataset_id=dataset['id'],provenance=provenance)
