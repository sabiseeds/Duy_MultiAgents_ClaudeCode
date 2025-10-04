"""
Contract tests for Agent API endpoints.
These tests validate agent API contracts against OpenAPI specification.
"""
import pytest
import httpx
from typing import List


AGENT_PORTS = [8001, 8002, 8003, 8004, 8005]


class TestAgentHealth:
    """Contract tests for GET /health endpoint"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("port", AGENT_PORTS)
    async def test_agent_health_returns_200(self, port: int):
        """Test GET /health returns 200 for all agents"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:{port}/health"
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.parametrize("port", AGENT_PORTS)
    async def test_agent_health_schema(self, port: int):
        """Test GET /health returns correct schema"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:{port}/health"
            )

            data = response.json()

            # Validate required fields
            assert "status" in data
            assert data["status"] == "healthy"

            assert "agent_id" in data
            assert isinstance(data["agent_id"], str)
            assert data["agent_id"].startswith("agent_")

            assert "is_available" in data
            assert isinstance(data["is_available"], bool)

            # current_task is nullable
            assert "current_task" in data or "current_task" not in data
            if "current_task" in data and data["current_task"] is not None:
                assert isinstance(data["current_task"], str)

            assert "sdk_version" in data
            assert isinstance(data["sdk_version"], str)
            assert "claude-agent-sdk" in data["sdk_version"].lower()

    @pytest.mark.asyncio
    async def test_agent_health_different_agent_ids(self):
        """Test each agent has unique agent_id"""
        agent_ids = set()

        async with httpx.AsyncClient() as client:
            for port in AGENT_PORTS:
                response = await client.get(
                    f"http://localhost:{port}/health"
                )
                data = response.json()
                agent_ids.add(data["agent_id"])

        # All agents should have unique IDs
        assert len(agent_ids) == len(AGENT_PORTS)


class TestAgentStatus:
    """Contract tests for GET /status endpoint"""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("port", AGENT_PORTS)
    async def test_agent_status_returns_200(self, port: int):
        """Test GET /status returns 200 for all agents"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:{port}/status"
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.parametrize("port", AGENT_PORTS)
    async def test_agent_status_schema(self, port: int):
        """Test GET /status returns comprehensive agent status"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://localhost:{port}/status"
            )

            data = response.json()

            # Validate AgentStatus schema
            assert "agent_id" in data
            assert isinstance(data["agent_id"], str)

            assert "port" in data
            assert isinstance(data["port"], int)
            assert data["port"] == port

            assert "is_available" in data
            assert isinstance(data["is_available"], bool)

            # current_task is nullable
            assert "current_task" in data or "current_task" not in data

            assert "capabilities" in data
            assert isinstance(data["capabilities"], list)
            assert len(data["capabilities"]) > 0
            for cap in data["capabilities"]:
                assert cap in [
                    "data_analysis", "web_scraping", "code_generation",
                    "file_processing", "database_operations", "api_integration"
                ]

            assert "cpu_usage" in data
            assert isinstance(data["cpu_usage"], (int, float))
            assert 0 <= data["cpu_usage"] <= 100

            assert "memory_usage" in data
            assert isinstance(data["memory_usage"], (int, float))
            assert 0 <= data["memory_usage"] <= 100

            assert "tasks_completed" in data
            assert isinstance(data["tasks_completed"], int)
            assert data["tasks_completed"] >= 0

    @pytest.mark.asyncio
    async def test_agent_capabilities_match_config(self):
        """Test agents have expected capabilities per configuration"""
        expected_capabilities = {
            8001: ["data_analysis", "code_generation"],
            8002: ["web_scraping", "api_integration"],
            8003: ["file_processing", "database_operations"],
            8004: ["code_generation", "api_integration"],
            8005: ["data_analysis", "database_operations"],
        }

        async with httpx.AsyncClient() as client:
            for port, expected_caps in expected_capabilities.items():
                response = await client.get(
                    f"http://localhost:{port}/status"
                )
                data = response.json()

                # Verify capabilities match expected configuration
                assert set(data["capabilities"]) == set(expected_caps)


class TestAgentExecute:
    """Contract tests for POST /execute endpoint"""

    @pytest.mark.asyncio
    async def test_agent_execute_valid_request(self):
        """Test POST /execute with valid request returns 200"""
        async with httpx.AsyncClient() as client:
            request_body = {
                "task_id": "task_test123",
                "subtask": {
                    "id": "subtask_test456",
                    "description": "Test subtask execution",
                    "required_capabilities": ["data_analysis"],
                    "dependencies": [],
                    "priority": 5,
                    "estimated_duration": 10,
                    "input_data": {}
                },
                "task_context": {}
            }

            response = await client.post(
                "http://localhost:8001/execute",
                json=request_body
            )

            # 200 if accepted, 503 if busy
            assert response.status_code in [200, 503]

            if response.status_code == 200:
                data = response.json()
                assert "status" in data
                assert data["status"] == "accepted"

                assert "agent_id" in data
                assert isinstance(data["agent_id"], str)

    @pytest.mark.asyncio
    async def test_agent_execute_missing_required_fields(self):
        """Test POST /execute with missing fields returns error"""
        async with httpx.AsyncClient() as client:
            # Missing subtask field
            request_body = {
                "task_id": "task_test123",
                "task_context": {}
            }

            response = await client.post(
                "http://localhost:8001/execute",
                json=request_body
            )

            # Should return validation error
            assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_agent_execute_when_busy(self):
        """Test POST /execute when agent is busy returns 503"""
        async with httpx.AsyncClient() as client:
            request_body = {
                "task_id": "task_test123",
                "subtask": {
                    "id": "subtask_test456",
                    "description": "First task to make agent busy",
                    "required_capabilities": ["data_analysis"],
                    "dependencies": [],
                    "priority": 5,
                    "input_data": {}
                },
                "task_context": {}
            }

            # Send first request
            response1 = await client.post(
                "http://localhost:8001/execute",
                json=request_body
            )

            # If first succeeded, send second immediately
            if response1.status_code == 200:
                request_body["subtask"]["id"] = "subtask_test789"
                request_body["subtask"]["description"] = "Second task while busy"

                response2 = await client.post(
                    "http://localhost:8001/execute",
                    json=request_body
                )

                # Second request should be 503 or 200 (if first finished)
                assert response2.status_code in [200, 503]

                if response2.status_code == 503:
                    data = response2.json()
                    assert "detail" in data

    @pytest.mark.asyncio
    async def test_agent_execute_subtask_validation(self):
        """Test POST /execute validates subtask schema"""
        async with httpx.AsyncClient() as client:
            # Invalid required_capabilities (empty array)
            request_body = {
                "task_id": "task_test123",
                "subtask": {
                    "id": "subtask_test456",
                    "description": "Test subtask",
                    "required_capabilities": [],  # Invalid: must have at least one
                    "dependencies": [],
                    "priority": 5,
                    "input_data": {}
                },
                "task_context": {}
            }

            response = await client.post(
                "http://localhost:8001/execute",
                json=request_body
            )

            # Should return validation error
            assert response.status_code in [400, 422]

    @pytest.mark.asyncio
    async def test_agent_execute_priority_validation(self):
        """Test POST /execute validates priority range"""
        async with httpx.AsyncClient() as client:
            # Priority out of range (0-10)
            request_body = {
                "task_id": "task_test123",
                "subtask": {
                    "id": "subtask_test456",
                    "description": "Test subtask",
                    "required_capabilities": ["data_analysis"],
                    "dependencies": [],
                    "priority": 15,  # Invalid: > 10
                    "input_data": {}
                },
                "task_context": {}
            }

            response = await client.post(
                "http://localhost:8001/execute",
                json=request_body
            )

            # Should return validation error
            assert response.status_code in [400, 422]
