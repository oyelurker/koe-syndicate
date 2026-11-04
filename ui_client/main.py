"""
FastAPI application for the Koe Syndicate UI Client.

Provides a web interface to manage sales agent workflows including lead finding,
SDR engagement, lead management, and calendar scheduling. Features real-time
updates via WebSocket and A2A integration with sales agents.
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv



# Google OAuth imports
import google.oauth2.credentials
from googleapiclient.discovery import build

load_dotenv()

from . import db

# ── NVIDIA RAPIDS Lead Scoring ────────────────────────────────────────────────
# Import the GPU-accelerated (or sklearn fallback) scoring engine.
# score_leads() uses cuML Random Forest if NVIDIA RAPIDS is available.
try:
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from lead_scoring_ml import score_leads as _rapids_score_leads
    RAPIDS_SCORING_AVAILABLE = True
except Exception as _rapids_err:
    RAPIDS_SCORING_AVAILABLE = False
    _rapids_score_leads = None
    logging.getLogger("UIClient").warning(f"RAPIDS scoring unavailable: {_rapids_err}")

# Common project imports
import common.config as config
import httpx
from pydantic import BaseModel, Field, ValidationError

from fastapi import Depends, FastAPI, Form, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware

UI_CLIENT_LOGGER = "UIClient"
BUSINESS_LOGIC_LOGGER = "BusinessLogic"

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(UI_CLIENT_LOGGER)

# A2A SDK Imports (optional - fallback to simple HTTP if not available)
try:
    from a2a.client import A2AClient, A2AClientHTTPError, A2AClientJSONError
    from a2a.types import DataPart as A2ADataPart
    from a2a.types import JSONRPCErrorResponse
    from a2a.types import SendMessageSuccessResponse
    from a2a.types import Message as A2AMessage
    from a2a.types import MessageSendConfiguration, MessageSendParams
    from a2a.types import Role as A2ARole
    from a2a.types import SendMessageRequest, SendMessageResponse
    from a2a.types import Task as A2ATask
    A2A_AVAILABLE = True
except ImportError:
    logger.warning("A2A dependencies not found, falling back to simple HTTP client")
    A2A_AVAILABLE = False

# Ensure imports work
try:
    import common.config
except ImportError as e:
    logger.error(f"Failed to import necessary application modules: {e}")
    logger.error("Ensure you run uvicorn from the project root directory.")
    logger.error("Example: uvicorn ui_client.main:app --reload --port 8000")
    sys.exit(1)

module_dir = Path(__file__).parent
templates_dir = module_dir / "templates"
static_dir = module_dir / "static"

# Ensure static directory exists (for Cloud Run)
if not static_dir.exists():
    logger.warning(f"Static directory not found at {static_dir}, searching alternative paths...")
    # Try alternative paths for Cloud Run deployment
    alternative_paths = [
        Path("/app/koe_syndicate/ui_client/static"),
        Path("/app/ui_client/static"),
        module_dir.parent / "ui_client" / "static"
    ]
    for alt_path in alternative_paths:
        if alt_path.exists():
            static_dir = alt_path
            logger.info(f"Found static directory at {static_dir}")
            break
    else:
        logger.error(f"Static directory not found in any expected location. Checked: {[str(p) for p in [static_dir] + alternative_paths]}")

logger.info(f"Using static directory: {static_dir}")
logger.info(f"Using templates directory: {templates_dir}")

# Business Status Enums
class BusinessStatus(str, Enum):
    FOUND = "found"
    CONTACTED = "contacted"
    ENGAGED = "engaged"
    NOT_INTERESTED = "not_interested"
    NO_RESPONSE = "no_response"
    CONVERTING = "converting"
    MEETING_SCHEDULED = "meeting_scheduled"

class AgentType(str, Enum):
    LEAD_FINDER = "lead_finder"
    SDR = "sdr"
    LEAD_MANAGER = "lead_manager"
    CALENDAR = "calendar"

# Data Models
class Business(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    description: Optional[str] = None
    city: str
    status: BusinessStatus = BusinessStatus.FOUND
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    notes: List[str] = Field(default_factory=list)

class AgentUpdate(BaseModel):
    agent_type: AgentType
    business_id: str
    status: BusinessStatus
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Optional[dict[str, Any]] = None

class LeadFinderRequest(BaseModel):
    city: str = Field(..., min_length=1, max_length=100, description="Target city for lead finding")
    niche: Optional[str] = Field(None, description="Target business niche or type")

class HumanInputRequest(BaseModel):
    job_id: str | None = None
    campaign_id: str | None = None
    request_id: str
    prompt: str
    type: str
    timestamp: str

class HumanInputResponse(BaseModel):
    campaign_id: str = Field(..., min_length=1, max_length=128)
    request_id: str
    response: str

# Local runtime cache. Durable records remain scoped by their explicit owner.
def empty_pipeline_state():
    return {
        "is_running": False,
        "current_city": None,
        "businesses": {},
        "agent_updates": [],
        "websocket_connections": set(),
        "session_id": None,
        "human_input_requests": {},
        "lead_scores": {},
    }


from .runtime import OwnerRuntime, runtime_owner, PipelineRuntimeMiddleware

app_state = OwnerRuntime(empty_pipeline_state)

# Session Signer
from common.security import ServiceAuth, SecurityError, require_action, mode, campaign_context
from .security import BrowserSecurityMiddleware, validate_config
from .store import Store, StoreConflict
from . import db as token_db
from common.security import Execution, execution, owner_email
from common.execution_store import WorkStore, PolicyDenied

pipeline_store: Store | None = None
runtime_worker_id: str | None = None


def pipeline_snapshot():
    def encode(value):
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, Enum):
            return value.value
        raise TypeError("Pipeline state must be JSON serializable")
    return json.loads(json.dumps({k: v for k, v in app_state.items() if k != "websocket_connections"}, default=encode))


def restore_pipeline(snapshot):
    app_state.update(snapshot)
    app_state["businesses"] = {key: Business.model_validate(value) for key, value in snapshot.get("businesses", {}).items()}
    app_state["agent_updates"] = [AgentUpdate.model_validate(value) for value in snapshot.get("agent_updates", [])]
    app_state["human_input_requests"] = {key: HumanInputRequest.model_validate(value)
        for key, value in snapshot.get("human_input_requests", {}).items()
        if snapshot.get("session_id") and value.get("campaign_id") == snapshot["session_id"]}


def campaign_is_current(campaign_id):
    context = execution.get()
    view = app_state.current_view() if context else None
    return bool(context and not (view and view.conflicted) and campaign_id and app_state["session_id"] == campaign_id)


def require_current_campaign():
    context = execution.get()
    if not context or not campaign_is_current(context.campaign_id):
        raise SecurityError("Campaign is missing, reset or superseded")
    if context.job_id:
        WorkStore().require_job()


@asynccontextmanager
async def pipeline_scope():
    if pipeline_store is None:
        raise RuntimeError("Persistent storage has not completed application startup")
    committed = await asyncio.to_thread(pipeline_store.read_view, runtime_owner())
    token = app_state.bind(committed["revision"])
    try:
        if committed["snapshot"]:
            restore_pipeline(committed["snapshot"])
        view = app_state.current_view()
        view.cursor = committed["cursor"]
        view.baseline = pipeline_snapshot()
        yield view
    finally:
        view = app_state.current_view()
        if view.baseline is not None and pipeline_snapshot() == view.baseline:
            app_state.cache_current()
        app_state.unbind(token)


async def persist_pipeline(event, dispatch=None):
    context = execution.get()
    if context is None:
        raise SecurityError("Missing owner for persistent pipeline update")
    view = app_state.current_view()
    if view is None or view.conflicted:
        raise StoreConflict("A fresh pipeline view is required")
    if context.campaign_id:
        require_current_campaign()
    if pipeline_store is None:
        raise RuntimeError("Persistent storage has not completed application startup")
    snapshot = pipeline_snapshot()
    try:
        result = await asyncio.to_thread(pipeline_store.save, context.owner, snapshot,
            json.loads(json.dumps(event, default=str)), expected_revision=view.revision, worker_id=runtime_worker_id, dispatch=dispatch)
    except StoreConflict:
        # Discard this operation's speculative state and stop its later callbacks/finalizers.
        view.conflicted = True
        raise
    view.revision = result["revision"]
    view.baseline = snapshot
    return result


async def flush_pipeline():
    view = app_state.current_view()
    if view and not view.conflicted and pipeline_snapshot() != view.baseline:
        await persist_pipeline({"type": "state_changed"})


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""
    
    def __init__(self, persist=None, durable_delivery=False):
        self.active_connections: dict[WebSocket, str] = {}
        self.persist = persist
        self.durable_delivery = durable_delivery
    
    async def connect(self, websocket: WebSocket):
        owner = runtime_owner()
        await websocket.accept()
        self.active_connections[websocket] = owner
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.pop(websocket, None)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_update(self, data: dict[str, Any], dispatch=None):
        """Persist and publish only within the verified owner's current view."""
        owner = runtime_owner()
        if self.durable_delivery and app_state.current_view() is None:
            async with pipeline_scope():
                return await self.send_update(data, dispatch=dispatch)
        context = execution.get()
        campaign = context.campaign_id or app_state["session_id"]
        if context.campaign_id:
            require_current_campaign()
        if self.persist is not None:
            if dispatch is None:
                await self.persist(data)
            else:
                await self.persist(data, dispatch=dispatch)
        if self.durable_delivery:
            return
        envelope = {**data, "campaign_id": campaign}
        message = json.dumps(envelope, default=str)
        # Snapshot membership: a disconnect/connect may happen while sending.
        for connection, connection_owner in list(self.active_connections.items()):
            if connection_owner != owner:
                continue
            # Recheck after every await; reset/new search invalidates old events.
            if app_state["session_id"] != campaign:
                return
            if self.active_connections.get(connection) != owner:
                continue
            try:
                await connection.send_text(message)
            except Exception:
                logger.warning("WebSocket delivery failed; disconnecting client")
                self.disconnect(connection)

