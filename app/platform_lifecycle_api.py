"""Company-owned naming, reversible archive and recorded revision navigation."""
from typing import Literal
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from .platform_identity import principal
from .platform_sales_api import source_scope
from .resource_lifecycle import MetadataConflict, family

Kind = Literal['sources','datasets','forecasts','runs']

class Version(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    version: int = Field(ge=0,strict=True)

class Rename(Version):
    name: str = Field(min_length=1,max_length=160)


def install_platform_lifecycle(api, workspaces):
    router = APIRouter(tags=['Resource lifecycle'])

    def resolve(request, kind, key, write=False):
        who = principal(request)
        if workspaces is None: raise HTTPException(503,'Company storage is not configured.')
        w = workspaces.for_principal(who)
        try:
            if kind=='sources':
                row=w.datasets.source(key)[0]; scope=source_scope(row['role'])
            elif kind=='datasets':
                row=w.datasets.get(key); scope='inputs'
            elif kind=='forecasts':
                row=w.jobs.get_group(key); scope='forecasts' if write else 'drafts'
                if not write and 'drafts:read' not in who['permissions']:
                    from .company_context import ReportAccess
                    principal(request,'reports:read')
                    access=ReportAccess(w,who);visible=False
                    for run in w.list_runs():
                        if run.get('forecast_group_id')==key:
                            try:access.approved(run['run_id']);visible=True
                            except HTTPException:continue
                    if not visible:raise HTTPException(404,'Approved report not found.')
                    scope='reports'
            else:
                from .company_context import ReportAccess
                principal(request,'forecasts:write' if write else 'reports:read')
                value=ReportAccess(w,who).run(key)
                # Grouped methods are one forecast, with one shared name/status.
                if value.get('forecast_group_id'):
                    return resolve(request,'forecasts',value['forecast_group_id'],write)
                row={'id':key,'name':value.get('forecast_name') or value.get('dataset_name') or 'Forecast',
                     'parent_run_id':value.get('base_run_id'),'created_at':value.get('issued_at')}
                scope='forecasts' if write else 'reports'
            principal(request,scope+(':write' if write else ':read'))
        except ValueError:
            raise HTTPException(404,'Item not found.') from None
        return w,kind,key,row

    def present(w,kind,key,row):
        # Return lightweight metadata, not job owner tokens or source bytes.
        value={k:row[k] for k in ('name','created_at','parent_dataset_id','parent_run_id') if k in row}
        return w.lifecycle.present(kind,key,dict(value,id=key,kind=kind))

    @router.get('/{kind}/{resource_id}/metadata')
    def metadata(kind:Kind,resource_id:str,request:Request):
        return present(*resolve(request,kind,resource_id))

    @router.patch('/{kind}/{resource_id}/metadata')
    def rename(kind:Kind,resource_id:str,body:Rename,request:Request):
        return change(request,kind,resource_id,body.version,name=body.name)

    def change(request,kind,key,version,**changes):
        w,kind,key,row=resolve(request,kind,key,True)
        if kind=='forecasts' and w.jobs.active_group_jobs(key) and changes.get('archived'):
            raise HTTPException(409,'Wait for the forecast to finish before archiving it.')
        try:w.lifecycle.update(kind,key,version,**changes)
        except MetadataConflict as exc:raise HTTPException(409,str(exc)) from exc
        return present(w,kind,key,row)

    @router.post('/{kind}/{resource_id}/archive')
    def archive(kind:Kind,resource_id:str,body:Version,request:Request):
        return change(request,kind,resource_id,body.version,archived=True)

    @router.post('/{kind}/{resource_id}/restore')
    def restore(kind:Kind,resource_id:str,body:Version,request:Request):
        return change(request,kind,resource_id,body.version,archived=False)

    @router.get('/{kind}/{resource_id}/revisions')
    def revisions(kind:Kind,resource_id:str,request:Request):
        w,kind,key,row=resolve(request,kind,resource_id)
        if kind=='sources': rows=[row]; parent='unused'
        elif kind=='datasets':rows=w.datasets.list();parent='parent_dataset_id'
        else:
            from .company_context import ReportAccess
            access=ReportAccess(w,principal(request));rows=[];parent='parent_run_id'
            runs=w.list_runs();canonical={r['run_id']:r.get('forecast_group_id') or r['run_id'] for r in runs}
            parent='parent_id'
            for group in w.jobs.list_groups(limit=None):
                try:resolve(request,'forecasts',group['id'])
                except HTTPException:continue
                permitted=[]
                for run in runs:
                    if run.get('forecast_group_id')!=group['id']:continue
                    if not access.drafts:
                        try:access.approved(run['run_id'])
                        except HTTPException:continue
                    permitted.append(run['run_id'])
                rows.append(dict(id=group['id'],kind='forecasts',name=group['name'],created_at=group['created_at'],
                    parent_id=group['jobs'][0]['payload'].get('parent_forecast_id') if group['jobs'] else None,
                    run_id=permitted[0] if permitted else None))
            for r in runs:
                if r.get('forecast_group_id'):continue
                if not access.drafts:
                    try:access.approved(r['run_id'])
                    except HTTPException:continue
                rows.append(dict(id=r['run_id'],kind='runs',name=r.get('forecast_name') or r.get('dataset_name') or 'Forecast',
                                 created_at=r.get('issued_at'),parent_id=canonical.get(r.get('base_run_id')),run_id=r['run_id']))
        items=[]
        for r in family(rows,key,parent):
            value=present(w,r.get('kind',kind),r['id'],r)
            value['parent_id']=r.get(parent)
            if value['parent_id'] not in {item['id'] for item in rows}:value['parent_id']=None
            if 'run_id' in r:value['run_id']=r['run_id']
            items.append(value)
        def issued(r):
            from datetime import datetime
            value=r.get('created_at')
            return value if isinstance(value,(int,float)) else datetime.fromisoformat(value).timestamp() if value else 0
        return {'revisions':sorted(items,key=issued,reverse=True)}

    api.include_router(router)
