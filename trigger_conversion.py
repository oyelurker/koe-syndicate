import httpx
import json
from datetime import datetime

UI_CLIENT_URL = "http://localhost:8000/agent_callback"

def trigger_hot_lead():
    payload = {
        "agent_type": "lead_manager",
        "business_id": "test_hot_lead_123",
        "status": "converting",
        "message": "Hot lead email from prospect@example.com",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "name": "Acme Corp (Converting)",
            "sender_email": "prospect@example.com",
            "sender_name": "John Prospect",
            "subject": "Interested in your services",
            "body_preview": "Hi, we saw your email and would like to learn more...",
            "received_date": datetime.now().isoformat(),
            "message_id": "msg_123",
            "type": "hot_lead_email"
        }
    }
    
    print(f"Sending hot lead (CONVERTING) to UI...")
    response = httpx.post(UI_CLIENT_URL, json=payload)
    print(f"Response: {response.status_code}")

def trigger_meeting():
    payload = {
        "agent_type": "calendar",
        "business_id": "test_meeting_456",
        "status": "meeting_scheduled",
        "message": "Incoming meeting with ceo@bigcompany.com",
        "timestamp": datetime.now().isoformat(),
        "data": {
            "name": "BigCompany (Meeting Scheduled)",
            "sender_email": "ceo@bigcompany.com",
            "business_id": "test_meeting_456"
        }
    }
    
    print(f"Sending calendar meeting (SECURED MEETINGS) to UI...")
    response = httpx.post(UI_CLIENT_URL, json=payload)
    print(f"Response: {response.status_code}")

if __name__ == "__main__":
    trigger_hot_lead()
    trigger_meeting()
    print("Check your UI dashboard now!")
