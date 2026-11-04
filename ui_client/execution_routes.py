"""Owner-only policy/review/job controls. Agents cannot grant themselves approval."""
import asyncio
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from common.execution_store import WorkStore
from common.security import SecurityError, execution

router=APIRouter(prefix='/api')

class Policy(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    hourly_limit:int=Field(ge=0,le=100000)
    daily_limit:int=Field(ge=0,le=100000)
    concurrency:int=Field(ge=0,le=100)
    daily_units:int=Field(ge=0,le=100000)
    timezone:str=Field(max_length=100)
    start_hour:int=Field(ge=0,le=23)
    end_hour:int=Field(ge=1,le=24)
    weekdays:list[int]=Field(min_length=1,max_length=7)
    recipients:list[str]=Field(max_length=1000)
    unit_costs:dict[str,int]

class Approval(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    action_key:str=Field(pattern='^[a-f0-9]{64}$')
    seconds:int=Field(900,ge=1,le=3600)

class Suppression(BaseModel):
    model_config=ConfigDict(extra='forbid',strict=True)
    recipient:str=Field(max_length=254)
    reason:str=Field('Owner opt-out',max_length=200)

@router.put('/outreach/policy')
async def configure_policy(policy:Policy):
    try:
        await asyncio.to_thread(WorkStore().configure,policy.model_dump())
        return {'success':True}
    except (SecurityError,ValueError,KeyError):
        return JSONResponse({'error':'Invalid or unauthorized outreach policy'},400)

@router.get('/outreach/proposals')
async def proposals():
    return {'proposals':await asyncio.to_thread(WorkStore().proposals)}

@router.post('/outreach/approvals')
async def approve(approval:Approval):
    try:
        await asyncio.to_thread(WorkStore().approve,approval.action_key,approval.seconds)
        return {'success':True}
    except SecurityError as exc:
        return JSONResponse({'error':str(exc)},403)

@router.post('/outreach/suppressions')
async def suppress(request:Suppression):
    try:
        await asyncio.to_thread(WorkStore().suppress,request.recipient,request.reason)
        return {'success':True}
    except SecurityError as exc:
        return JSONResponse({'error':str(exc)},400)

@router.get('/outreach/audit')
async def audit():
    return {'decisions':await asyncio.to_thread(WorkStore().audit)}

@router.get('/jobs')
async def jobs():
    return {'jobs':await asyncio.to_thread(WorkStore().jobs,execution.get().owner)}

@router.post('/jobs/{identity}/cancel')
async def cancel(identity:str):
    ok=await asyncio.to_thread(WorkStore().cancel_job,identity)
    return JSONResponse({'cancelled':ok},200 if ok else 404)


@router.post('/outreach/actions/{key}/dispatch')
async def dispatch_approved(key:str):
    try:
        identity=await asyncio.to_thread(WorkStore().queue_approved,key)
        return JSONResponse({'success':True,'job_id':identity,'message':'Approved action queued'},202)
    except SecurityError as exc:
        return JSONResponse({'error':str(exc)},403)


@router.post('/outreach/actions/{key}/reconcile')
async def reconcile(key:str):
    import httpx
    from common.security import Execution,ServiceAuth,service_url
    ledger=WorkStore()
    row=await asyncio.to_thread(ledger.owner_action,key)
    if not row:
        return JSONResponse({'error':'Action not found'},404)
    current=execution.get()
    context=Execution(current.owner,current.mode,row['campaign'])
    token=execution.set(context)
    try:
        if row['kind']=='calendar':
            from .calendar_routes import reconcile_meeting
            return await reconcile_meeting(key)
        async with httpx.AsyncClient(auth=ServiceAuth('ui-client','sdr'),timeout=30) as client:
            response=await client.post(service_url('sdr')+'/internal/actions/'+key+'/reconcile',json={})
            response.raise_for_status()
            return response.json()
    except Exception:
        return JSONResponse({'error':'Provider evidence unavailable; action remains quarantined'},502)
    finally:
        execution.reset(token)


@router.get('/outreach/policy')
async def current_policy():
    return {'policy':await asyncio.to_thread(WorkStore().policy)}

@router.get('/outreach/actions')
async def action_receipts():
    return {'actions':await asyncio.to_thread(WorkStore().actions)}
