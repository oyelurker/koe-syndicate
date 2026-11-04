"""
Test suite for the Koe Syndicate UI Client.

This module contains comprehensive tests for the UI Client including:
- API endpoints
- WebSocket functionality
- Business state management
- A2A integration
- Error handling

Run tests with:
    python -m pytest ui_client/test/test_ui_client.py -v
    python -m pytest ui_client/test/test_ui_client.py::TestUIClient::test_health_check -v
"""

import json
import pytest
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch
from fastapi.testclient import TestClient
from fastapi.websockets import WebSocket
import httpx
from google.oauth2.credentials import Credentials
from common.security import Execution, ServiceAuth, execution
from ui_client import db, security
from ui_client.store import Store
from ui_client.main import pipeline_snapshot
from a2a.types import Task, TaskStatus, TaskState, SendMessageResponse, SendMessageSuccessResponse, JSONRPCError, JSONRPCErrorResponse

from ui_client.main import app, app_state, manager, ConnectionManager, Business, BusinessStatus, AgentType, AgentUpdate


def persist_fixture_state():
    store = Store(db.DB_PATH)
    revision = store.read_view("owner@example.test")["revision"]
    store.save("owner@example.test", pipeline_snapshot(), expected_revision=revision)


def signed_callback(client, payload):
    request = httpx.Request("POST", "http://localhost:8000/agent_callback", json=payload)
    app_state["session_id"] = app_state["session_id"] or "fixture-campaign"
    persist_fixture_state()
    signed = next(ServiceAuth("sdr", "ui-client", Execution("owner@example.test", "demo", app_state["session_id"])).auth_flow(request))
    return client.post(request.url.path, content=request.content, headers=dict(signed.headers))

