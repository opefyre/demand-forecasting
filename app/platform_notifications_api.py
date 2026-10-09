"""Interactive administrator-only outbound notifications and delivery receipts."""
from fastapi import APIRouter,Depends,HTTPException,Query,Request
from pydantic import Field,StrictBool
from .notifications import DestinationInput,NotificationError,NotificationConflict,tick
from .platform_sales_api import StrictInput
from .platform_identity import principal
from .company_context import personal_owner


class DestinationUpdate(DestinationInput):
    version:int=Field(ge=1,strict=True)

class Version(StrictInput):
    version:int=Field(ge=1,strict=True)

class Send(Version):
    request_id:str=Field(min_length=8,max_length=100)
    confirmed:StrictBool=False
    duplicate_confirmed:StrictBool=False


def install_platform_notifications(api,workspaces,service=None):
    def admin(request):
        who=principal(request,'connections:manage',interactive=True)
        if who['role']!='admin':raise HTTPException(403,'Administrator access required.')
        if workspaces is None:raise HTTPException(503,'Company storage is unavailable.')
        return workspaces.for_principal(who),personal_owner(who)

    def guard(request:Request):admin(request)
    router=APIRouter(prefix='/notifications',tags=['Notifications'],dependencies=[Depends(guard)])

    def call(fn,missing=False):
        try:return fn()
        except NotificationConflict as exc:raise HTTPException(409,str(exc)) from None
        except NotificationError as exc:raise HTTPException(404 if missing else 400,str(exc)) from None
        except Exception:raise HTTPException(503,'Notifications are unavailable. Existing history is kept.') from None

    def check(w,owner):
        from .company_workflows import schedule_authorized
        return schedule_authorized(service,w,owner)

    def origin():
        if service is None:raise NotificationError('Company notification sending is not configured.')
        return service.config.origin

    @router.get('/destinations')
    def listing(request:Request,include_archived:bool=False):
        w,_=admin(request)
        return {'destinations':call(lambda:w.notifications.list(include_archived))}

    @router.post('/destinations',status_code=201)
    def create(body:DestinationInput,request:Request):
        w,owner=admin(request)
        return call(lambda:w.notifications.save(body,owner))

    @router.get('/destinations/{destination_id}')
    def get(destination_id:str,request:Request):
        w,_=admin(request)
        return call(lambda:w.notifications.get(destination_id),True)

    @router.put('/destinations/{destination_id}')
    def update(destination_id:str,body:DestinationUpdate,request:Request):
        w,owner=admin(request);call(lambda:w.notifications.get(destination_id),True)
        return call(lambda:w.notifications.save(DestinationInput.model_validate(body.model_dump(exclude={'version'})),owner,destination_id,body.version))

    @router.delete('/destinations/{destination_id}')
    def archive(destination_id:str,body:Version,request:Request):
        w,owner=admin(request);call(lambda:w.notifications.get(destination_id),True)
        return call(lambda:w.notifications.archive(destination_id,body.version,True,owner))

    @router.post('/destinations/{destination_id}/restore')
    def restore(destination_id:str,body:Version,request:Request):
        w,owner=admin(request);call(lambda:w.notifications.get(destination_id),True)
        return call(lambda:w.notifications.archive(destination_id,body.version,False,owner))

    @router.post('/destinations/{destination_id}/test',status_code=202)
    def test(destination_id:str,body:Send,request:Request):
        w,owner=admin(request);call(lambda:w.notifications.get(destination_id),True)
        if not body.confirmed:raise HTTPException(400,'Confirm sending a test to this destination.')
        call(origin)
        receipt=call(lambda:w.notifications.queue(destination_id,'test','test:'+body.request_id,owner,version=body.version))
        call(lambda:w.notifications.drain(lambda actor:check(w,actor),origin()))
        return w.notifications.delivery(receipt['id'])

    @router.get('/deliveries')
    def history(request:Request,limit:int=Query(default=100,ge=1,le=500),offset:int=Query(default=0,ge=0),destination_id:str|None=None):
        w,_=admin(request)
        if destination_id:call(lambda:w.notifications.get(destination_id),True)
        return call(lambda:w.notifications.history(limit,offset,destination_id))

    @router.get('/deliveries/{delivery_id}')
    def receipt(delivery_id:str,request:Request):
        w,_=admin(request)
        return call(lambda:w.notifications.delivery(delivery_id),True)

    @router.post('/deliveries/{delivery_id}/retry',status_code=202)
    def retry(delivery_id:str,body:Send,request:Request):
        w,owner=admin(request);call(lambda:w.notifications.delivery(delivery_id),True)
        if not body.confirmed:raise HTTPException(400,'Confirm resending this notification.')
        call(origin)
        receipt=call(lambda:w.notifications.retry(delivery_id,body.request_id,body.version,owner,body.duplicate_confirmed))
        call(lambda:w.notifications.drain(lambda actor:check(w,actor),origin()))
        return w.notifications.delivery(receipt['id'])

    @router.post('/check')
    def check_pending(request:Request):
        w,_=admin(request)
        return {'deliveries':call(lambda:tick(w,lambda actor:check(w,actor),origin()))}

    api.include_router(router)
    install_scheduler(api,workspaces,service)


def install_scheduler(api,workspaces,service):
    if workspaces is None or service is None:return
    from .platform_identity import COMPANY_ID
    from .company_workflows import schedule_authorized
    def check():
        if not workspaces.root.exists():return
        for path in workspaces.root.iterdir():
            if path.is_symlink() or not path.is_dir() or not COMPANY_ID.fullmatch(path.name) or not (path/'notifications.sqlite3').is_file():continue
            w=workspaces.for_principal({'company_id':path.name})
            try:tick(w,lambda owner:schedule_authorized(service,w,owner),service.config.origin)
            except Exception:continue
    def start():
        from apscheduler.schedulers.background import BackgroundScheduler
        scheduler=BackgroundScheduler(timezone='UTC')
        scheduler.add_job(check,'interval',minutes=1,id='company-notifications',max_instances=1,coalesce=True)
        scheduler.start();api.state.notification_scheduler=scheduler
    def stop():
        scheduler=getattr(api.state,'notification_scheduler',None)
        if scheduler:scheduler.shutdown(wait=False)
    api.router.add_event_handler('startup',start);api.router.add_event_handler('shutdown',stop)
