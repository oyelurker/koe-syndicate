import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from lead_finder.lead_finder.agent import lead_finder_agent
from google.adk.sessions import Session

# Set dummy API keys if not present
os.environ['GOOGLE_API_KEY'] = 'dummy' if 'GOOGLE_API_KEY' not in os.environ else os.environ['GOOGLE_API_KEY']

async def main():
    print('Starting manual agent test...')
    session = Session(state={"city": "New Delhi"})
    try:
        res = await lead_finder_agent.run_async("Find leads", session=session)
        print("AGENT RUN SUCCESS")
        print("Session final state:", session.state.keys())
        if "final_merged_leads" in session.state:
            print("final_merged_leads:")
            print(session.state["final_merged_leads"])
        else:
            print("NO final_merged_leads in state!")
    except Exception as e:
        print("AGENT RUN ERROR:", e)

asyncio.run(main())
