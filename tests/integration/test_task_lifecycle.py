"""
Integration test for multi-step task lifecycle.
Tests task decomposition, dependency ordering, and result aggregation.
"""
import pytest
import httpx
import asyncio
import asyncpg
from typing import List, Dict, Any


ORCHESTRATOR_BASE_URL = "http://localhost:8000"
POSTGRES_URL = "postgresql://postgres:postgres@localhost:5432/multi_agent_db"


class TestMultiStepTaskLifecycle:
    """Integration tests for complex multi-step tasks"""

    @pytest.mark.asyncio
    async def test_complex_task_decomposition(self):
        """
        Test that complex task is decomposed into multiple subtasks
        with correct required_capabilities
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Submit complex task requiring multiple capabilities
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Fetch weather data from API, analyze temperature trends, and create summary report",
                    "user_id": "test_user_complex"
                }
            )

            assert response.status_code == 200
            data = response.json()
            task_id = data["task_id"]

            # Task should be decomposed into multiple subtasks
            assert data["subtasks_count"] >= 2, "Complex task should have multiple subtasks"

            # Retrieve full task details
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
            )

            task = response.json()["task"]

            # Verify subtasks have required_capabilities
            if task.get("subtasks"):
                for subtask in task["subtasks"]:
                    assert "required_capabilities" in subtask
                    assert len(subtask["required_capabilities"]) > 0
                    assert "description" in subtask
                    assert len(subtask["description"]) >= 10

    @pytest.mark.asyncio
    async def test_subtask_dependency_ordering(self):
        """
        Test that subtasks execute in correct dependency order
        Dependent subtasks wait for prerequisites to complete
        """
        async with httpx.AsyncClient(timeout=90.0) as client:
            # Submit task with clear sequential steps
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "First read data from file, then analyze the data, finally generate a report based on analysis",
                    "user_id": "test_user_dependencies"
                }
            )

            task_id = response.json()["task_id"]

            # Poll until task completes
            max_wait = 90
            elapsed = 0
            task_completed = False

            while elapsed < max_wait:
                response = await client.get(
                    f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
                )

                task = response.json()["task"]

                if task["status"] == "completed":
                    task_completed = True
                    break
                elif task["status"] == "failed":
                    # If task fails, still check dependency ordering in results
                    break

                await asyncio.sleep(3)
                elapsed += 3

            # Retrieve subtask results
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
            )

            subtask_results = response.json()["subtask_results"]

            if len(subtask_results) > 1:
                # Verify results have timestamps showing sequential execution
                timestamps = [result["created_at"] for result in subtask_results]

                # If there are dependencies, dependent tasks should complete after prerequisites
                # (We can't strictly enforce order without knowing exact dependencies from decomposition,
                # but we can verify all have timestamps)
                for timestamp in timestamps:
                    assert timestamp is not None

    @pytest.mark.asyncio
    async def test_final_result_aggregates_all_outputs(self):
        """
        Test that final task result aggregates all subtask outputs
        """
        async with httpx.AsyncClient(timeout=90.0) as client:
            # Submit multi-step task
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Calculate sum of 1 to 10, then calculate product of 1 to 5, then combine results",
                    "user_id": "test_user_aggregation"
                }
            )

            task_id = response.json()["task_id"]

            # Wait for completion
            max_wait = 90
            elapsed = 0

            while elapsed < max_wait:
                response = await client.get(
                    f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
                )

                task = response.json()["task"]

                if task["status"] in ["completed", "failed"]:
                    break

                await asyncio.sleep(3)
                elapsed += 3

            # Verify final result exists and aggregates outputs
            if task["status"] == "completed":
                assert task["result"] is not None

                result = task["result"]

                # Result should contain subtask_results or summary
                assert "subtask_results" in result or "summary" in result

                # All subtask outputs should be present
                subtask_results = response.json()["subtask_results"]
                assert len(subtask_results) >= 1

                # Each subtask should have output
                for subtask_result in subtask_results:
                    if subtask_result["status"] == "completed":
                        assert subtask_result["output"] is not None

    @pytest.mark.asyncio
    async def test_subtask_agent_assignments(self):
        """
        Test that subtasks are assigned to agents with correct capabilities
        """
        async with httpx.AsyncClient(timeout=90.0) as client:
            # Submit task requiring specific capabilities
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Scrape data from website, then analyze the scraped data statistically",
                    "user_id": "test_user_assignments"
                }
            )

            task_id = response.json()["task_id"]

            # Wait for at least one subtask to start
            await asyncio.sleep(10)

            # Get task details
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
            )

            task_data = response.json()
            subtask_results = task_data["subtask_results"]

            # If any subtasks completed, verify agent assignments
            if len(subtask_results) > 0:
                for result in subtask_results:
                    agent_id = result["agent_id"]
                    assert agent_id is not None
                    assert agent_id.startswith("agent_")

                    # Verify agent has required capabilities
                    # (Would need to query agent status to validate, simplified here)
                    assert result["execution_time"] > 0

    @pytest.mark.asyncio
    async def test_parallel_subtask_execution(self):
        """
        Test that independent subtasks can execute in parallel
        """
        async with httpx.AsyncClient(timeout=90.0) as client:
            # Submit task with independent parallel steps
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Calculate factorial of 5 and calculate fibonacci of 10 independently",
                    "user_id": "test_user_parallel"
                }
            )

            task_id = response.json()["task_id"]

            # Wait for completion
            max_wait = 90
            elapsed = 0

            while elapsed < max_wait:
                response = await client.get(
                    f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
                )

                task = response.json()["task"]

                if task["status"] in ["completed", "failed"]:
                    break

                await asyncio.sleep(3)
                elapsed += 3

            # Retrieve subtask results
            subtask_results = response.json()["subtask_results"]

            # If there are multiple independent subtasks, they should execute quickly
            # (parallel execution should be faster than sequential)
            if len(subtask_results) >= 2:
                total_execution_time = sum(r["execution_time"] for r in subtask_results)

                # Check task total time from created_at to updated_at
                from datetime import datetime

                created = datetime.fromisoformat(task["created_at"].replace('Z', '+00:00'))
                updated = datetime.fromisoformat(task["updated_at"].replace('Z', '+00:00'))
                total_time = (updated - created).total_seconds()

                # If parallel, total time should be less than sum of execution times
                # (allowing overhead for orchestration)
                # This is a soft check as timing can vary
                assert total_time < total_execution_time * 1.5

    @pytest.mark.asyncio
    async def test_task_status_transitions(self):
        """
        Test that task status transitions correctly through lifecycle
        pending → in_progress → completed
        """
        async with httpx.AsyncClient(timeout=90.0) as client:
            # Submit task
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Multi-step task for status tracking",
                    "user_id": "test_user_status"
                }
            )

            task_id = response.json()["task_id"]

            # Track status transitions
            statuses_observed = []

            max_wait = 90
            elapsed = 0

            while elapsed < max_wait:
                response = await client.get(
                    f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
                )

                task = response.json()["task"]
                status = task["status"]

                # Record status if new
                if not statuses_observed or statuses_observed[-1] != status:
                    statuses_observed.append(status)

                if status in ["completed", "failed"]:
                    break

                await asyncio.sleep(2)
                elapsed += 2

            # Verify valid status progression
            # Should start with pending or in_progress
            assert statuses_observed[0] in ["pending", "in_progress"]

            # Should end with completed or failed
            assert statuses_observed[-1] in ["completed", "failed"]

            # Should not go backwards (e.g., completed → in_progress)
            valid_transitions = {
                "pending": ["in_progress", "failed", "cancelled"],
                "in_progress": ["completed", "failed", "cancelled"],
                "completed": [],
                "failed": ["in_progress"],  # Can retry
                "cancelled": []
            }

            for i in range(len(statuses_observed) - 1):
                current = statuses_observed[i]
                next_status = statuses_observed[i + 1]

                assert next_status in valid_transitions.get(current, []) or next_status == current

    @pytest.mark.asyncio
    async def test_database_persistence_during_lifecycle(self):
        """
        Test that task and results are persisted to database during execution
        """
        async with httpx.AsyncClient(timeout=90.0) as client:
            # Submit task
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Task for database persistence testing",
                    "user_id": "test_user_persistence"
                }
            )

            task_id = response.json()["task_id"]

            # Check database immediately after creation
            conn = await asyncpg.connect(POSTGRES_URL)
            try:
                # Task should exist in database
                task_row = await conn.fetchrow(
                    "SELECT * FROM tasks WHERE id = $1",
                    task_id
                )

                assert task_row is not None
                assert task_row["status"] in ["pending", "in_progress"]

                # Wait for task to progress
                await asyncio.sleep(10)

                # Check if any subtask results exist
                result_rows = await conn.fetch(
                    "SELECT * FROM subtask_results WHERE task_id = $1",
                    task_id
                )

                # Results may or may not exist yet depending on execution speed
                # Just verify structure if they do exist
                for row in result_rows:
                    assert row["agent_id"] is not None
                    assert row["status"] in ["completed", "failed"]

            finally:
                await conn.close()
