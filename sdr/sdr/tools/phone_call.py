"""Bounded asynchronous phone execution with durable at-most-once dispatch."""
import asyncio
import json
import math
import os
import re
import time
import httpx
from elevenlabs import AsyncElevenLabs
from google.adk.tools import FunctionTool
from common.security import require_action, SecurityError
from common.execution_store import WorkStore, normalize_phone, cached_result, PolicyDenied
from ..config import ELEVENLABS_API_KEY, ELEVENLABS_AGENT_ID, ELEVENLABS_PHONE_NUMBER_ID
from ..prompts import CALLER_PROMPT


def validate_us_phone_number(phone_number):
    try:
        return {'valid':True,'normalized':normalize_phone(phone_number),'error':None}
    except SecurityError as exc:
        return {'valid':False,'normalized':None,'error':str(exc)}


def _init_elevenlabs_client(http_client):
    if not all((ELEVENLABS_API_KEY,ELEVENLABS_AGENT_ID,ELEVENLABS_PHONE_NUMBER_ID)):
        raise ValueError('Call provider configuration is incomplete')
    client=AsyncElevenLabs(api_key=ELEVENLABS_API_KEY,timeout=10,httpx_client=http_client,follow_redirects=False)
    return client,client.conversational_ai


def _result(details,conversation_id):
    status=getattr(details,'status','unknown')
    turns=getattr(details,'transcript',None) or []
    transcript=[{'role':getattr(t,'role','unknown'),'message':str(getattr(t,'message',getattr(t,'text','')))} for t in turns]
    return {'status':status,'conversation_id':conversation_id,'transcript':transcript,
            'error':None if status=='done' else ('Provider call failed' if status=='failed' else None)}


async def _stop_call(call_sid):
    """Stop a known Twilio call; deleting an ElevenLabs transcript is not hangup."""
    account=os.getenv('TWILIO_ACCOUNT_SID',''); secret=os.getenv('TWILIO_AUTH_TOKEN','')
    if not re.fullmatch(r'AC[a-fA-F0-9]{32}',account) or not secret or not re.fullmatch(r'CA[a-fA-F0-9]{32}',call_sid or ''):
        return False
    try:
        async with httpx.AsyncClient(timeout=5,follow_redirects=False) as client:
            url=f'https://api.twilio.com/2010-04-01/Accounts/{account}/Calls/{call_sid}.json'
            current=await client.get(url,auth=(account,secret))
            if not current.is_success:
                return False
            status=current.json().get('status')
            if status in {'completed','canceled','busy','failed','no-answer'}:
                return True
            target='canceled' if status in {'queued','initiated','ringing'} else 'completed'
            response=await client.post(url,auth=(account,secret),data={'Status':target})
            return response.is_success
    except Exception:
        return False


async def reconcile_call(action_key):
    ledger=WorkStore(); row=await asyncio.to_thread(ledger.action,action_key)
    if not row or row['kind']!='calls':
        return {'status':'error','error':'Call action not found'}
    if row['state'] in {'succeeded','failed'} or not row['provider_id']:
        return cached_result(row)
    try:
        async with httpx.AsyncClient(timeout=10,follow_redirects=False) as transport:
            _,convai=_init_elevenlabs_client(transport)
            async with asyncio.timeout(12):
                details=await convai.conversations.get(row['provider_id'],request_options={'timeout_in_seconds':10,'max_retries':0})
        result=_result(details,row['provider_id'])
        if result['status'] in {'done','failed'}:
            await asyncio.to_thread(ledger.record,action_key,'succeeded' if result['status']=='done' else 'failed',result,row['provider_id'])
            return result
    except Exception:
        pass
    return cached_result(row)


