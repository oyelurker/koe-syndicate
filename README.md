# Koe Syndicate: Agentic Sales Engine

Koe Syndicate is a fully autonomous, AI-driven B2B Sales Automation engine. It is designed to emulate the entire workflow of a modern sales organization by chaining together specialized autonomous agents that handle lead generation, personalized outreach, phone calls, and email follow-ups.

## Architecture & Workflow

The engine is composed of three primary autonomous agents:

1. **Lead Finder Agent (`lead_finder`)**
   - Extracts hyper-targeted local business leads using Google Maps data based on natural language queries (e.g., "Software Engineering services in San Francisco").
   - Enriches lead data with names, websites, phone numbers, and addresses.

2. **Sales Development Representative (SDR) Agent (`sdr`)**
   - Operates as a voice-enabled AI salesperson.
   - Automatically researches the digital footprint of a given lead, formulates a personalized pitch, and executes a real phone call (powered by ElevenLabs).
   - After the call, it stores the results and transcripts into a centralized database.

3. **Lead Manager Agent (`lead_manager`) & Gmail Listener**
   - Monitors a dedicated sales inbox (via Google Cloud Pub/Sub and Gmail API).
   - Whenever a prospect replies via email, this agent qualifies the lead, analyzes the sentiment, and takes appropriate action (such as pushing the lead to a CRM or scheduling a follow-up).

4. **UI Dashboard (`ui_client`)**
   - A sleek, terminal-inspired Ops Console that monitors the live telemetry of all agents in real-time.
   - Built with FastAPI and WebSockets, allowing human oversight and manual override capabilities.

---

## Getting Started

### Prerequisites
- Python 3.10+
- Google Cloud Project with BigQuery enabled
- Gemini 2.0 API Key (For agent reasoning)
- ElevenLabs API Key (For voice calls)
- Serper API Key (For Google search enrichment)

### Installation

1. **Clone and Setup Virtual Environment:**
   ```bash
   python -m venv venv
   source venv/Scripts/activate  # Windows
   pip install -r requirements.txt
   ```

2. **Environment Variables:**
   Copy the `config.template` file to `.env` and fill in your API credentials.
   ```bash
   cp config.template .env
   ```

### Running the Services

You must launch each service in its own terminal window.

```bash
# Terminal 1: Lead Finder
python -m lead_finder --port 8081

# Terminal 2: Lead Manager
python -m lead_manager --port 8082

# Terminal 3: SDR Agent
python -m sdr --port 8084

# Terminal 4: UI Dashboard
python -m ui_client.main
```
*Navigate to `http://localhost:8000` to view the Ops Console.*

---

## 🧪 Demo & Testing Mode (IMPORTANT)

This project heavily utilizes the Gemini API. During intensive testing or presentations, you may exhaust your Free Tier API quota (resulting in `429 RESOURCE_EXHAUSTED` errors) or your ElevenLabs minutes.

To solve this, we built **Mock Testing Flags** into the `.env` file to bypass expensive LLM and Voice calls while keeping the UI fully functional. 

To enable Mock Mode, open your `.env` file and set:
```env
MOCK_LEAD_FINDER=true
MOCK_SDR=true
```
*(Remember to restart the `ui_client`, `lead_finder`, and `sdr` terminals after changing these flags!)*

### What Mock Mode Does:
1. **Lead Finder:** Instantly returns 2 hardcoded "Demo Leads" without using Google Maps API or Gemini.
2. **SDR Agent:** Fakes the digital footprint analysis and mimics a successful phone call directly in the dashboard telemetry without actually dialing your phone or using ElevenLabs.
3. **Lead Manager:** Re-routes the "Trigger Lead Manager" dashboard button to simulate an inbound email reply from a prospect ("Yes, we are interested...") so you can demonstrate the conversion flow without setting up real Gmail Pub/Sub routing.
4. **BigQuery Fallback:** If `GOOGLE_CLOUD_PROJECT` is not set, the SDR agent gracefully skips the database upload and saves the raw call data to a local `.json` file in the project directory instead of crashing.

This allows you to smoothly rehearse and present the entire Koe Syndicate UI pipeline to judges or stakeholders with zero risk of API failures!
