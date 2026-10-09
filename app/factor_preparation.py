"""Read-only source suggestions. Existing alignment owns every numerical match."""
from zipfile import BadZipFile

from .commodity_prices import SERIES
from .factor_imports import digest
from .factor_links import choices, inputs, preview_link
from .live_factor_alignment import FACTOR_METHODS
from .factor_context import FactorContext

POLICY = 'source-preparation-v1'


def connected_source_readiness(identifier,live=None,states=None):
    states=states if states is not None else live.listing()['sources'] if live else []
    row=next(((state,s) for state in states for s in state.get('series',[]) if s['id']==identifier),None)
    if not row:return {'ready':False,'note':'Connected source status is unavailable. Review Data → Factors.'}
    state,series=row
    if state['id']=='iran_cpi' and not state.get('permission_confirmed'):
        return {'ready':False,'note':'Source-use permission is needed.'}
    if state.get('refresh_overdue') or series.get('data_behind'):
        return {'ready':False,'note':'Refresh the source before using it.'}
    return {'ready':True,'note':'Review historical coverage, timing and future assumptions.'}


def tested_methods(run):
    return sorted({r['model'].split(' [',1)[0] if run.get('method_selection')=='factor_test' else r['model']
                   for r in run.get('leaderboard',[])})


def prepare_sources(run, datasets, factors, live, context, profile=None):
    context=FactorContext.model_validate(context).model_dump()
    source,settings,_,_,_=inputs(run,datasets)
    options=choices(run,datasets,factors)
    series_ids=[profile['series_id']] if profile else None
    snapshots={r['id']:r for r in options['snapshots'] if r['public_vintage'] or r['live_what_if']}
    latest={}
    for snapshot in factors.list():
        if snapshot['id'] in snapshots:latest.setdefault(snapshot['factor_id'],snapshot)
    states={s['id']:s for s in live.listing()['sources']} if live else {}
    wanted=[('iran_cpi_headline','iran_cpi','Monthly Iran prices',
             'National price pressure may affect buying. Product relevance still needs review.')]
    # The source adapter owns the exact CPI identifier, rather than a UI alias.
    from .iran_cpi import FACTOR_ID as CPI
    wanted[0]=(CPI,*wanted[0][1:])
    if context['currency_exposure']:
        wanted.append(('servix_usd_rls','servix','Iran exchange rate',
                       'You marked currency exposure. Verify this quote market matches your business.'))
    if context['global_supply']:
        wanted.append(('global_supply_pressure','supply','Global supply pressure',
                       'You marked overseas supply exposure. This is global context, not local demand.'))
    if context['hormuz_route']:
        from .hormuz_traffic import FACTOR_ID as HORMUZ
        wanted.append((HORMUZ,'hormuz','Hormuz shipping',
                       'You marked this route as relevant. Ship counts are a disruption proxy, not orders.'))
    for material in context['materials']:
        wanted.append(('worldbank_'+material,'commodities',SERIES[material][0],
                       'You selected this material. Global reference prices may differ from your local prices.'))
    methods=[name for name in tested_methods(run) if name in FACTOR_METHODS]
    fixed='Ridge + drivers' if 'Ridge + drivers' in methods else next(iter(methods),None)
    rows=[]
    for factor_id,source_id,name,reason in wanted:
        state=states.get(source_id,{})
        snapshot=latest.get(factor_id)
        row=dict(factor_id=factor_id,source_id=source_id,name=name,reason=reason,
                 status='not_connected',can_prepare=False,snapshot_id=None,
                 note='Connect this source in Data → Factors.',captured_at=None,
                 history_missing=None,future_missing=None,lag_months=2)
        if source_id=='iran_cpi' and not state.get('permission_confirmed'):
            row.update(status='permission_needed',note='Commercial-use permission has not been recorded.')
        elif snapshot:
            row.update(snapshot_id=snapshot['id'],captured_at=snapshot['captured_at'],
                       unit=snapshot['unit'],geography=snapshot['geography'],provider=snapshot['provider'])
            status=next((s for s in state.get('series',[]) if s['id']==snapshot['id']),{})
            row['data_behind']=bool(status.get('data_behind'))
            row['refresh_overdue']=bool(state.get('refresh_overdue'))
            row['source_status']=state.get('status')
            row['last_success']=state.get('last_success')
            row['cooldown_until']=state.get('cooldown_until')
            row['what_if']=snapshots[snapshot['id']]['live_what_if']
            method='model:'+fixed if row['what_if'] and fixed else 'factor_test'
            row['method']=method
            link=dict(snapshot_id=snapshot['id'],lag_months=2,
                      availability_policy='reviewed_what_if' if row['what_if'] else 'vintage_month_end')
            if snapshot.get('calendar')=='jalali':link['period_alignment']='last_completed_jalali_month'
            row['link']=link
            if row['what_if'] and not fixed:
                row.update(status='method_needed',note='Recalculate a baseline with a supported factor-aware method.')
            else:
                try:
                    report=preview_link(run,datasets,factors,{'links':[link],'method':method,
                                                            **({'series_ids':series_ids} if series_ids else {})})
                    past=[r for r in report['rows'] if r['kind']=='history']
                    future=[r for r in report['rows'] if r['kind']=='future']
                    row.update(history_missing=sum(r['value'] is None for r in past),history_months=len(past),
                               future_missing=sum(r['value'] is None for r in future),
                               future_months=[{'period':r['sales_month'],'known_value':r['value'],
                                              'source':r['treatment']} for r in future],
                               policy=report['policy'])
                    if row['data_behind'] or row['refresh_overdue']:
                        row.update(status='refresh_needed',note='Refresh this source and check again. Old observations are not renewed.')
                    elif row['history_missing']:
                        row.update(status='history_missing',note=f"{row['history_missing']} required historical months are missing. No gap filling.")
                    else:
                        row.update(can_prepare=True,status='assumptions_needed' if row['future_missing'] else 'ready',
                                   note=f"Review {row['future_missing']} future assumptions." if row['future_missing'] else 'Required months are covered. Review source timing.')
                except (ValueError,TypeError,KeyError,OSError,BadZipFile):
                    # Never expose raw provider/retained-file errors to the UI.
                    row.update(status='unavailable',note='Source evidence cannot be matched safely. Review the source or sales history.')
        rows.append(row)
    result={'policy':POLICY,'context':context,'recommendations':rows,
            'profile':profile,'series_ids':series_ids,
            'materials':[[key,name] for key,(name,_) in SERIES.items()],
            'planning_calendar':settings.get('month_basis','gregorian'),
            'note':'Suggestions are based on declared exposure, not proven accuracy. Two-month timing is a starting point; review it. No source is fetched, no future value invented and no order changed.',
            'context_only':['Annual Iran inflation and industry growth are background only, not monthly model inputs.']}
    result['review_token']=digest({'result':result,'run':run,'dataset':source,
                                  'snapshots':[latest[r['factor_id']] for r in rows if r['snapshot_id']]})
    return result