class TestUIClient:
    """Test class for UI Client functionality."""
    
    @pytest.fixture
    def client(self):
        """Use real session and CSRF validation against temporary storage."""
        with TestClient(app, base_url="http://localhost:8000", follow_redirects=False) as caller:
            async def seed():
                uid = await db.upsert_user({"id": "owner", "email": "owner@example.test"},
                    Credentials(token="test-token", refresh_token="test-refresh", token_uri="https://oauth2.googleapis.com/token",
                                client_id="test", client_secret="test", scopes=[]))
                await db.create_session("ui-test-session", uid)
            asyncio.run(seed())
            caller.cookies.set("koe_session", security.signer().dumps("ui-test-session"))
            caller.headers.update({"Origin": "http://localhost:3000", "X-Koe-CSRF": security.csrf_token("ui-test-session")})
            yield caller
    
    def test_health_check(self, client, reset_app_state):
        """Test the health check endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "ui_client"
        assert "timestamp" in data
        assert not {"active_connections", "is_running", "business_count"} & data.keys()
    
    def test_root_endpoint_initial_state(self, client, reset_app_state):
        """The authenticated legacy root redirects to the frontend."""
        response = client.get("/")
        assert response.status_code == 303
        assert response.headers["location"] == "http://localhost:3000/dashboard"
    
    def test_root_endpoint_with_data(self, client, reset_app_state):
        """Test root endpoint returns dashboard when data exists."""
        # Add some test business data
        test_business = Business(
            name="Test Company",
            city="San Francisco",
            status=BusinessStatus.FOUND
        )
        app_state["businesses"][test_business.id] = test_business
        app_state["current_city"] = "San Francisco"
        
        response = client.get("/")
        assert response.status_code == 303
        assert response.headers["location"] == "http://localhost:3000/dashboard"
    
    def test_start_lead_finding_valid_input(self, client, reset_app_state):
        """Test starting lead finding with valid city input."""
        with patch("ui_client.main.WorkStore.claim", return_value=None):
            response = client.post("/start_lead_finding", data={"city": "New York"})
            assert response.status_code == 303  # Redirect
            assert app_state["current_city"] == "New York"
            assert app_state["is_running"] is True
            assert app_state["session_id"] is not None
            from common.execution_store import WorkStore
            assert WorkStore().jobs("owner@example.test")[0]["kind"] == "discovery"
    
    def test_start_lead_finding_empty_city(self, client, reset_app_state):
        """Test starting lead finding with empty city input."""
        response = client.post("/start_lead_finding", data={"city": "   "})
        assert response.status_code == 400
        assert app_state["is_running"] is False
    
    def test_start_lead_finding_already_running(self, client, reset_app_state):
        """Test starting lead finding when already running."""
        app_state["is_running"] = True
        persist_fixture_state()
        response = client.post("/start_lead_finding", data={"city": "Boston"})
        assert response.status_code == 400
        data = response.json()
        assert "already running" in data["error"]
    
    def test_agent_callback_valid_update(self, client, reset_app_state):
        """Test agent callback with valid business update."""
        # Create a test business
        test_business = Business(
            name="Test Business",
            city="Chicago",
            status=BusinessStatus.FOUND
        )
        app_state["businesses"][test_business.id] = test_business
        
        # Send agent update
        update_data = {
            "agent_type": "sdr",
            "business_id": test_business.id,
            "status": "engaged",
            "message": "Business showed interest",
            "timestamp": datetime.now().isoformat()
        }
        
        with patch.object(manager, "send_update") as mock_send:
            response = signed_callback(client, update_data)
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            
            # Check business was updated
            updated_business = app_state["businesses"][test_business.id]
            assert updated_business.status == BusinessStatus.ENGAGED
            assert len(updated_business.notes) == 1
            
            # Check WebSocket update was sent
            mock_send.assert_called_once()
    
    def test_agent_callback_business_not_found(self, client, reset_app_state):
        """Test agent callback with non-existent business ID."""
        update_data = {
            "agent_type": "sdr",
            "business_id": "non-existent-id",
            "status": "engaged",
            "message": "Business showed interest",
            "timestamp": datetime.now().isoformat()
        }
        
        response = signed_callback(client, update_data)
        assert response.status_code == 400
        data = response.json()
        assert data["status"] == "error"
        assert "missing name" in data["message"]
    
    def test_api_businesses_empty(self, client, reset_app_state):
        """Test businesses API endpoint with no businesses."""
        persist_fixture_state()
        response = client.get("/api/businesses")
        assert response.status_code == 200
        data = response.json()
        assert data["businesses"] == []
        assert data["total"] == 0
    
    def test_api_businesses_with_data(self, client, reset_app_state):
        """Test businesses API endpoint with business data."""
        test_business = Business(
            name="API Test Business",
            city="Seattle",
            status=BusinessStatus.ENGAGED
        )
        app_state["businesses"][test_business.id] = test_business
        
        persist_fixture_state()
        response = client.get("/api/businesses")
        assert response.status_code == 200
        data = response.json()
        assert len(data["businesses"]) == 1
        assert data["total"] == 1
        assert data["businesses"][0]["name"] == "API Test Business"
    
    def test_api_status(self, client, reset_app_state):
        """Test status API endpoint."""
        app_state["current_city"] = "Portland"
        app_state["is_running"] = True
        app_state["session_id"] = "test-session-123"
        
        persist_fixture_state()
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["current_city"] == "Portland"
        assert data["is_running"] is True
        assert data["session_id"] == "test-session-123"
        assert data["business_count"] == 0
    
    def test_reset_state(self, client, reset_app_state):
        """Test resetting application state."""
        # Set up some state
        app_state["current_city"] = "Denver"
        app_state["is_running"] = True
        test_business = Business(name="Test", city="Denver")
        app_state["businesses"][test_business.id] = test_business
        
        with patch.object(manager, "send_update") as mock_send:
            response = client.post("/reset")
            assert response.status_code == 303  # Redirect
            
            # Check state was reset
            assert app_state["current_city"] is None
            assert app_state["is_running"] is False
            assert len(app_state["businesses"]) == 0
            
            # Check WebSocket update was sent
            mock_send.assert_called_once()

class TestWebSocketManager:
    """Test WebSocket functionality."""

    @pytest.fixture
    def connection_manager(self):
        return ConnectionManager()
    
    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        mock_ws = Mock(spec=WebSocket)
        mock_ws.accept = AsyncMock()
        mock_ws.send_text = AsyncMock()
        return mock_ws
    
    @pytest.mark.asyncio
    async def test_websocket_connect(self, connection_manager, mock_websocket):
        """Test WebSocket connection."""
        await connection_manager.connect(mock_websocket)
        
        mock_websocket.accept.assert_called_once()
        assert mock_websocket in connection_manager.active_connections
    
    def test_websocket_disconnect(self, connection_manager, mock_websocket):
        """Test WebSocket disconnection."""
        connection_manager.active_connections[mock_websocket] = "owner@example.test"
        connection_manager.disconnect(mock_websocket)
        
        assert mock_websocket not in connection_manager.active_connections
    
    @pytest.mark.asyncio
    async def test_send_update_no_connections(self, connection_manager):
        """Test sending update with no active connections."""
        connection_manager.active_connections.clear()
        
        # Should not raise an exception
        await connection_manager.send_update({"type": "test", "data": "test"})
    
    @pytest.mark.asyncio
    async def test_send_update_with_connections(self, connection_manager, mock_websocket):
        """Test sending update to active connections."""
        connection_manager.active_connections[mock_websocket] = "owner@example.test"
        
        test_data = {"type": "test", "message": "hello"}
        await connection_manager.send_update(test_data)
        
        mock_websocket.send_text.assert_called_once_with(json.dumps({**test_data, "campaign_id": None}))
    
    @pytest.mark.asyncio
    async def test_send_update_connection_error(self, connection_manager, mock_websocket):
        """Test handling connection errors during update."""
        mock_websocket.send_text.side_effect = Exception("Connection error")
        connection_manager.active_connections[mock_websocket] = "owner@example.test"
        
        # Should handle the error gracefully and remove the connection
        await connection_manager.send_update({"type": "test"})
        
        assert mock_websocket not in connection_manager.active_connections

class TestBusinessModels:
    """Test business data models."""
    
    def test_business_creation(self):
        """Test creating a Business instance."""
        business = Business(
            name="Test Company",
            phone="123-456-7890",
            email="test@company.com",
            description="A test company",
            city="Austin"
        )
        
        assert business.name == "Test Company"
        assert business.phone == "123-456-7890"
        assert business.email == "test@company.com"
        assert business.description == "A test company"
        assert business.city == "Austin"
        assert business.status == BusinessStatus.FOUND
        assert isinstance(business.created_at, datetime)
        assert len(business.notes) == 0
    
    def test_agent_update_creation(self):
        """Test creating an AgentUpdate instance."""
        update = AgentUpdate(
            agent_type=AgentType.SDR,
            business_id="test-id",
            status=BusinessStatus.ENGAGED,
            message="Business engaged successfully"
        )
        
        assert update.agent_type == AgentType.SDR
        assert update.business_id == "test-id"
        assert update.status == BusinessStatus.ENGAGED
        assert update.message == "Business engaged successfully"
        assert isinstance(update.timestamp, datetime)

class TestA2AIntegration:
    """Test A2A integration functionality."""

    @pytest.fixture(autouse=True)
    def execution_owner(self):
        token = execution.set(Execution("owner@example.test", "demo"))
        yield
        execution.reset(token)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("state,success", [(TaskState.completed, True), (TaskState.failed, False)])
    async def test_call_lead_finder_task_response(self, state, success):
        """Exercise the real SDK response union, including empty successful results."""
        with patch("ui_client.main.httpx.AsyncClient") as mock_client_class:
            # Mock the HTTP client and A2A client
            mock_http_client = AsyncMock()
            mock_client_class.return_value.__aenter__.return_value = mock_http_client
            
            with patch("ui_client.main.A2AClient") as mock_a2a_client_class:
                mock_a2a_client = AsyncMock()
                mock_a2a_client_class.return_value = mock_a2a_client
                
                mock_response = SendMessageResponse(root=SendMessageSuccessResponse(id="request", result=Task(
                    id="task", contextId="campaign", status=TaskStatus(state=state), artifacts=[])))
                
                mock_a2a_client.send_message.return_value = mock_response
                
                from ui_client.main import call_lead_finder_agent_a2a
                
                result = await call_lead_finder_agent_a2a("San Francisco", "test-session", niche="cafes")
                
                # Verify the call was made
                mock_a2a_client.send_message.assert_awaited_once()
                request = mock_a2a_client.send_message.call_args.args[0]
                assert request.params.message.parts[0].root.data == {"city": "San Francisco", "niche": "cafes"}
                
                assert result["success"] is success
                assert result["businesses"] == []
                assert (result["error"] is None) is success

    @pytest.mark.asyncio
    async def test_call_lead_finder_rpc_error(self):
        with patch("ui_client.main.httpx.AsyncClient") as client_class:
            client_class.return_value.__aenter__.return_value = AsyncMock()
            with patch("ui_client.main.A2AClient") as a2a_class:
                a2a = AsyncMock()
                a2a.send_message.return_value = SendMessageResponse(root=JSONRPCErrorResponse(
                    id="request", error=JSONRPCError(code=-32603, message="Provider unavailable")))
                a2a_class.return_value = a2a
                from ui_client.main import call_lead_finder_agent_a2a
                result = await call_lead_finder_agent_a2a("San Francisco", "test-session")
                assert result["success"] is False
                assert result["businesses"] == []
                assert "Provider unavailable" in result["error"]

if __name__ == "__main__":
    # Run tests if script is executed directly
    pytest.main([__file__, "-v"])
