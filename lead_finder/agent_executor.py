from common.security import agent_session_identity
import re
from common.security import service_url
import json
import logging
from typing import Any
from datetime import datetime
from pathlib import Path

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.events import EventQueue
from a2a.server.tasks import TaskUpdater
from a2a.types import DataPart, Part, TaskState

# Make sure you have a shared config for the artifact name
from common.config import DEFAULT_LEAD_FINDER_ARTIFACT_NAME, DEFAULT_UI_CLIENT_URL
from google.adk import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types as genai_types

from .lead_finder.agent import lead_finder_agent

logger = logging.getLogger(__name__)

# Initialize logging to file
root_path = Path.cwd()
log_file = root_path / "lead_finder/lead_finder_agent.log"
def log_to_file(message: str):
    """Sensitive agent payloads are not written to ad-hoc files."""
    return None

# Clear previous logs and start fresh for this call

class LeadFinderAgentExecutor(AgentExecutor):
    """Executes the Lead Finder ADK agent logic in response to A2A requests."""

    def __init__(self):
        self._adk_agent = lead_finder_agent
        self._adk_runner = Runner(
            app_name="lead_finder_adk_runner",
            agent=self._adk_agent,
            artifact_service=InMemoryArtifactService(),
            session_service=InMemorySessionService(),
        )
        logger.info("LeadFinderAgentExecutor initialized with ADK Runner.")

    async def execute(self, context: RequestContext, event_queue: EventQueue):
        owner_id_for_adk, scoped_session_id = agent_session_identity(context.context_id, context.task_id)
        task_updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        
        logger.info("Received Lead Finder request")

        if not context.current_task:
            task_updater.submit(message=context.message)

        task_updater.start_work(
            message=task_updater.new_agent_message(
                parts=[
                    Part(root=DataPart(data={"status": "Processing city search request..."}))
                ]
            )
        )

        # Extract city from context.message - IMPROVED EXTRACTION
        city_name: str | None = None
        niche_name: str | None = None
        ui_client_url = service_url("ui-client")

        if context.message and context.message.parts:
            for part_union in context.message.parts:
                part = part_union.root
                if isinstance(part, DataPart):
                    # Try multiple keys for city
                    if "city" in part.data:
                        city_name = part.data["city"]
                    elif "query" in part.data:
                        city_name = part.data["query"]  # Assuming query contains city
                    elif "search_query" in part.data:
                        city_name = part.data["search_query"]
                        
                    if "niche" in part.data:
                        niche_name = part.data["niche"]
                    

        if city_name is None:
            logger.error(f"Task {context.task_id}: Missing city name in input")
            task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[
                        Part(
                            root=DataPart(
                                data={"error": "Invalid input: Missing city name"}
                            )
                        )
                    ]
                )
            )
            return

        # Prepare input for ADK Agent with clear structure
        agent_input_dict = {
            "city": city_name,
            "ui_client_url": ui_client_url,
            "operation": "find_leads"
        }
        
        # Create a clear user message for the agent
        user_message = f"Find potential business leads in {city_name}"
        
        # Create both text and structured data
        adk_content = genai_types.Content(
            parts=[
                genai_types.Part(text=user_message),
                genai_types.Part(text=json.dumps(agent_input_dict))
            ]
        )

        # [Rest of the session handling code remains the same...]
        session_id_for_adk = scoped_session_id
        logger.info(f"Task {context.task_id}: Using ADK session_id: '{session_id_for_adk}' for city: '{city_name}'")

        session: Session | None = None
        if session_id_for_adk:
            try:
                session = await self._adk_runner.session_service.get_session(
                    app_name=self._adk_runner.app_name,
                    user_id=owner_id_for_adk,
                    session_id=session_id_for_adk,
                )
            except Exception as e:
                logger.exception(f"Task {context.task_id}: Exception during get_session: {e}")
                session = None

            if not session:
                logger.info(f"Task {context.task_id}: Creating new ADK session for city: {city_name}")
                try:
                    session = await self._adk_runner.session_service.create_session(
                        app_name=self._adk_runner.app_name,
                        user_id=owner_id_for_adk,
                        session_id=session_id_for_adk,
                        state={"city": city_name},  # Store city in session state
                    )
                    if session:
                        logger.info(f"Task {context.task_id}: Successfully created ADK session with city: {city_name}")
                except Exception as e:
                    logger.exception(f"Task {context.task_id}: Exception during create_session: {e}")
                    session = None

        if not session:
            error_message = f"Failed to establish ADK session for city '{city_name}', continuing with bypass..."
            logger.error(f"Task {context.task_id}: {error_message}")
            # Do not return here so we can still use the hackathon bypass

        # Execute the ADK Agent (HACKATHON BYPASS)
        try:
            logger.info(f"Task {context.task_id}: Bypassing ADK due to rate limits for city: {city_name}")
            
            from .lead_finder.tools.maps_search import google_maps_search
            
            # Direct call to Maps API to bypass Gemini AI rate limits
            maps_results = google_maps_search(city=city_name, business_type=niche_name, max_results=10)
            
            businesses = maps_results.get("results", [])
            final_result = {
                "status": "completed", 
                "city": city_name, 
                "businesses": businesses,
                "count": len(businesses)
            }
            
            task_updater.add_artifact(
                parts=[Part(root=DataPart(data=final_result))],
                name=DEFAULT_LEAD_FINDER_ARTIFACT_NAME,
            )
            task_updater.complete()

        except Exception as e:
            logger.exception(f"Task {context.task_id}: Error running Lead Finder ADK agent for city {city_name}: {e}")
            task_updater.failed(
                message=task_updater.new_agent_message(
                    parts=[Part(root=DataPart(data={"error": f"ADK Agent error: {e}"}))]
                )
            )

    async def cancel(self, context: RequestContext, event_queue: EventQueue):
        logger.warning(f"Cancellation not implemented for Lead Finder task: {context.task_id}")
        task_updater = TaskUpdater(event_queue, context.task_id, context.context_id)
        task_updater.failed(
            message=task_updater.new_agent_message(
                parts=[Part(root=DataPart(data={"error": "Task cancelled"}))]
            )
        )