async def _make_call(to_number,system_prompt,first_message,poll_interval=1.0,*,total_timeout=None):
    require_action('calls')
    ledger=WorkStore(); key=None; dispatched=False; conversation_id=None; call_sid=None
    try:
        number=normalize_phone(to_number)
        max_duration=int(os.getenv('MAX_CALL_SECONDS','120'))
        if not 60<=max_duration<=600:
            raise ValueError('MAX_CALL_SECONDS must be between 60 and 600')
        if not re.fullmatch(r'AC[a-fA-F0-9]{32}',os.getenv('TWILIO_ACCOUNT_SID','')) or len(os.getenv('TWILIO_AUTH_TOKEN',''))<16:
            raise ValueError('Twilio cancellation credentials are required before live calls')
        payload={'number':number,'system_prompt':system_prompt,'first_message':first_message,'max_duration_seconds':max_duration,
                 'agent_id':ELEVENLABS_AGENT_ID,'phone_number_id':ELEVENLABS_PHONE_NUMBER_ID}
        key=await asyncio.to_thread(ledger.propose,'calls',[number],payload)
        row=await asyncio.to_thread(ledger.reserve,key,math.ceil(max_duration/60))
        if row['state']!='reserved':
            return await reconcile_call(key)
        deadline=total_timeout if total_timeout is not None else max_duration+40
        if not 0<deadline<=660:
            raise ValueError('Invalid total call deadline')
        async with httpx.AsyncClient(timeout=10,follow_redirects=False) as transport:
            _,convai=_init_elevenlabs_client(transport)
            async with asyncio.timeout(deadline):
                await asyncio.to_thread(ledger.begin,key)
                dispatched=True
                response=await convai.twilio.outbound_call(agent_id=ELEVENLABS_AGENT_ID,
                    agent_phone_number_id=ELEVENLABS_PHONE_NUMBER_ID,to_number=number,
                    call_recording_enabled=False,telephony_call_config={'ringing_timeout_secs':15},
                    conversation_initiation_client_data={'dynamic_variables':{'koe_action_key':key},
                        'conversation_config_override':{'conversation':{'max_duration_seconds':max_duration},
                            'agent':{'prompt':{'prompt':system_prompt},'first_message':first_message}}},
                    request_options={'timeout_in_seconds':10,'max_retries':0})
                conversation_id=getattr(response,'conversation_id',None)
                call_sid=getattr(response,'call_sid',None) or getattr(response,'callSid',None)
                if not getattr(response,'success',True) or not conversation_id:
                    raise ValueError('Provider did not confirm a conversation identifier')
                await asyncio.to_thread(ledger.record,key,'initiated',{'call_sid':call_sid},conversation_id)
                while True:
                    await asyncio.to_thread(ledger.check,key)
                    details=await convai.conversations.get(conversation_id,request_options={'timeout_in_seconds':10,'max_retries':0})
                    result=_result(details,conversation_id)
                    if result['status'] in {'done','failed'}:
                        result['call_sid']=call_sid
                        await asyncio.to_thread(ledger.record,key,'succeeded' if result['status']=='done' else 'failed',result,conversation_id)
                        return {**result,'action_key':key}
                    await asyncio.sleep(max(0.05,min(float(poll_interval),2)))
    except asyncio.CancelledError:
        if dispatched:
            stopped=await _stop_call(call_sid)
            await asyncio.to_thread(ledger.record,key,'unknown',{'status':'cancelled','hangup_confirmed':stopped,'call_sid':call_sid},conversation_id)
        raise
    except Exception as exc:
        category=('timeout' if isinstance(exc,TimeoutError) else 'policy' if isinstance(exc,SecurityError)
                  else 'authentication' if getattr(exc,'status_code',None) in {401,403}
                  else 'quota' if getattr(exc,'status_code',None)==429 else 'provider')
        rejected=dispatched and conversation_id is None and getattr(exc,'status_code',None) in {400,401,403,404,422,429}
        result={'status':'failed' if rejected else 'unknown' if dispatched else 'error','error_category':category,
                'error':str(exc) if isinstance(exc,(SecurityError,ValueError)) else 'Call provider request failed',
                'conversation_id':conversation_id,'call_sid':call_sid,'action_key':key,'transcript':[]}
        if dispatched:
            result['hangup_confirmed']=await _stop_call(call_sid)
            await asyncio.to_thread(ledger.record,key,'failed' if rejected else 'unknown',result,conversation_id)
        return result


async def phone_call(business_data:dict,proposal:str):
    require_action('calls')
    if not isinstance(business_data,dict) or not isinstance(proposal,str) or not proposal.strip():
        return {'status':'error','error_category':'validation','error':'Business and proposal are required'}
    phone=business_data.get('phone') or business_data.get('phone_number')
    validation=validate_us_phone_number(phone)
    if not validation['valid']:
        return {'status':'error','error_category':'validation','error':validation['error']}
    prompt=CALLER_PROMPT.format(business_data=json.dumps(business_data,sort_keys=True),proposal=proposal)
    return await _make_call(validation['normalized'],prompt,
        'Hello, this is Koe Syndicate. Is this a convenient time to discuss your business website?')

phone_call_tool=FunctionTool(func=phone_call)