manager = ConnectionManager(persist=persist_pipeline, durable_delivery=True)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Handles application startup and shutdown events."""
    global pipeline_store, runtime_worker_id
    validate_config()
    logger.info("UI Client starting up...")
    
    # Initialize SQLite database
    await db.init_db()
    store = Store(token_db.DB_PATH)
    runtime_worker_id = str(uuid.uuid4())
    await asyncio.to_thread(store.heartbeat, runtime_worker_id)
    token = execution.set(Execution(owner_email(), mode()))
    try:
        app_state.clear_all()
        manager.active_connections.clear()
        app_state.update(empty_pipeline_state())
        await asyncio.to_thread(store.interrupt_incomplete, owner_email())
        restored = await asyncio.to_thread(store.read_view, owner_email())
        if restored["snapshot"]:
            restore_pipeline(restored["snapshot"])
        app_state._revisions[runtime_owner()] = restored["revision"]
        pipeline_store = store
        logger.info("Database initialized successfully.")

        # ── NVIDIA RAPIDS: Pre-score demo leads at startup ────────────────────────
        if RAPIDS_SCORING_AVAILABLE and not app_state["lead_scores"]:
            try:
                _demo_path = Path(__file__).parent.parent / "demo_leads.json"
                if _demo_path.exists():
                    with open(_demo_path, "r") as _f:
                        _demo_leads = json.load(_f)
                    app_state["lead_scores"] = _rapids_score_leads(_demo_leads)
                    logger.info(f"[RAPIDS] Scored {len(app_state['lead_scores'])} leads at startup.")
                else:
                    logger.warning("[RAPIDS] demo_leads.json not found — scores unavailable until leads are generated.")
            except Exception as _e:
                logger.warning(f"[RAPIDS] Startup scoring failed: {_e}")
        elif not RAPIDS_SCORING_AVAILABLE:
            logger.warning("[RAPIDS] Scoring engine not loaded — /api/lead-scores will return empty.")
        if pipeline_snapshot() != (restored["snapshot"] or empty_pipeline_state()) and app_state["lead_scores"]:
            try:
                initialized = await asyncio.to_thread(store.save, owner_email(), pipeline_snapshot(),
                    {"type": "scores_initialized"}, expected_revision=restored["revision"], worker_id=runtime_worker_id)
                app_state._revisions[runtime_owner()] = initialized["revision"]
            except StoreConflict:
                latest = await asyncio.to_thread(store.read_view, owner_email())
                app_state.clear()
                app_state.update(empty_pipeline_state())
                if latest["snapshot"]:
                    restore_pipeline(latest["snapshot"])

    finally:
        execution.reset(token)

    async def renew_worker():
        while True:
            await asyncio.sleep(20)
            try:
                await asyncio.to_thread(store.heartbeat, runtime_worker_id)
                await asyncio.to_thread(store.interrupt_incomplete, owner_email())
            except Exception:
                logger.error("Worker lease renewal failed; expired leases deny further writes")
    heartbeat_task = asyncio.create_task(renew_worker())
    dispatcher_task = asyncio.create_task(dispatch_loop())
    try:
        yield
    finally:
        dispatcher_task.cancel()
        with suppress(asyncio.CancelledError):
            await dispatcher_task
        heartbeat_task.cancel()
        with suppress(asyncio.CancelledError):
            await heartbeat_task
        await asyncio.to_thread(store.release_worker, runtime_worker_id)
        runtime_worker_id = None
        pipeline_store = None
        app_state.clear_all()
        manager.active_connections.clear()
        logger.info("UI Client shutting down...")

app = FastAPI(lifespan=lifespan, debug=False, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(PipelineRuntimeMiddleware, scope_factory=pipeline_scope, flush=flush_pipeline)
app.add_middleware(BrowserSecurityMiddleware)

# Add CORS Middleware to allow requests from the frontend with cookies
app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000")],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory=str(templates_dir))

# Mount static files with additional logging
logger.info(f"Mounting static files from {static_dir} to /static")
try:
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
    logger.info("Static files mounted successfully")
except Exception as e:
    logger.error(f"Failed to mount static files: {e}")
    # Try to create a minimal static mount as fallback
    try:
        from fastapi.responses import FileResponse
        logger.warning("Creating fallback static file handler")
    except Exception as fallback_error:
        logger.error(f"Fallback static handler also failed: {fallback_error}")

def format_currency(value: Optional[float]) -> str:
    """Formats an optional float value as currency."""
    if value is None:
        return "N/A"
    return f"${value:,.2f}"

def format_datetime(dt: datetime) -> str:
    """Formats datetime for display."""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

# Add custom filters to templates
templates.env.filters["format_currency"] = format_currency
templates.env.filters["format_datetime"] = format_datetime


# ── NVIDIA RAPIDS: Lead Scores API ──────────────────────────────────────────
# These endpoints expose the GPU-computed lead scores to the Next.js dashboard.

from fastapi import APIRouter
rapids_router = APIRouter(prefix="/api", tags=["RAPIDS"])

@rapids_router.get("/lead-scores")
async def get_lead_scores():
    """
    Returns NVIDIA RAPIDS (cuML) predictive conversion scores for all known leads.
    Scores are computed at startup using a GPU-accelerated Random Forest classifier.
    Falls back to sklearn on CPU if RAPIDS is not available.
    """
    return {
        "scores": app_state.get("lead_scores", {}),
        "engine": "nvidia-cuml" if (RAPIDS_SCORING_AVAILABLE and HAS_CUML_GLOBAL) else "sklearn-cpu" if RAPIDS_SCORING_AVAILABLE else "unavailable",
        "count": len(app_state.get("lead_scores", {})),
    }

@rapids_router.post("/rescore")
async def rescore_leads():
    """
    Re-runs the NVIDIA RAPIDS scoring engine on the current pipeline businesses
    and updates the cached scores. Useful after new leads are added.
    """
    if not RAPIDS_SCORING_AVAILABLE:
        return JSONResponse(status_code=503, content={"error": "RAPIDS scoring engine not available."})

    try:
        leads = [
            {"name": b.name, "city": b.city, "rating": 4.0, "industry": "General"}
            for b in app_state["businesses"].values()
        ]
        if not leads:
            # Fall back to demo_leads.json
            _demo_path = Path(__file__).parent.parent / "demo_leads.json"
            if _demo_path.exists():
                with open(_demo_path, "r") as f:
                    leads = json.load(f)

        app_state["lead_scores"] = _rapids_score_leads(leads)
        return {"status": "ok", "scored": len(app_state["lead_scores"]), "scores": app_state["lead_scores"]}
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})

# Check if cuML was actually loaded (for the engine label)
try:
    import cuml as _cuml_check
    HAS_CUML_GLOBAL = True
except ImportError:
    HAS_CUML_GLOBAL = False

app.include_router(rapids_router)
# ── End RAPIDS API ────────────────────────────────────────────────────────────

from .auth_routes import router as auth_router
from .calendar_routes import router as calendar_router
app.include_router(auth_router)
app.include_router(calendar_router)
from .execution_routes import router as execution_router
app.include_router(execution_router)

async def call_lead_finder_agent_a2a(city: str, session_id: str, **kwargs) -> dict[str, Any]:
    """
    Calls the Lead Finder agent via A2A to find businesses in the specified city.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    lead_finder_url = os.environ.get(
        "LEAD_FINDER_SERVICE_URL", config.DEFAULT_LEAD_FINDER_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling Lead Finder at {lead_finder_url} for city: {city}")
    
    outcome = {
        "success": False,
        "businesses": [],
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(auth=ServiceAuth("ui-client", "lead-finder", campaign_context(session_id)), ) as http_client:
            a2a_client = A2AClient(httpx_client=http_client, url=lead_finder_url)
            
            # Prepare A2A message
            a2a_task_id = f"lead-search-{session_id}"
            
            search_data = {
                "city": city,
                "niche": kwargs.get("niche", ""),
            }
            
            sdk_message = A2AMessage(
                taskId=a2a_task_id,
                contextId=session_id,
                messageId=str(uuid.uuid4()),
                role=A2ARole.user,
                parts=[A2ADataPart(data=search_data)],
                metadata={"operation": "find_leads", "city": city, "niche": kwargs.get("niche", "")},
            )
            
            sdk_send_params = MessageSendParams(
                message=sdk_message,
                configuration=MessageSendConfiguration(
                    acceptedOutputModes=["data", "application/json"]
                ),
            )
            
            sdk_request = SendMessageRequest(
                id=str(uuid.uuid4()), params=sdk_send_params
            )
            
            # Send request to Lead Finder
            response: SendMessageResponse = await a2a_client.send_message(sdk_request)
            root_response_part = response.root
            
            if isinstance(root_response_part, JSONRPCErrorResponse):
                actual_error = root_response_part.error
                business_logger.error(
                    f"A2A Error from Lead Finder: {actual_error.code} - {actual_error.message}"
                )
                outcome["error"] = f"A2A Error: {actual_error.code} - {actual_error.message}"
                
            elif isinstance(root_response_part, SendMessageSuccessResponse):
                task_result: A2ATask = root_response_part.result
                business_logger.info(
                    f"Lead Finder task {task_result.id} completed with state: {task_result.status.state}"
                )
                
                # Check if the task failed
                if hasattr(task_result.status.state, 'value'):
                    is_failed = task_result.status.state.value.upper() == "FAILED"
                else:
                    is_failed = str(task_result.status.state).upper() == "FAILED"
                
                if is_failed:
                    business_logger.error(f"Lead Finder task {task_result.id} FAILED.")
                    outcome["success"] = False
                    
                    # Try to get error from parts if available
                    outcome["error"] = "Agent task failed internally"
                    try:
                        if hasattr(task_result.status, "message") and task_result.status.message and hasattr(task_result.status.message, "parts") and task_result.status.message.parts:
                            part_root = task_result.status.message.parts[0].root
                            if isinstance(part_root, A2ADataPart) and isinstance(part_root.data, dict) and "error" in part_root.data:
                                outcome["error"] = part_root.data["error"]
                    except Exception as err:
                        business_logger.warning(f"Could not parse error details: {err}")
                        
                # Extract business data from artifacts
                elif task_result.artifacts:
                    lead_results_artifact = next(
                        (
                            a
                            for a in task_result.artifacts
                            if a.name == config.DEFAULT_LEAD_FINDER_ARTIFACT_NAME
                        ),
                        None,
                    )
                    
                    if lead_results_artifact and lead_results_artifact.parts:
                        art_part_root = lead_results_artifact.parts[0].root
                        if isinstance(art_part_root, A2ADataPart):
                            result_data = art_part_root.data
                            logger.debug("Sensitive payload omitted")
                            
                            if isinstance(result_data, dict) and "businesses" in result_data:
                                outcome["success"] = True
                                outcome["businesses"] = result_data["businesses"]
                            else:
                                business_logger.warning("Unexpected lead results format")
                                outcome["error"] = "Invalid lead results format"
                        else:
                            business_logger.warning(f"Unexpected artifact part type: {type(art_part_root)}")
                    else:
                        business_logger.info("Lead results artifact not found or empty - checking for empty results")
                        # Don't set this as an error immediately, let the success flow handle empty results
                        outcome["success"] = True
                        outcome["businesses"] = []
                else:
                    business_logger.info("No artifacts found in Lead Finder response - treating as empty results")
                    outcome["success"] = True
                    outcome["businesses"] = []
            else:
                business_logger.error(f"Invalid A2A response type: {type(root_response_part)}")
                outcome["error"] = "Invalid response type"
                
    except Exception as e:
        if A2A_AVAILABLE and 'A2AClientHTTPError' in str(type(e)):
            business_logger.error(f"HTTP Error calling Lead Finder: {e}")
            outcome["error"] = f"Connection Error: {e}"
        elif A2A_AVAILABLE and 'A2AClientJSONError' in str(type(e)):
            business_logger.error(f"JSON Error from Lead Finder: {e}")
            outcome["error"] = f"JSON Response Error: {e}"
        else:
            business_logger.error(f"Unexpected error calling Lead Finder: {e}", exc_info=True)
            outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_lead_finder_agent_simple(city: str, session_id: str, **kwargs) -> dict[str, Any]:
    """
    Calls the Lead Finder service via simple HTTP POST when A2A is not available.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    lead_finder_url = os.environ.get(
        "LEAD_FINDER_SERVICE_URL", config.DEFAULT_LEAD_FINDER_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling Lead Finder (simple HTTP) at {lead_finder_url} for city: {city}")
    
    outcome = {
        "success": False,
        "businesses": [],
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(auth=ServiceAuth("ui-client", "lead-finder", campaign_context(session_id)), timeout=300.0) as client:
            # Try different endpoints that might exist
            endpoints_to_try = [
                f"{lead_finder_url}/find_leads",
                f"{lead_finder_url}/search",
                f"{lead_finder_url}/",
            ]
            
            search_data = {
                "city": city,
                "max_results": 50,
                "session_id": session_id,
                "niche": kwargs.get("niche", ""),
            }
            
            for endpoint in endpoints_to_try:
                try:
                    business_logger.info(f"Trying endpoint: {endpoint}")
                    response = await client.post(endpoint, json=search_data)
                    
                    if response.status_code == 200:
                        result_data = response.json()
                        logger.debug("Sensitive payload omitted")
                        
                        # Handle different response formats
                        if isinstance(result_data, dict):
                            if "businesses" in result_data:
                                outcome["success"] = True
                                outcome["businesses"] = result_data["businesses"]
                                break
                            elif "results" in result_data:
                                outcome["success"] = True
                                outcome["businesses"] = result_data["results"]
                                break
                            elif "data" in result_data:
                                outcome["success"] = True
                                outcome["businesses"] = result_data["data"]
                                break
                        elif isinstance(result_data, list):
                            outcome["success"] = True
                            outcome["businesses"] = result_data
                            break
                    
                    business_logger.warning(f"Endpoint {endpoint} returned status {response.status_code}")
                    
                except Exception as e:
                    business_logger.warning(f"Endpoint {endpoint} failed: {e}")
                    continue
            
            if not outcome["success"]:
                outcome["error"] = "All Lead Finder endpoints failed or returned no data"
                
    except Exception as e:
        business_logger.error(f"Unexpected error calling Lead Finder: {e}", exc_info=True)
        outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_lead_finder_agent(city: str, session_id: str, **kwargs) -> dict[str, Any]:
    """
    Calls the Lead Finder agent - uses A2A if available, otherwise falls back to simple HTTP.
    """
    import os, uuid, asyncio
    if mode() == "demo":
        logging.getLogger("UI_CLIENT").info(f"Using MOCK leads for {city} to save API credits.")
        await asyncio.sleep(2)  # Simulate agent thinking time
        return {
            "success": True,
            "businesses": [
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "koe-demo:"+city+":alpha")),
                    "name": f"Demo Lead Alpha - {city}",
                    "phone": "+1-555-0101",
                    "email": "contact@demoleadalpha.com",
                    "description": "A promising mock lead for testing purposes without using API credits.",
                    "city": city,
                    "status": "found",
                    "notes": ["Generated via Mock Mode"]
                },
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, "koe-demo:"+city+":beta")),
                    "name": f"Demo Lead Beta - {city}",
                    "phone": "+1-555-0102",
                    "email": "hello@demoleadbeta.com",
                    "description": "Another mock lead generated to save Gemini credits during testing.",
                    "city": city,
                    "status": "found",
                    "notes": ["Generated via Mock Mode"]
                }
            ],
            "error": None
        }

    if A2A_AVAILABLE:
        return await call_lead_finder_agent_a2a(city, session_id, **kwargs)
    else:
        return await call_lead_finder_agent_simple(city, session_id, **kwargs)

async def call_sdr_agent_a2a(business_data: dict[str, Any], session_id: str) -> dict[str, Any]:
    """
    Calls the SDR agent via A2A to process a business lead.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    sdr_url = os.environ.get(
        "SDR_SERVICE_URL", config.DEFAULT_SDR_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling SDR agent at {sdr_url} for business: {business_data.get('name', 'Unknown')}")
    
    outcome = {
        "success": False,
        "message": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(auth=ServiceAuth("ui-client", "sdr", campaign_context(session_id)), timeout=300.0) as http_client:
            a2a_client = A2AClient(httpx_client=http_client, url=sdr_url)
            
            # Prepare A2A message
            a2a_task_id = f"sdr-engagement-{session_id}-{business_data.get('id', 'unknown')}"
            
            sdk_message = A2AMessage(
                taskId=a2a_task_id,
                contextId=session_id,
                messageId=str(uuid.uuid4()),
                role=A2ARole.user,
                parts=[A2ADataPart(data=business_data)],
                metadata={"operation": "engage_lead", "business_id": business_data.get("id")},
            )
            
            sdk_send_params = MessageSendParams(
                message=sdk_message,
                configuration=MessageSendConfiguration(
                    acceptedOutputModes=["data", "application/json"]
                ),
            )
            
            sdk_request = SendMessageRequest(
                id=str(uuid.uuid4()), params=sdk_send_params
            )
            
            # Send request to SDR agent
            response: SendMessageResponse = await a2a_client.send_message(sdk_request)
            root_response_part = response.root
            
            if isinstance(root_response_part, JSONRPCErrorResponse):
                actual_error = root_response_part.error
                business_logger.error(
                    f"A2A Error from SDR agent: {actual_error.code} - {actual_error.message}"
                )
                outcome["error"] = f"A2A Error: {actual_error.code} - {actual_error.message}"
                
            elif isinstance(root_response_part, SendMessageSuccessResponse):
                task_result: A2ATask = root_response_part.result
                business_logger.info(
                    f"SDR agent task {task_result.id} completed with state: {task_result.status.state}"
                )
                
                outcome["success"] = True
                outcome["message"] = f"SDR agent has started processing {business_data.get('name', 'the business')}"
                
            else:
                business_logger.error(f"Invalid A2A response type: {type(root_response_part)}")
                outcome["error"] = "Invalid response type"
                
    except Exception as e:
        if A2A_AVAILABLE and 'A2AClientHTTPError' in str(type(e)):
            business_logger.error(f"HTTP Error calling SDR agent: {e}")
            outcome["error"] = f"Connection Error: {e}"
        elif A2A_AVAILABLE and 'A2AClientJSONError' in str(type(e)):
            business_logger.error(f"JSON Error from SDR agent: {e}")
            outcome["error"] = f"JSON Response Error: {e}"
        else:
            business_logger.error(f"Unexpected error calling SDR agent: {e}", exc_info=True)
            outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_sdr_agent_simple(business_data: dict[str, Any], session_id: str) -> dict[str, Any]:
    """
    Calls the SDR agent via simple HTTP POST when A2A is not available.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    sdr_url = os.environ.get(
        "SDR_SERVICE_URL", config.DEFAULT_SDR_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling SDR agent (simple HTTP) at {sdr_url} for business: {business_data.get('name', 'Unknown')}")
    
    outcome = {
        "success": False,
        "message": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(auth=ServiceAuth("ui-client", "sdr", campaign_context(session_id)), timeout=300.0) as client:
            # Try different endpoints that might exist
            endpoints_to_try = [
                # f"{sdr_url}/engage_lead",
                # f"{sdr_url}/process",
                f"{sdr_url}/",
            ]
            
            sdr_data = {
                "business": business_data,
                "session_id": session_id,
            }
            
            for endpoint in endpoints_to_try:
                try:
                    business_logger.info(f"Trying SDR endpoint: {endpoint}")
                    response = await client.post(endpoint, json=sdr_data)
                    
                    if response.status_code == 200:
                        result_data = response.json()
                        logger.debug("Sensitive payload omitted")
                        
                        outcome["success"] = True
                        outcome["message"] = f"SDR agent has started processing {business_data.get('name', 'the business')}"
                        break
                    
                    business_logger.warning(f"SDR endpoint {endpoint} returned status {response.status_code}")
                    
                except Exception as e:
                    business_logger.warning(f"SDR endpoint {endpoint} failed: {e}")
                    continue
            
            if not outcome["success"]:
                outcome["error"] = "All SDR agent endpoints failed"
                
    except Exception as e:
        business_logger.error(f"Unexpected error calling SDR agent: {e}", exc_info=True)
        outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_sdr_agent(business_data: dict[str, Any], session_id: str) -> dict[str, Any]:
    """
    Calls the SDR agent - uses A2A if available, otherwise falls back to simple HTTP.
    """
    if A2A_AVAILABLE:
        return await call_sdr_agent_a2a(business_data, session_id)
    else:
        return await call_sdr_agent_simple(business_data, session_id)

async def call_lead_manager_agent_a2a(query: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Manager agent via A2A to process lead management tasks.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    lead_manager_url = os.environ.get(
        "LEAD_MANAGER_SERVICE_URL", config.DEFAULT_LEAD_MANAGER_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling Lead Manager at {lead_manager_url} for query: {query}")
    
    outcome = {
        "success": False,
        "message": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(auth=ServiceAuth("ui-client", "lead-manager", campaign_context(session_id)), ) as http_client:
            a2a_client = A2AClient(httpx_client=http_client, url=lead_manager_url)
            
            # Prepare A2A message
            a2a_task_id = f"lead-management-{session_id}"
            
            lead_data = {
                "query": query,
                "ui_client_url": config.DEFAULT_UI_CLIENT_URL
            }
            
            sdk_message = A2AMessage(
                taskId=a2a_task_id,
                contextId=session_id,
                messageId=str(uuid.uuid4()),
                role=A2ARole.user,
                parts=[A2ADataPart(data=lead_data)],
                metadata={"operation": "process_lead_management", "query": query},
            )
            
            sdk_send_params = MessageSendParams(
                message=sdk_message,
                configuration=MessageSendConfiguration(
                    acceptedOutputModes=["data", "application/json"]
                ),
            )
            
            sdk_request = SendMessageRequest(
                id=str(uuid.uuid4()), params=sdk_send_params
            )
            
            # Send request to Lead Manager
            response: SendMessageResponse = await a2a_client.send_message(sdk_request)
            root_response_part = response.root
            
            if isinstance(root_response_part, JSONRPCErrorResponse):
                actual_error = root_response_part.error
                business_logger.error(
                    f"A2A Error from Lead Manager: {actual_error.code} - {actual_error.message}"
                )
                outcome["error"] = f"A2A Error: {actual_error.code} - {actual_error.message}"
                
            elif isinstance(root_response_part, SendMessageSuccessResponse):
                task_result: A2ATask = root_response_part.result
                business_logger.info(
                    f"Lead Manager task {task_result.id} completed with state: {task_result.status.state}"
                )
                
                # Extract result from artifacts
                if task_result.artifacts:
                    lead_management_artifact = next(
                        (
                            a
                            for a in task_result.artifacts
                            if a.name == config.DEFAULT_LEAD_MANAGER_ARTIFACT_NAME
                        ),
                        None,
                    )
                    
                    if lead_management_artifact and lead_management_artifact.parts:
                        art_part_root = lead_management_artifact.parts[0].root
                        if isinstance(art_part_root, A2ADataPart):
                            result_data = art_part_root.data
                            logger.debug("Sensitive payload omitted")
                            outcome["success"] = True
                            outcome["message"] = result_data.get("message", "Lead management task completed")
                
                if not outcome["success"]:
                    outcome["success"] = True
                    outcome["message"] = "Lead management task completed successfully"
                
            else:
                business_logger.error(f"Invalid A2A response type: {type(root_response_part)}")
                outcome["error"] = "Invalid response type"
                
    except Exception as e:
        business_logger.warning(f"A2A Lead Manager call failed: {e}")
        outcome["error"] = f"A2A call failed: {e}"
    
    return outcome

async def call_lead_manager_agent_simple(query: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Manager service via simple HTTP POST when A2A is not available.
    """
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    
    lead_manager_url = os.environ.get(
        "LEAD_MANAGER_SERVICE_URL", config.DEFAULT_LEAD_MANAGER_URL
    ).rstrip("/")
    
    business_logger.info(f"Calling Lead Manager (simple) at {lead_manager_url} for query: {query}")
    
    outcome = {
        "success": False,
        "message": None,
        "error": None,
    }
    
    try:
        async with httpx.AsyncClient(auth=ServiceAuth("ui-client", "lead-manager", campaign_context(session_id)), ) as http_client:
            payload = {
                "query": query,
                "ui_client_url": config.DEFAULT_UI_CLIENT_URL
            }
            
            response = await http_client.post(
                f"{lead_manager_url}/search",
                json=payload,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                business_logger.info(f"Lead Manager (simple) responded: {result}")
                outcome["success"] = True
                outcome["message"] = result.get("message", "Lead management completed successfully")
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                business_logger.error(f"Lead Manager (simple) error: {error_msg}")
                outcome["error"] = error_msg
                
    except Exception as e:
        business_logger.error(f"Unexpected error calling Lead Manager (simple): {e}", exc_info=True)
        outcome["error"] = f"Unexpected error: {e}"
    
    return outcome

async def call_lead_manager_agent(query: str, session_id: str) -> dict[str, Any]:
    """
    Calls the Lead Manager agent - uses A2A if available, otherwise falls back to simple HTTP.
    """
    if A2A_AVAILABLE:
        try:
            return await call_lead_manager_agent_a2a(query, session_id)
        except Exception as e:
            business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
            business_logger.warning(f"A2A call failed, falling back to simple HTTP: {e}")
            return await call_lead_manager_agent_simple(query, session_id)
    else:
        return await call_lead_manager_agent_simple(query, session_id)

def service_url_for_sdr():
    from common.security import service_url
    return service_url("sdr")


async def run_durable_job(job):
    context = Execution(owner_email(), job["mode"], job["campaign"], job["id"], job["claim_token"])
    store = WorkStore()
    token = execution.set(context)
    current = asyncio.current_task()
    async def renew_claim():
        while True:
            await asyncio.sleep(10)
            try:
                await asyncio.to_thread(store.renew, context)
            except Exception:
                current.cancel()
                return
    renewal = asyncio.create_task(renew_claim())
    try:
        if job["kind"] == "action":
            proposal = await asyncio.to_thread(store.proposal,job["payload"]["action_key"])
            if not proposal:
                raise PolicyDenied("Approved action not found")
            payload = json.loads(proposal["payload"])
            if proposal["kind"] in {"calls","email"}:
                async with httpx.AsyncClient(auth=ServiceAuth("ui-client","sdr"),timeout=660) as client:
                    response=await client.post(service_url_for_sdr()+"/internal/actions/"+job["payload"]["action_key"]+"/execute",json={})
                    response.raise_for_status()
                    output=response.json()
            else:
                from .calendar_routes import meeting,Meeting
                output = await meeting(Meeting.model_validate(payload))
                if isinstance(output,JSONResponse):
                    output = json.loads(output.body)
            result = {"success":output.get("success") is True or output.get("status") in {"success","done"},"provider_result":output}
            if result["success"]:
                async with pipeline_scope():
                    require_current_campaign()
                    from common.execution_store import normalize_phone,normalize_email
                    matched=[]
                    for business in app_state["businesses"].values():
                        with suppress(SecurityError):
                            recipient=normalize_phone(business.phone) if proposal["kind"]=="calls" else normalize_email(business.email)
                            if recipient in json.loads(proposal["recipients"]):
                                matched.append(business.id)
                    if len(matched)==1 or proposal["kind"]=="calendar":
                        await agent_callback(AgentUpdate(agent_type=AgentType.CALENDAR if proposal["kind"]=="calendar" else AgentType.SDR,
                            business_id=matched[0] if len(matched)==1 else "unknown_business",
                            status=BusinessStatus.MEETING_SCHEDULED if proposal["kind"]=="calendar" else BusinessStatus.CONTACTED,
                            message="Provider confirmed the approved action",data={**output,"action_key":job["payload"]["action_key"]}))

        elif job["kind"] == "discovery":
            result = await run_lead_finding_process(job["payload"]["city"],job["campaign"],job["payload"].get("niche", ""))
        else:
            async with pipeline_scope():
                require_current_campaign()
                if job["kind"] == "sdr":
                    result = await call_sdr_agent(job["payload"]["business"],job["campaign"])
                else:
                    result = await call_lead_manager_agent(job["payload"]["query"],job["campaign"])
                require_current_campaign()
                await manager.send_update({"type":"job_result","job_id":job["id"],"success":bool(result.get("success"))})
        await asyncio.to_thread(store.finish_job,context,result,
            None if result and result.get("success") else "Workflow did not confirm success")
    except asyncio.CancelledError:
        with suppress(Exception):
            await asyncio.to_thread(store.finish_job,context,None,"Consumer stopped; outcome unresolved")
        raise
    except Exception:
        with suppress(Exception):
            await asyncio.to_thread(store.finish_job,context,None,"Workflow failed or provider outcome is uncertain")
        logger.warning("Durable job did not complete; see owner job ledger")
    finally:
        renewal.cancel()
        with suppress(asyncio.CancelledError):
            await renewal
        execution.reset(token)


async def dispatch_loop():
    while True:
        await asyncio.sleep(0.25)
        try:
            job = await asyncio.to_thread(WorkStore().claim,owner_email(),runtime_worker_id,mode())
            if job:
                # A cancelled claim must not stop the lifespan consumer.
                task = asyncio.create_task(run_durable_job(job))
                try:
                    await task
                except asyncio.CancelledError:
                    if asyncio.current_task().cancelling():
                        task.cancel()
                        with suppress(asyncio.CancelledError):
                            await task
                        raise
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.error("Durable dispatcher unavailable; no provider work dispatched")
            await asyncio.sleep(1)


async def run_lead_finding_process(city: str, session_id: str, niche: str = ""):
    token = execution.set(campaign_context(session_id))
    try:
        if pipeline_store is not None:
            async with pipeline_scope():
                if campaign_is_current(session_id):
                    return await _run_lead_finding_process(city, session_id, niche)
        elif campaign_is_current(session_id):
            return await _run_lead_finding_process(city, session_id, niche)
    except StoreConflict:
        logger.info("Discarded obsolete discovery result after a competing commit")
    finally:
        execution.reset(token)


async def _run_lead_finding_process(city: str, session_id: str, niche: str = ""):
    """Run the complete lead finding process."""
    business_logger = logging.getLogger(BUSINESS_LOGIC_LOGGER)
    outcome = {"success": False, "error": "Discovery did not complete"}
    
    try:
        business_logger.info(f"Starting lead finding process for {city}")
        
        # Call Lead Finder agent
        result = await call_lead_finder_agent(city, session_id, niche=niche)
        if not campaign_is_current(session_id):
            return
        outcome = result
        
        if result["success"]:
            found_businesses = result.get("businesses", [])
            business_logger.info(f"Lead Finder returned {len(found_businesses)} businesses")
            
            # Store businesses in UI state and notify the dashboard
            for b_data in found_businesses:
                if not campaign_is_current(session_id):
                    return
                try:
                    import hashlib
                    stable_id = hashlib.sha256(json.dumps([city,b_data.get("name"),b_data.get("phone")],sort_keys=True).encode()).hexdigest()
                    biz_id = b_data.get("id") or stable_id
                    new_biz = Business(
                        id=biz_id,
                        name=b_data.get("name") or "Unknown Business",
                        city=city,
                        phone=b_data.get("phone") or b_data.get("phone_number"),
                        email=b_data.get("email"),
                        description=b_data.get("description") or b_data.get("snippet"),
                        status=BusinessStatus.FOUND,
                        notes=["Found via Lead Finder"]
                    )
                    app_state["businesses"][biz_id] = new_biz
                    
                    # Push to UI immediately
                    await manager.send_update({
                        "type": "business_updated",
                        "agent": AgentType.LEAD_FINDER.value,
                        "business": new_biz.model_dump(),
                        "update": {
                            "agent_type": AgentType.LEAD_FINDER.value,
                            "business_id": biz_id,
                            "status": BusinessStatus.FOUND.value,
                            "message": "Lead discovered in initial search"
                        },
                        "timestamp": datetime.now().isoformat(),
                    })
                except StoreConflict:
                    raise
                except Exception as e:
                    business_logger.error(f"Error processing business lead: {e}")

            # Send completion update regardless of whether businesses were found
            await manager.send_update({
                "type": "lead_finding_completed",
                "city": city,
                "business_count": len(found_businesses),
                "timestamp": datetime.now().isoformat(),
            })
            
            # Check if the returned list is empty
            if not found_businesses:
                business_logger.info(f"No businesses found for city: {city}. Notifying UI.")
                await manager.send_update({
                    "type": "lead_finding_empty",
                    "city": city,
                    "message": "No businesses found for this city. Try another city.",
                    "timestamp": datetime.now().isoformat(),
                })
            
        else:
            business_logger.error(f"Lead finding failed: {result['error']}")
            await manager.send_update({
                "type": "lead_finding_failed",
                "error": result["error"],
                "timestamp": datetime.now().isoformat(),
            })
    
    except StoreConflict:
        raise
    except Exception as e:
        if not campaign_is_current(session_id):
            return
        business_logger.error(f"Error in lead finding process: {e}", exc_info=True)
        await manager.send_update({
            "type": "lead_finding_failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        })
    
    finally:
        # Old work must never finish or publish into a reset/newer campaign.
        if campaign_is_current(session_id):
            app_state["is_running"] = False
            await manager.send_update({
                "type": "process_finished",
                "timestamp": datetime.now().isoformat(),
            })
    return outcome

def socket_snapshot(snapshot, revision):
    snapshot = snapshot or empty_pipeline_state()
    return {"type": "initial_state", "campaign_id": snapshot.get("session_id"), "revision": revision,
            "businesses": list(snapshot.get("businesses", {}).values()),
            "current_city": snapshot.get("current_city"), "is_running": snapshot.get("is_running", False)}


async def deliver_socket_events(websocket, cursor, revision):
    """Consume a bounded committed owner outbox; works across local UI workers."""
    batch = await asyncio.to_thread(pipeline_store.read_view, runtime_owner(), cursor)
    campaign = (batch["snapshot"] or {}).get("session_id")
    for event in batch["events"]:
        if event["campaign_id"] == campaign:
            await websocket.send_text(json.dumps({**event["payload"], "event_id": event["id"]}, default=str))
        cursor = event["id"]
    if cursor >= batch["cursor"] and revision != batch["revision"]:
        await websocket.send_text(json.dumps(socket_snapshot(batch["snapshot"], batch["revision"]), default=str))
        revision = batch["revision"]
    return cursor, revision


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        view = app_state.current_view()
        cursor, revision = view.cursor, view.revision
        await websocket.send_text(json.dumps(socket_snapshot(pipeline_snapshot(), revision), default=str))
        while True:
            try:
                await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
            # Validate even during quiet periods, including a logout on another worker.
            from .security import session_user
            _, user = await session_user(websocket.scope)
            if user is None:
                await websocket.close(code=1008)
                return
            cursor, revision = await deliver_socket_events(websocket, cursor, revision)
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)

# Agent callback endpoint
# In ui_client/main.py
# In ui_client/main.py

# In ui_client/main.py

# In ui_client/main.py

@app.post("/agent_callback")
async def agent_callback(update: AgentUpdate):
    """
    Endpoint for agents to send updates about business processing.
    This version handles creating new businesses and correctly serializes
    Pydantic models before sending them over WebSockets.
    """
    try:
        require_current_campaign()
    except SecurityError:
        return JSONResponse({"error": "Campaign is missing, reset or superseded"}, status_code=409)

    if update.status in {BusinessStatus.CONTACTED,BusinessStatus.MEETING_SCHEDULED}:
        receipt = update.data or {}
        kind = "calendar" if update.status == BusinessStatus.MEETING_SCHEDULED else ("calls" if receipt.get("conversation_id") else "email")
        provider_id = receipt.get("meeting_id") or receipt.get("conversation_id") or receipt.get("message_id")
        if not WorkStore().confirmed(receipt.get("action_key"),kind,provider_id):
            return JSONResponse({"error":"No confirmed durable provider receipt"},409)

    logger.info(f"Received agent callback: {update.agent_type} for business {update.business_id}")

    # Special handling for Calendar agent: do not auto-create businesses, only send meeting notifications
    if update.agent_type == AgentType.CALENDAR:
        # If the business exists, update its status and send business_updated event
        if update.business_id in app_state["businesses"]:
            business = app_state["businesses"][update.business_id]
            business.status = update.status
            business.updated_at = datetime.now()
            business.notes.append(f"{update.agent_type}: {update.message}")
            logger.info(f"Updated business {business.name} status to {update.status}")
            biz_payload = {
                "type": "business_updated",
                "agent": update.agent_type.value,
                "business": business.model_dump(),
                "update": update.model_dump(),
                "timestamp": datetime.now().isoformat(),
            }
            await manager.send_update(biz_payload)
        # Always send the calendar-specific notification
        cal_payload = {
            "type": "calendar_notification",
            "agent": update.agent_type.value,
            "business_id": update.business_id,
            "data": update.data or {},
            "message": update.message,
            "timestamp": datetime.now().isoformat(),
        }
        await manager.send_update(cal_payload)
        return JSONResponse(status_code=200, content={"status": "success", "message": "Calendar notification sent"})
    # Check if business exists for non-calendar agents
    if update.business_id in app_state["businesses"]:
        # Business exists, so update it
        business = app_state["businesses"][update.business_id]
        business.status = update.status
        business.updated_at = datetime.now()
        business.notes.append(f"{update.agent_type}: {update.message}")
        logger.info(f"Updated business {business.name} status to {update.status}")
    else:
        # Business does NOT exist, attempt to create a new entry with available data
        logger.info(f"Business ID {update.business_id} not found. Attempting to create new business entry.")
        data = update.data or {}
        # Fallback fields from various possible keys
        name = data.get("name") or data.get("sender_name") or data.get("lead_name")
        city = data.get("city") or ""
        phone = data.get("phone") or data.get("lead_phone") or data.get("phone_number")
        email = data.get("email") or data.get("sender_email") or data.get("lead_email")
        description = (
            data.get("description") or data.get("subject") or data.get("email_subject") or data.get("body_preview")
        )
        if not name:
            logger.warning(f"Cannot create business {update.business_id}: missing name in callback data.")
            return JSONResponse(status_code=400, content={"status": "error", "message": "Cannot create business: missing name"})
        try:
            new_business = Business(
                id=update.business_id,
                name=name,
                phone=phone,
                email=email,
                description=description,
                city=city,
                status=update.status,
                notes=[f"{update.agent_type}: {update.message}"]
            )
            app_state["businesses"][update.business_id] = new_business
        except Exception as e:
            logger.error(f"Failed to create business from callback data: {e}")
            return JSONResponse(status_code=400, content={"status": "error", "message": f"Cannot create business: {str(e)}"})

    # Get the final business object to send in the update
    final_business_obj = app_state["businesses"].get(update.business_id)
    if final_business_obj and update.status == BusinessStatus.NOT_INTERESTED:
        for recipient in (final_business_obj.email, final_business_obj.phone):
            if recipient:
                with suppress(SecurityError):
                    await asyncio.to_thread(WorkStore().suppress,recipient,"Recipient opted out")

    # Handle calendar events: first send a business_updated to move/create the card,
    # then send a calendar_notification with meeting details
    if update.agent_type == AgentType.CALENDAR and final_business_obj:
        # Business_updated event for calendar status
        biz_payload = {
            "type": "business_updated",
            "agent": update.agent_type.value,
            "business": final_business_obj.model_dump(),
            "update": update.model_dump(),
            "timestamp": datetime.now().isoformat(),
        }
        await manager.send_update(biz_payload)
        # Calendar-specific notification
        cal_payload = {
            "type": "calendar_notification",
            "agent": update.agent_type.value,
            "business_id": update.business_id,
            "data": update.data,
            "message": update.message,
            "timestamp": datetime.now().isoformat(),
        }
        await manager.send_update(cal_payload)
    # Handle other agent updates
    elif final_business_obj:
        # Standard business update: store and notify
        app_state["agent_updates"].append(update)
        update_payload = {
            "type": "business_updated",
            "agent": update.agent_type.value,
            "business": final_business_obj.model_dump(),
            "update": update.model_dump(),
            "timestamp": datetime.now().isoformat(),
        }
        await manager.send_update(update_payload)

    return JSONResponse(status_code=200, content={"status": "success", "message": "Business processed"})

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request) -> HTMLResponse:
    """Use the dashboard that supplies session credentials and CSRF headers."""
    return RedirectResponse(
        os.getenv("NEXT_PUBLIC_FRONTEND_URL", "http://localhost:3000").rstrip("/") + "/dashboard",
        status_code=303,
    )

@app.get("/architecture_diagram", response_class=HTMLResponse)
async def architecture_diagram(request: Request) -> HTMLResponse:
    """Serves the architecture diagram page."""
    return templates.TemplateResponse(
        request=request,
        name="architecture_diagram.html",
        context={}
    )
        
        
@app.post("/start_lead_finding")
async def start_lead_finding(city: str = Form(...), niche: str = Form(None)):
    """Start the lead finding process for a given city."""
    if app_state["is_running"]:
        return JSONResponse(
            status_code=400,
            content={"error": "Lead finding process is already running"}
        )
    
    try:
        # Validate input
        request_data = LeadFinderRequest(city=city.strip(), niche=niche.strip() if niche else None)
        
        app_state["is_running"] = True
        app_state["current_city"] = request_data.city
        session_id = str(uuid.uuid4())
        app_state["session_id"] = session_id
        app_state["businesses"] = {}  # Reset businesses for new search
        app_state["agent_updates"] = []  # Reset updates
        app_state["human_input_requests"] = {}
        app_state["lead_scores"] = {}
        
        logger.info(f"Starting lead finding process for city: {request_data.city}")
        
        # Send initial update
        await manager.send_update({
            "type": "process_started",
            "city": request_data.city,
            "timestamp": datetime.now().isoformat(),
        }, dispatch={"kind":"discovery","payload":{"city":request_data.city,"niche":request_data.niche or ""},"mode":mode()})
        
        return RedirectResponse("/", status_code=303)
        
    except ValidationError as e:
        logger.error(f"Invalid city input: {e}")
        return JSONResponse(
            status_code=400,
            content={"error": f"Invalid input: {e}"}
        )
    except StoreConflict:
        raise
    except Exception as e:
        logger.error(f"Error starting lead finding: {e}", exc_info=True)
        app_state["is_running"] = False
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to start process: {e}"}
        )

@app.get("/api/businesses")
async def get_businesses():
    """API endpoint to get all businesses."""
    return {
        "businesses": [business.model_dump() for business in app_state["businesses"].values()],
        "total": len(app_state["businesses"])
    }

@app.get("/api/status")
async def get_status():
    """API endpoint to get current application status."""
    return {
        "is_running": app_state["is_running"],
        "current_city": app_state["current_city"],
        "business_count": len(app_state["businesses"]),
        "session_id": app_state["session_id"],
    }

@app.post("/send_to_sdr")
async def send_business_to_sdr(
    business_id: str = Form(...), 
    user_phone: Optional[str] = Form(None)
):
    """Send a business to the SDR agent for processing."""
    try:
        require_action("calls")
    except SecurityError as exc:
        return JSONResponse({"error": str(exc)}, status_code=403)
    try:
        # Check if business exists
        if business_id not in app_state["businesses"]:
            return JSONResponse(
                status_code=404,
                content={"error": "Business not found"}
            )
        
        business = app_state["businesses"][business_id]
        
        # Convert business to dict for sending to SDR
        business_data = business.model_dump(mode="json")
        
        # Override phone number if user provided one
        if user_phone:
            business_data["phone_number"] = user_phone
            business_data["phone"] = user_phone
            logger.info(f"Overriding phone number to: {user_phone} for business {business.name}")
        
        from common.execution_store import normalize_phone
        try:
            business_data["phone"] = normalize_phone(business_data.get("phone") or business_data.get("phone_number"))
            business_data["phone_number"] = business_data["phone"]
        except SecurityError as exc:
            return JSONResponse({"error":str(exc),"error_category":"validation"},422)
        # Get current session ID
        session_id = app_state["session_id"]
        if not session_id:
            return JSONResponse({"error": "Start a campaign before contacting a lead"}, status_code=409)
        
        logger.info(f"Sending business {business.name} to SDR agent")
        
        queued = await persist_pipeline({"type":"job_queued","agent":"sdr"},
            dispatch={"kind":"sdr","payload":{"business":business_data},"mode":mode()})
        return JSONResponse({"success":True,"job_id":queued["job_id"],"message":"Outreach queued; no provider action is confirmed"},202)

    except StoreConflict:
        raise
    except Exception as e:
        logger.error(f"Error sending business to SDR: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"error": f"Failed to send to SDR: {e}"}
        )

@app.post("/reset")
async def reset_state():
    """Reset the application state."""
    app_state["is_running"] = False
    app_state["current_city"] = None
    app_state["businesses"] = {}
    app_state["agent_updates"] = []
    app_state["session_id"] = None
    app_state["human_input_requests"] = {}
    app_state["lead_scores"] = {}
    
    await manager.send_update({
        "type": "state_reset",
        "timestamp": datetime.now().isoformat(),
    })
    
    return RedirectResponse("/", status_code=303)

@app.post("/trigger_lead_manager")
async def trigger_lead_manager():
    if mode() != "live":
        return JSONResponse({"error":"Live workflow disabled in demo mode"},403)
    if not app_state["session_id"]:
        return JSONResponse({"error":"Start a campaign first"},409)
    queued = await persist_pipeline({"type":"job_queued","agent":"lead_manager"},
        dispatch={"kind":"lead_manager","payload":{"query":"check_lead_emails"},"mode":mode()})
    return JSONResponse({"success":True,"job_id":queued["job_id"],"message":"Lead Manager queued"},202)

@app.post("/api/human-input")
async def receive_human_input_request(request: HumanInputRequest):
    """Receive a human input request from agents."""
    logger.info(f"Received human input request: {request.request_id} - {request.type}")
    
    try:
        require_current_campaign()
    except SecurityError:
        return JSONResponse({"error": "Campaign is missing, reset or superseded"}, status_code=409)

    campaign = execution.get().campaign_id
    if request.campaign_id is not None and request.campaign_id != campaign:
        return JSONResponse({"error": "Request campaign does not match signer"}, status_code=409)
    request = request.model_copy(update={"campaign_id": campaign,"job_id":execution.get().job_id})
    # Store only the provenance verified from the service signature.
    app_state["human_input_requests"][request.request_id] = request
    
    # Send notification to all connected WebSocket clients
    await manager.send_update({
        "type": "human_input_request",
        "request_id": request.request_id,
        "prompt": request.prompt,
        "input_type": request.type,
        "timestamp": request.timestamp,
    })
    
    return {
        "status": "received",
        "request_id": request.request_id,
        "message": "Human input request received. Please check the UI for the modal dialog.",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/human-input")
async def get_pending_human_input_requests():
    """Get all pending human input requests."""
    return {
        "requests": [req.model_dump() for req in app_state["human_input_requests"].values()],
        "count": len(app_state["human_input_requests"])
    }

@app.post("/api/human-input/{request_id}")
async def submit_human_input_response(request_id: str, response: HumanInputResponse):
    """Submit a response to a human input request."""
    if request_id not in app_state["human_input_requests"]:
        return JSONResponse(
            status_code=404,
            content={"error": "Request not found"}
        )
    
    # Get the request first (but don't remove it yet)
    original_request = app_state["human_input_requests"].get(request_id)
    session_id = app_state["session_id"]
    if (response.request_id != request_id or response.campaign_id != session_id
            or original_request.campaign_id != session_id):
        return JSONResponse({"error": "Approval does not belong to the active campaign"}, status_code=409)

    logger.info("Human input response submitted for %s", request_id)
    
    # Try to notify the human creation tool via HTTP callback to SDR agent
    success = False
    agent_url = os.environ.get("SDR_SERVICE_URL", config.DEFAULT_SDR_URL).rstrip("/")
    callback_url = f"{agent_url}/api/human-input/{request_id}"
    approval_context = campaign_context(session_id)
    if original_request.job_id:
        with WorkStore().connection() as connection:
            job=connection.execute("SELECT * FROM dispatch_jobs WHERE owner=? AND id=? AND state='running'",(execution.get().owner,original_request.job_id)).fetchone()
            if not job:
                return JSONResponse({"error":"Approval job is no longer active"},409)
            approval_context=Execution(execution.get().owner,job['mode'],session_id,job['id'],job['claim_token'])
    try:
        async with httpx.AsyncClient(auth=ServiceAuth("ui-client", "sdr", approval_context), timeout=10.0) as client:
            agent_resp = await client.post(
                callback_url,
                json={"url": response.response},
                headers={"Content-Type": "application/json"}
            )
            if agent_resp.status_code == 200:
                logger.info(f"Successfully notified human creation tool on agent for request {request_id}")
                success = True
            else:
                logger.warning(f"Agent returned status {agent_resp.status_code} for request {request_id}: {agent_resp.text}")
    except httpx.ConnectError:
        logger.warning(f"Connection to SDR agent failed for request {request_id}")
    except Exception as e:
        logger.error(f"Error notifying SDR agent for request {request_id}: {e}")
    
    if not campaign_is_current(session_id):
        return JSONResponse({"error": "Campaign was reset or superseded"}, status_code=409)

    if not success:
        return JSONResponse({"error": "Approval delivery failed; request remains pending"}, status_code=503)
    # Only remove the request after successful processing by the matching agent.
    app_state["human_input_requests"].pop(request_id, None)
    
    # Send WebSocket notification that response was submitted
    await manager.send_update({
        "type": "human_input_response_submitted",
        "request_id": request_id,
        "response": response.response,
        "timestamp": datetime.now().isoformat()
    })
    
    return {
        "status": "success",
        "request_id": request_id,
        "message": "Response submitted successfully",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring and load balancers."""
    return {
        "status": "healthy",
        "service": "ui_client",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
    }

@app.get("/debug/static")
async def debug_static():
    """Debug endpoint to check static file configuration."""
    import os
    
    static_files_info = {
        "static_dir": str(static_dir),
        "static_dir_exists": static_dir.exists(),
        "templates_dir": str(templates_dir),
        "templates_dir_exists": templates_dir.exists(),
        "working_directory": os.getcwd(),
        "module_file_location": str(Path(__file__)),
        "module_dir": str(module_dir)
    }
    
    # List static files if directory exists
    if static_dir.exists():
        try:
            static_files = []
            for root, dirs, files in os.walk(static_dir):
                for file in files:
                    rel_path = os.path.relpath(os.path.join(root, file), static_dir)
                    static_files.append(rel_path)
            static_files_info["static_files"] = static_files
        except Exception as e:
            static_files_info["static_files_error"] = str(e)
    else:
        static_files_info["static_files"] = "Directory does not exist"
    
    return static_files_info

@app.get("/api/system-status")
async def get_system_status():
    """
    Checks two things separately:
    - call_ready: ElevenLabs / Twilio keys exist → real outbound calls can be made
    - lead_finder_ready: Google Maps API billing is active → real lead search works
    
    The system is considered 'ready' if call_ready is True.
    Maps API failure only triggers 'demo_leads' mode (mock businesses), not full demo mode.
    """
    import os
    import httpx

    if mode() == "demo":
        return {"ready": False, "lead_finder_ready": False, "mode": "demo",
                "missing": [], "message": "Demo mode — external actions are disabled",
                "lead_finder_message": "Simulated lead discovery"}
    
    # ── Check call readiness (ElevenLabs / Twilio) ───────────────────────
    elevenlabs_key = os.getenv("ELEVENLABS_API_KEY", "")
    elevenlabs_agent = os.getenv("ELEVENLABS_AGENT_ID", "")
    twilio_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
    
    call_ready = bool(elevenlabs_key and elevenlabs_agent) and os.getenv("ENABLE_LIVE_CALLS", "false").lower() == "true"
    
    # ── Check lead finder (Google Maps API billing) ───────────────────────
    maps_key = os.getenv("GOOGLE_MAPS_API_KEY", "")
    lead_finder_ready = False
    lead_finder_message = "Google Maps API key not configured"
    
    if maps_key:
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(
                    "https://maps.googleapis.com/maps/api/place/textsearch/json",
                    params={"query": "coffee", "key": maps_key},
                    timeout=5.0
                )
                data = res.json()
                status = data.get("status", "")
                if status in ("OK", "ZERO_RESULTS"):
                    lead_finder_ready = True
                    lead_finder_message = "Google Maps API active"
                elif status == "REQUEST_DENIED":
                    lead_finder_message = f"Google Maps billing not enabled — using realistic mock leads"
                elif status == "OVER_QUERY_LIMIT":
                    lead_finder_message = "Google Maps over quota — using realistic mock leads"
                else:
                    lead_finder_message = f"Google Maps status: {status}"
        except Exception as e:
            lead_finder_message = f"Maps API unreachable: {str(e)}"
    
    return {
        "ready": call_ready,           # True = SDR/ElevenLabs calls work fine
        "lead_finder_ready": lead_finder_ready,  # True = real Maps search works
        "missing": [] if call_ready else ["ELEVENLABS_API_KEY or TWILIO_ACCOUNT_SID"],
        "message": "System ready — outbound calls active" if call_ready else "Call agent not configured",
        "lead_finder_message": lead_finder_message,
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("--- Starting FastAPI server for UI Client ---")
    logger.info("Ensure dependent A2A services are running:")
    logger.info(f"  Lead Finder: python -m lead_finder --port {config.DEFAULT_LEAD_FINDER_PORT}")
    logger.info(f"  SDR: python -m sdr --port {config.DEFAULT_SDR_PORT}")
    logger.info(f"  Lead Manager: python -m lead_manager --port {config.DEFAULT_LEAD_MANAGER_PORT}")
    logger.info(f"--- Access UI at http://0.0.0.0:{config.UI_CLIENT_SERVICE_NAME} ---")
    
    uvicorn.run(
        "ui_client.main:app",
        host="0.0.0.0",
        port=config.UI_CLIENT_SERVICE_NAME,
        reload=False
    )
