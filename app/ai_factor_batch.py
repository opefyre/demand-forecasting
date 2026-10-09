"""Read-only SDK proposals; human confirmation reuses reviewed factor/batch saves."""
from copy import deepcopy
import uuid
from pydantic import BaseModel, ConfigDict, Field
from .ai_factor_scenarios import AssistantFactorScenarios, FactorAssumption
from .factor_imports import digest
from .factor_links import preview_link, save_link
from .factor_batch import preview_batch, save_batch
from .factor_preparation import connected_source_readiness


class FactorGroup(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    series_ids:list[str]=Field(min_length=1,max_length=100)
    links:list[FactorAssumption]=Field(min_length=1,max_length=8)
    method:str=Field(min_length=1,max_length=120)


class AssistantFactorBatch:
    def __init__(self,run,datasets,factors,live=None,profiles=None):
        self.run,self.datasets,self.factors,self.live,self.profiles=run,datasets,factors,live,profiles
        self.scenarios=AssistantFactorScenarios(run,datasets,factors)

    def choices(self):
        options=self.scenarios.choices()
        profiles=self.profiles.for_run(self.run)['profiles'] if self.profiles else []
        states=self.live.listing()['sources'] if self.live else []
        for source in options['snapshots']:
            source.update(self.readiness(source['id'],states))
        return {**options,'profiles':profiles,'max_groups':20,
            'public_history_methods':['factor_test','recommended'],
            'note':'Exact series IDs; no overlap. Only connected sources are available to AI. Future values must come from the user. Missing details can open the batch review instead.'}

    def readiness(self,identifier,states=None):
        return connected_source_readiness(identifier,self.live,states)

    def scope(self,ids):
        if (not isinstance(ids,list) or not 1<=len(ids)<=100 or any(not isinstance(s,str) for s in ids)
                or len(ids)!=len(set(ids)) or set(ids)-(set(self.run['series'])-{'__all__'})):
            raise ValueError('Choose distinct exact customer/product IDs from inspect_factor_batch.')
        return sorted(ids)

    def handoff(self,ids):
        self.choices();ids=self.scope(ids)
        return {'kind':'factor_batch_review','run_id':self.run['run_id'],'series_ids':ids,
            'run_sha256':digest(self.run),'scope':[{'id':s,**self.run.get('metadata',{}).get(s,{})} for s in ids]}

    def open(self,action):
        fresh=self.handoff(action['series_ids'])
        if fresh!=action:raise ValueError('The forecast changed. Ask for a new batch review.')
        return {'workflow':'factor_batch_review','run_id':self.run['run_id'],'series_ids':action['series_ids']}

    def preview(self,groups):
        if not isinstance(groups,list) or not 1<=len(groups)<=20:raise ValueError('Choose one to twenty factor groups.')
        options=self.choices();seen=set();payloads=[];summaries=[]
        for supplied in groups:
            group=FactorGroup.model_validate(supplied);ids=self.scope(group.series_ids)
            if seen.intersection(ids):raise ValueError('A customer/product can appear in only one group.')
            seen.update(ids)
            links=[r.model_dump(exclude_none=True) for r in group.links]
            for link in links:
                if not self.readiness(link['snapshot_id'])['ready']:raise ValueError('A source is stale, unconnected or needs permission. Review Data → Factors.')
            automatic=group.method in options['public_history_methods']
            method=options['methods'][0] if automatic and options['methods'] else group.method
            payload,report,summary=self.scenarios.preview(links,method)
            payload['series_ids']=ids;payload['method']=group.method
            report=preview_link(self.run,self.datasets,self.factors,payload,self.live,self.profiles)
            summary={**summary,'scope':[{'id':s,**self.run.get('metadata',{}).get(s,{})} for s in ids],
                'method':report['method'],'missing':report['missing'],'series_count':len(ids),
                'future_rows':[r for r in report['rows'] if r['kind']=='future']}
            payloads.append({'payload':payload,'review_token':report['review_token']});summaries.append(summary)
        report={'groups':summaries,'unchanged_series_ids':sorted(set(self.run['series'])-{'__all__'}-seen),
            'months':options['forecast_periods'],'orders_changed':False,
            'policy':'Each group is calculated separately. Others keep the baseline. Review current orders afterwards. No combined accuracy or range claim.'}
        token=digest({'report':report,'inputs':payloads,'run':self.run})
        return payloads,report,token

    def proposal(self,groups):
        payloads,report,token=self.preview(groups)
        if any(g['missing'] for g in report['groups']):raise ValueError('Missing observations or future assumptions. Review the gaps; never invent values.')
        return {'kind':'factor_batch','base_run_id':self.run['run_id'],'groups':deepcopy(groups),
            'review_token':token,'run_sha256':digest(self.run),'preview':report}

    def save(self,action,request):
        payloads,report,token=self.preview(action['groups'])
        if (action['base_run_id']!=self.run['run_id'] or action['run_sha256']!=digest(self.run)
                or token!=action['review_token'] or report!=action['preview']):
            raise ValueError('Batch inputs or sources changed. Ask for a fresh review.')
        ids=[]
        for i,group in enumerate(payloads):
            identifier=str(uuid.uuid5(uuid.NAMESPACE_URL,f'{request}:group:{i}'))
            saved=save_link(self.run,self.datasets,self.factors,{**group['payload'],'review_token':group['review_token'],
                'reviewed':True,'request_id':identifier},self.live,self.profiles)
            ids.append(saved['id'])
        preview=preview_batch(self.run,self.datasets,self.factors,{'dataset_ids':ids,'require_connected_sources':True},self.live,self.profiles)
        return save_batch(self.run,self.datasets,self.factors,{'dataset_ids':ids,'review_token':preview['review_token'],
            'reviewed':True,'require_connected_sources':True,'request_id':str(uuid.uuid5(uuid.NAMESPACE_URL,request))},self.live,self.profiles)
