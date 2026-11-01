import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lead_finder.lead_finder.sub_agents.merger_agent import merger_agent
from google.adk.sessions import Session

# Set dummy API keys if not present
os.environ['GOOGLE_API_KEY'] = 'dummy' if 'GOOGLE_API_KEY' not in os.environ else os.environ['GOOGLE_API_KEY']

async def main():
    print('Starting manual merger agent test...')
    session = Session(id="test-session", appName="test-app", userId="test-user", state={"city": "New Delhi"})
    try:
        from google.adk.agents.agent_runner import AgentRunner
        runner = AgentRunner(merger_agent)
        
        async for event in runner.run_async(
            user_id="test-user",
            session_id="test-session",
            new_message="Here are the potential leads: [{'name': 'Test Business', 'address': '123 Test St', 'phone': '12345', 'category': 'Test'}]"
        ):
            print("EVENT:", type(event).__name__, event.content if hasattr(event, "content") else "")
            
        print("Merger agent finished.")
        
        state_data = await runner.session_service.get_session("test-app", "test-user", "test-session")
        print("Final session state:")
        print(state_data.state)
        
    except Exception as e:
        print("AGENT RUN ERROR:", e)

asyncio.run(main())
