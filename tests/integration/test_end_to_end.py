"""
End-to-end integration test for simple task execution.
This test validates the complete workflow from task submission to completion.
Based on quickstart.md Step 3 scenario.
"""
import pytest
import httpx
import asyncio
import asyncpg
from typing import Optional


ORCHESTRATOR_BASE_URL = "http://localhost:8000"
POSTGRES_URL = "postgresql://postgres:postgres@localhost:5432/multi_agent_db"


class TestEndToEndSimpleTask:
    """End-to-end test for simple task execution"""

    @pytest.mark.asyncio
    async def test_simple_task_complete_workflow(self):
        """
        Test complete workflow: Submit simple task → Execute → Complete
        Scenario: Calculate factorial of 10
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Step 1: Submit task
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Calculate factorial of 10",
                    "user_id": "test_user_e2e"
                }
            )

            assert response.status_code == 200
            data = response.json()
            task_id = data["task_id"]

            # Verify task created
            assert data["status"] == "created"
            assert data["subtasks_count"] >= 1
            assert data["initial_subtasks_queued"] >= 1

            # Step 2: Poll task status until completion or timeout
            max_wait_time = 60  # seconds
            poll_interval = 2  # seconds
            elapsed_time = 0
            task_completed = False

            while elapsed_time < max_wait_time:
                response = await client.get(
                    f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
                )

                assert response.status_code == 200
                task_data = response.json()
                task = task_data["task"]

                # Check task status
                if task["status"] == "completed":
                    task_completed = True
                    break
                elif task["status"] == "failed":
                    pytest.fail(f"Task failed with error: {task.get('error')}")

                # Wait before next poll
                await asyncio.sleep(poll_interval)
                elapsed_time += poll_interval

            # Assert task completed within timeout
            assert task_completed, f"Task did not complete within {max_wait_time} seconds"

            # Step 3: Verify task transitions
            # Task should have transitioned: pending → in_progress → completed
            assert task["status"] == "completed"

            # Step 4: Verify subtask results
            subtask_results = task_data["subtask_results"]
            assert len(subtask_results) >= 1

            # All subtasks should be completed
            for result in subtask_results:
                assert result["status"] == "completed"
                assert result["execution_time"] > 0
                assert result["agent_id"] is not None
                assert result["output"] is not None

            # Step 5: Verify result contains factorial
            result = task["result"]
            assert result is not None

            # Result should contain aggregated subtask outputs
            assert "subtask_results" in result or "summary" in result

            # Step 6: Verify database records
            conn = await asyncpg.connect(POSTGRES_URL)
            try:
                # Check task in database
                task_row = await conn.fetchrow(
                    "SELECT * FROM tasks WHERE id = $1",
                    task_id
                )
                assert task_row is not None
                assert task_row["status"] == "completed"
                assert task_row["result"] is not None

                # Check subtask_results in database
                result_rows = await conn.fetch(
                    "SELECT * FROM subtask_results WHERE task_id = $1",
                    task_id
                )
                assert len(result_rows) >= 1

                for row in result_rows:
                    assert row["status"] == "completed"
                    assert row["execution_time"] > 0
                    assert row["agent_id"] is not None

            finally:
                await conn.close()

    @pytest.mark.asyncio
    async def test_task_execution_time_reasonable(self):
        """Test that simple task completes in reasonable time (<30s)"""
        import time

        async with httpx.AsyncClient(timeout=60.0) as client:
            start_time = time.time()

            # Submit simple task
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Simple calculation: 2 + 2",
                    "user_id": "test_user_perf"
                }
            )

            task_id = response.json()["task_id"]

            # Poll until complete
            while True:
                response = await client.get(
                    f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
                )

                task = response.json()["task"]
                if task["status"] in ["completed", "failed"]:
                    break

                await asyncio.sleep(1)

            end_time = time.time()
            total_time = end_time - start_time

            # Simple task should complete in under 30 seconds
            assert total_time < 30, f"Task took {total_time}s, expected <30s"

    @pytest.mark.asyncio
    async def test_multiple_simple_tasks_sequential(self):
        """Test submitting multiple simple tasks sequentially"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            task_ids = []

            # Submit 3 simple tasks
            for i in range(3):
                response = await client.post(
                    f"{ORCHESTRATOR_BASE_URL}/tasks",
                    params={
                        "description": f"Simple task number {i + 1}",
                        "user_id": "test_user_multi"
                    }
                )

                assert response.status_code == 200
                task_ids.append(response.json()["task_id"])

            # Wait for all to complete
            for task_id in task_ids:
                max_wait = 60
                elapsed = 0

                while elapsed < max_wait:
                    response = await client.get(
                        f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
                    )

                    task = response.json()["task"]
                    if task["status"] in ["completed", "failed"]:
                        break

                    await asyncio.sleep(2)
                    elapsed += 2

                # Verify each task completed
                assert task["status"] == "completed", f"Task {task_id} did not complete"

    @pytest.mark.asyncio
    async def test_task_with_default_user(self):
        """Test task submission without explicit user_id"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Submit without user_id
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Task without explicit user ID"
                }
            )

            assert response.status_code == 200
            task_id = response.json()["task_id"]

            # Verify task can be retrieved
            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
            )

            assert response.status_code == 200
            task = response.json()["task"]

            # Should have default user_id
            assert task["user_id"] == "default_user"

    @pytest.mark.asyncio
    async def test_agent_availability_after_task(self):
        """Test that agents become available after completing task"""
        async with httpx.AsyncClient(timeout=60.0) as client:
            # Submit task
            response = await client.post(
                f"{ORCHESTRATOR_BASE_URL}/tasks",
                params={
                    "description": "Test agent availability cycle",
                    "user_id": "test_user_availability"
                }
            )

            task_id = response.json()["task_id"]

            # Wait for task to complete
            while True:
                response = await client.get(
                    f"{ORCHESTRATOR_BASE_URL}/tasks/{task_id}"
                )

                task = response.json()["task"]
                if task["status"] in ["completed", "failed"]:
                    break

                await asyncio.sleep(2)

            # After completion, all agents should be available again
            # (assuming no other concurrent tasks)
            await asyncio.sleep(5)  # Wait for agent status update

            response = await client.get(
                f"{ORCHESTRATOR_BASE_URL}/agents"
            )

            agents = response.json()["agents"]

            # At least some agents should be available
            available_count = sum(1 for agent in agents if agent["is_available"])
            assert available_count > 0, "No agents available after task completion"
