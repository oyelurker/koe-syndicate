# 🚀 KOE Syndicate: AI-Powered Decision Intelligence & Autonomous Agent Platform

![Status](https://img.shields.io/badge/Status-Hackathon_Ready-success?style=for-the-badge)
![Python](https://img.shields.io/badge/Python-3.11-blue?style=for-the-badge&logo=python)
![Gemini](https://img.shields.io/badge/Powered_by-Gemini_2.0_Flash-orange?style=for-the-badge&logo=google)
![NVIDIA](https://img.shields.io/badge/Accelerated_by-NVIDIA_GPUs-76B900?style=for-the-badge&logo=nvidia)

<video src="./UpdatedVideo_Submission_The%20Syndicates.mp4" controls="controls" playsinline muted="muted" width="100%">
  Your browser does not support the video tag.
</video>

**KOE Syndicate** is a practical Decision-Intelligence and Autonomous Multi-Agent platform designed to solve a massive bottleneck in **Local Economic Development and B2B Enterprise Operations**. 

It transforms raw, unstructured local community data into actionable intelligence, visualizes it on a live Ops Console, and uses a team of autonomous AI agents to execute workflows and outreach.

---

## 🎯 Hackathon Problem Statement Fit

This project heavily aligns with both **Decision Intelligence Platform** and **Autonomous Multi-Agent System** tracks by fulfilling the core hackathon requirements:

*   **Real-World User & Problem:** Designed for B2B sales teams, local economic development agencies, and enterprise operations who suffer from the massive bottleneck of manual data entry, lead qualification, and outreach.
*   **The Data Pipeline:**
    1. **Ingests:** Pulls raw structured/unstructured local business data via Google Maps.
    2. **Analyzes:** Uses LLMs to clean the data and analyze the business's digital footprint (e.g., *Do they have a website? Do they have good reviews?*).
    3. **Visualizes & Decides:** Pushes the insights to a real-time Kanban Dashboard (Ops Console) for human-in-the-loop decision support.
    4. **Automates:** Triggers specialized AI agents to autonomously execute phone calls and handle email replies.
*   **Google Cloud & NVIDIA Tech Stack:** 
    *   🧠 **Gemini Enterprise Agent Platform** (Gemini 2.0 Flash) for complex agent reasoning and natural language interaction.
    *   📊 **BigQuery** for scalable data storage of lead telemetry and call transcripts.
    *   ⚡ **NVIDIA RAPIDS (cuDF)**: We utilize `cudf.pandas` to zero-code accelerate our data analytics pipeline, processing thousands of lead intelligence records on NVIDIA GPUs up to 150x faster.
    *   ☁️ **Cloud Run & Pub/Sub** for microservice deployment and asynchronous agent communication.

---

## 🧠 Architecture: The Multi-Agent Network

Instead of one massive, confusing AI prompt, we engineered a collaborative network of highly specialized digital teammates:

### 1. Lead Finder Agent (`lead_finder`)
*   **Role:** The Data Ingestor.
*   **Action:** Extracts hyper-targeted local business leads based on natural language queries (e.g., *"Software Engineering services in San Francisco"*). Enriches lead data with names, websites, phone numbers, and addresses.

### 2. SDR Agent (`sdr`)
*   **Role:** The Caller.
*   **Action:** Operates as a voice-enabled AI salesperson. It reasons about a business's needs, formulates a personalized pitch using **Gemini 2.0 Flash**, and executes a real-time, human-like phone call (powered by ElevenLabs).

### 3. Lead Manager Agent (`lead_manager`)
*   **Role:** The Closer.
*   **Action:** Monitors a dedicated inbox via Pub/Sub. When a prospect replies, this agent wakes up, uses Gemini to qualify the lead, analyzes the sentiment, and schedules follow-ups.

### 4. UI Dashboard (`ui_client`)
*   **Role:** The Decision-Support Ops Console.
*   **Action:** A sleek, terminal-inspired dashboard that monitors the live telemetry of all agents in real-time. Built with FastAPI and WebSockets, it provides the crucial **Human-in-the-Loop oversight** required for enterprise AI adoption.

---

## 💻 Getting Started

### Prerequisites
- Python 3.10+
- Google Cloud Project (BigQuery & Pub/Sub enabled)
- Gemini API Key
- ElevenLabs API Key
- Serper API Key

### Installation & Execution

1. **Clone and Setup Virtual Environment:**
   ```bash
   git clone <your-repo-url>
   cd koe-syndicate
   python -m venv venv
   source venv/Scripts/activate  # On Windows
   pip install -r requirements.txt
   ```

2. **Environment Variables:**
   Copy the `.env.example` file to `.env` and fill in your API credentials.
   ```bash
   cp .env.example .env
   ```

3. **Run the Microservices:**
   You must launch each service in its own terminal window.
   ```bash
   python -m lead_finder --port 8081  # Terminal 1
   python -m lead_manager --port 8082 # Terminal 2
   python -m sdr --port 8084          # Terminal 3
   python -m ui_client.main           # Terminal 4
   ```
   *Navigate to `http://localhost:8000` to view the live Ops Console!*

---

## 🧪 Demo & Testing Mode

To ensure smooth demonstrations without exhausting API quotas or requiring heavy Google Cloud billing setups during the hackathon, we built a **Mock Testing Mode**.

To enable it, open your `.env` file and set:
```env
MOCK_LEAD_FINDER=true
MOCK_SDR=true
```

### What Mock Mode Does:
1. **Lead Finder:** Bypasses the Maps API and instantly injects Demo Leads into the data pipeline.
2. **SDR Agent:** Simulates the digital footprint analysis and mimics a successful phone call directly in the dashboard telemetry.
3. **Lead Manager:** Instead of requiring a complex Gmail Pub/Sub integration to test email replies, you can simply run `python trigger_conversion.py` in a new terminal. This script mimics a prospect replying to an email, and you will see the UI immediately react and update the data visualization.
4. **Database Fallback:** If GCP billing is disabled, the system gracefully skips BigQuery upload and saves the raw data pipeline output to a local `.json` file instead of crashing.

---

## 🏎️ NVIDIA RAPIDS Data Analytics

As part of our data pipeline, we built an analytics module that processes large datasets of lead telemetry. To ensure lightning-fast processing at scale, this module is designed to be accelerated by **NVIDIA RAPIDS (cuDF)**.

To run the data analytics on an NVIDIA GPU using zero-code pandas acceleration:
```bash
# This will automatically run pandas operations on the NVIDIA GPU
python -m cudf.pandas analytics_acceleration.py --file demo_leads.json
```

This guarantees a flawless demonstration of the KOE Syndicate architecture!
