import asyncio
import sys
import os
import json
import traceback
import google.genai.types as genai_types
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk import Runner

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from lead_finder.lead_finder.agent import lead_finder_agent

async def main():
    print('Starting manual lead_finder_agent test...')
    
    runner = Runner(
        app_name="test_app",
        agent=lead_finder_agent,
        artifact_service=InMemoryArtifactService(),
        session_service=InMemorySessionService(),
    )
    
    await runner.session_service.create_session(
        app_name="test_app",
        user_id="test-user",
        session_id="test-session",
        state={"city": "New Delhi"}
    )
    
    agent_input_dict = {
        "city": "New Delhi",
        "ui_client_url": "http://localhost:8000",
        "operation": "find_leads"
    }
    user_message = f"Find potential business leads in New Delhi"
    
    adk_content = genai_types.Content(
        parts=[
            genai_types.Part(text=user_message),
            genai_types.Part(text=json.dumps(agent_input_dict))
        ]
    )
    
    try:
        async for event in runner.run_async(
            user_id="test-user",
            session_id="test-session",
            new_message=adk_content
        ):
            print("EVENT:", type(event).__name__, getattr(event, "content", getattr(event, "message", "")))
            if event.is_final_response():
                print("Final response:", getattr(event, "content", None))
                
        print("Agent finished.")
    except Exception as e:
        print("AGENT RUN ERROR:", type(e), e)
        traceback.print_exc()

asyncio.run(main())