def preparation_report(run,datasets,factors,live,payload,profiles=None):
    if set(payload)=={'profile_series_id'}:
        if not profiles:raise ValueError('Saved factor profiles are unavailable.')
        if not isinstance(payload['profile_series_id'],str):raise ValueError('Choose an exact saved profile.')
        profile=next((r for r in profiles.for_run(run)['profiles'] if r['series_id']==payload['profile_series_id']),None)
        if not profile:raise ValueError('This profile no longer matches an active customer/product. Review it in Customers.')
        return prepare_sources(run,datasets,factors,live,profile['context'],profile)
    return prepare_sources(run,datasets,factors,live,payload)


def validate_preparation(run,datasets,factors,live,payload,profiles=None):
    evidence=payload.get('preparation')
    if evidence is None:return None
    required={'context','review_token','snapshot_ids'}
    if not isinstance(evidence,dict) or set(evidence)-required not in (set(),{'profile_series_id'}) or not required<=set(evidence):
        raise ValueError('Check the source suggestions again before using them.')
    report=preparation_report(run,datasets,factors,live,
        {'profile_series_id':evidence['profile_series_id']} if 'profile_series_id' in evidence else evidence['context'],profiles)
    ids=evidence['snapshot_ids']
    eligible={r['snapshot_id'] for r in report['recommendations'] if r['can_prepare']}
    links=payload.get('links',[])
    if (not isinstance(ids,list) or not ids or any(not isinstance(i,str) for i in ids)
            or len(ids)!=len(set(ids)) or set(ids)-eligible
            or set(ids)!={r.get('snapshot_id') for r in links}
            or report['context']!=evidence['context']
            or (report['series_ids'] is not None and payload.get('series_ids')!=report['series_ids'])
            or evidence['review_token']!=report['review_token']):
        raise ValueError('Sources or exposure changed. Check suggestions and review the exact inputs again.')
    return {'policy':POLICY,'context':report['context'],'profile':report['profile'],'series_ids':report['series_ids'],'review_token':report['review_token'],
            'sources':[r for r in report['recommendations'] if r['snapshot_id'] in ids],
            'note':report['note']}
