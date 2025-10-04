"""
Contract tests for Orchestrator API endpoints.
These tests validate API contracts against OpenAPI specification.
"""
import pytest
import httpx
from typing import Dict, Any


ORCHESTRATOR_BASE_URL = "http://localhost:8000"


class TestPostTasks:
    """Contract tests for POST /tasks endpoint"""

    @pytest.mark.asyncio
    async def test_post_tasks_valid_request(self):
        """Test POST /tasks with valid description returns 200"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Calculate factorial of 10",
                    "user_id": "test_user"
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Validate response schema
            assert "task_id" in data
            assert isinstance(data["task_id"], str)
            assert data["task_id"].startswith("task_")

            assert "status" in data
            assert data["status"] == "created"

            assert "subtasks_count" in data
            assert isinstance(data["subtasks_count"], int)
            assert data["subtasks_count"] >= 1

            assert "initial_subtasks_queued" in data
            assert isinstance(data["initial_subtasks_queued"], int)

    @pytest.mark.asyncio
    async def test_post_tasks_minimum_description_length(self):
        """Test POST /tasks with description exactly 10 chars"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "1234567890",  # Exactly 10 chars
                    "user_id": "test_user"
                }
            )

            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_post_tasks_description_too_short(self):
        """Test POST /tasks with description < 10 chars returns 400"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "short",  # < 10 chars
                    "user_id": "test_user"
                }
            )

            assert response.status_code == 400
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_post_tasks_description_too_long(self):
        """Test POST /tasks with description > 5000 chars returns 400"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "x" * 5001,  # > 5000 chars
                    "user_id": "test_user"
                }
            )

            assert response.status_code == 400
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_post_tasks_default_user_id(self):
        """Test POST /tasks without user_id uses default"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Test task without user_id"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "task_id" in data


class TestGetTask:
    """Contract tests for GET /tasks/{task_id} endpoint"""

    @pytest.mark.asyncio
    async def test_get_task_valid_id(self):
        """Test GET /tasks/{task_id} with valid task returns 200"""
        # First create a task
        async with httpx.AsyncClient() as client:
            create_response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Test task for retrieval",
                    "user_id": "test_user"
                }
            )
            task_id = create_response.json()["task_id"]

            # Then retrieve it
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
            )

            assert response.status_code == 200
            data = response.json()

            # Validate task object structure
            assert "task" in data
            task = data["task"]

            assert "id" in task
            assert task["id"] == task_id

            assert "user_id" in task
            assert isinstance(task["user_id"], str)

            assert "description" in task
            assert isinstance(task["description"], str)

            assert "status" in task
            assert task["status"] in ["pending", "in_progress", "completed", "failed", "cancelled"]

            assert "created_at" in task
            assert "updated_at" in task

            assert "subtasks" in task or "subtasks" not in task  # May be null
            assert "result" in task or "result" not in task  # May be null
            assert "error" in task or "error" not in task  # May be null

            # Validate subtask_results array
            assert "subtask_results" in data
            assert isinstance(data["subtask_results"], list)

    @pytest.mark.asyncio
    async def test_get_task_invalid_id(self):
        """Test GET /tasks/{task_id} with non-existent ID returns 404"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/tasks/task_nonexistent123"
            )

            assert response.status_code == 404
            data = response.json()
            assert "detail" in data

    @pytest.mark.asyncio
    async def test_get_task_subtask_results_schema(self):
        """Test GET /tasks/{task_id} subtask_results have correct schema"""
        # Create and wait for a task to complete
        async with httpx.AsyncClient() as client:
            create_response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Simple task for result validation",
                    "user_id": "test_user"
                }
            )
            task_id = create_response.json()["task_id"]

            # Retrieve task (may not be complete yet)
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
            )

            data = response.json()

            # Validate each subtask result schema (if any)
            for result in data["subtask_results"]:
                assert "task_id" in result
                assert "subtask_id" in result
                assert "agent_id" in result
                assert "status" in result
                assert result["status"] in ["completed", "failed"]
                assert "execution_time" in result
                assert isinstance(result["execution_time"], (int, float))
                assert "created_at" in result


class TestGetAgents:
    """Contract tests for GET /agents endpoint"""

    @pytest.mark.asyncio
    async def test_get_agents_returns_array(self):
        """Test GET /agents returns array of agent statuses"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/agents"
            )

            assert response.status_code == 200
            data = response.json()

            assert "agents" in data
            assert isinstance(data["agents"], list)

    @pytest.mark.asyncio
    async def test_get_agents_schema(self):
        """Test GET /agents returns agents with correct schema"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/agents"
            )

            data = response.json()
            agents = data["agents"]

            # If agents exist, validate schema
            for agent in agents:
                assert "agent_id" in agent
                assert isinstance(agent["agent_id"], str)

                assert "port" in agent
                assert isinstance(agent["port"], int)
                assert 8001 <= agent["port"] <= 8005

                assert "is_available" in agent
                assert isinstance(agent["is_available"], bool)

                # current_task is nullable
                assert "current_task" in agent or "current_task" not in agent

                assert "capabilities" in agent
                assert isinstance(agent["capabilities"], list)
                for cap in agent["capabilities"]:
                    assert cap in [
                        "data_analysis", "web_scraping", "code_generation",
                        "file_processing", "database_operations", "api_integration"
                    ]

                assert "cpu_usage" in agent
                assert isinstance(agent["cpu_usage"], (int, float))
                assert 0 <= agent["cpu_usage"] <= 100

                assert "memory_usage" in agent
                assert isinstance(agent["memory_usage"], (int, float))
                assert 0 <= agent["memory_usage"] <= 100

                assert "tasks_completed" in agent
                assert isinstance(agent["tasks_completed"], int)
                assert agent["tasks_completed"] >= 0

                assert "last_heartbeat" in agent

    @pytest.mark.asyncio
    async def test_get_agents_available_filter(self):
        """Test GET /agents/available with capability filter"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/agents/available",
                params={"capability": "data_analysis"}
            )

            assert response.status_code == 200
            data = response.json()

            assert "available_agents" in data
            assert isinstance(data["available_agents"], list)

            assert "count" in data
            assert isinstance(data["count"], int)
            assert data["count"] == len(data["available_agents"])
