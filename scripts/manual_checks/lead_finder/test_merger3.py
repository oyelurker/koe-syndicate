import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lead_finder.lead_finder.sub_agents.merger_agent import merger_agent
from google.adk.sessions import Session
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk import Runner

# Set dummy API keys if not present
os.environ['GOOGLE_API_KEY'] = 'dummy' if 'GOOGLE_API_KEY' not in os.environ else os.environ['GOOGLE_API_KEY']

async def main():
    print('Starting manual merger agent test...')
    try:
        runner = Runner(
            app_name="test_app",
            agent=merger_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
        )
        
        await runner.session_service.create_session(
            app_name="test_app",
            user_id="test-user",
            session_id="test-session",
            state={"city": "New Delhi"}
        )
        
        # Using a dict for new_message
        msg_dict = {"text": "Here are the potential leads: [{'name': 'Test Business', 'address': '123 Test St', 'phone': '12345', 'category': 'Test'}]"}
        
        async for event in runner.run_async(
            user_id="test-user",
            session_id="test-session",
            new_message=msg_dict
        ):
            print("EVENT:", type(event).__name__, getattr(event, "content", getattr(event, "message", "")))
            
        print("Merger agent finished.")
        
        state_data = await runner.session_service.get_session("test_app", "test-user", "test-session")
        print("Final session state:")
        print(state_data.state)
        
    except Exception as e:
        print("AGENT RUN ERROR:", e)

asyncio.run(main())
