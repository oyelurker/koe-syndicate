import asyncio
import sys
import logging
import os
sys.path.insert(0, r'c:\Users\savy\Desktop\New folder\Koe Syndicate-main-copy for further\lead_finder')

from dotenv import load_dotenv
load_dotenv(r'c:\Users\savy\Desktop\New folder\Koe Syndicate-main-copy for further\.env')

from agent_executor import LeadFinderAgentExecutor
from a2a.server.agent_execution import RequestContext
from a2a.types import A2AMessage, A2ARole, DataPart
from a2a.server.events import EventQueue

logging.basicConfig(level=logging.INFO)

async def test_agent():
    executor = LeadFinderAgentExecutor()
    message = A2AMessage(
        taskId="test_1",
        contextId="ctx_1",
        messageId="msg_1",
        role=A2ARole.user,
        parts=[DataPart(data={"city": "Delhi", "operation": "find_leads"})]
    )
    context = RequestContext(
        message=message,
        task_id="test_1",
        context_id="ctx_1"
    )
    queue = EventQueue()
    print("Executing LeadFinderAgentExecutor...")
    await executor.execute(context, queue)
    
    events = []
    while not queue.empty():
        events.append(await queue.get())
        
    print(f"Total events generated: {len(events)}")
    for e in events:
        print(f"Event: {e}")

asyncio.run(test_agent())
