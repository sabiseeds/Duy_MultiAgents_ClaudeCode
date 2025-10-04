"""
Central orchestrator service for the Multi-Agent Task Execution System.
Coordinates task submission, agent assignment, and result aggregation.
"""
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Optional

from shared.models import Task, TaskStatus, SubTaskResult, AgentCapability
from shared.database import db_manager
from shared.redis_manager import redis_manager
from shared.config import settings
from orchestrator.task_analyzer import TaskAnalyzer


# Background tasks flag
background_tasks_running = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    global background_tasks_running

    # Startup
    print("[Orchestrator] Starting up...")
    await db_manager.connect()
    await redis_manager.connect()

    # Start background workers
    background_tasks_running = True
    asyncio.create_task(dispatch_tasks())
    asyncio.create_task(process_results())

    print("[Orchestrator] Ready to accept requests")

    yield

    # Shutdown
    print("[Orchestrator] Shutting down...")
    background_tasks_running = False
    await db_manager.disconnect()
    await redis_manager.disconnect()


# Create FastAPI app
app = FastAPI(
    title="Multi-Agent Orchestrator",
    version="1.0.0",
    lifespan=lifespan
)

# Task analyzer instance
task_analyzer = TaskAnalyzer()


@app.post("/tasks")
async def create_task(
    description: str = Query(..., min_length=10, max_length=5000),
    user_id: str = Query(default="default_user")
):
    """
    Create and submit a new task.
    Decomposes task into subtasks and queues them for execution.
    """
    try:
        # Decompose task using Claude AI
        subtasks = await task_analyzer.decompose_task(description)

        # Create task object
        task = Task(
            user_id=user_id,
            description=description,
            status=TaskStatus.PENDING,
            subtasks=subtasks
        )

        # Save to database
        await db_manager.create_task(task)

        # Queue subtasks with no dependencies
        queued_count = 0
        for subtask in subtasks:
            if not subtask.dependencies:
                await redis_manager.enqueue_task(
                    task_id=task.id,
                    subtask=subtask,
                    context={}
                )
                queued_count += 1

        # Update task status if any subtasks queued
        if queued_count > 0:
            await db_manager.update_task_status(task.id, TaskStatus.IN_PROGRESS)

        return {
            "task_id": task.id,
            "status": "created",
            "subtasks_count": len(subtasks),
            "initial_subtasks_queued": queued_count
        }

    except Exception as e:
        print(f"[Orchestrator] Error creating task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tasks/{task_id}")
async def get_task(task_id: str):
    """
    Get task status and results.
    Returns full task details including subtask results.
    """
    task = await db_manager.get_task(task_id)

    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Get subtask results
    subtask_results = await db_manager.get_subtask_results(task_id)

    return {
        "task": {
            "id": task.id,
            "user_id": task.user_id,
            "description": task.description,
            "status": task.status.value,
            "created_at": task.created_at.isoformat(),
            "updated_at": task.updated_at.isoformat(),
            "subtasks": [st.model_dump() for st in task.subtasks] if task.subtasks else [],
            "result": task.result,
            "error": task.error
        },
        "subtask_results": [
            {
                "task_id": sr.task_id,
                "subtask_id": sr.subtask_id,
                "agent_id": sr.agent_id,
                "status": sr.status.value,
                "output": sr.output,
                "error": sr.error,
                "execution_time": sr.execution_time,
                "created_at": sr.created_at.isoformat()
            }
            for sr in subtask_results
        ]
    }


@app.get("/agents")
async def get_agents():
    """
    Get all registered agents.
    Returns status of all active agents.
    """
    agents = await redis_manager.get_all_agents()

    return {
        "agents": [
            {
                "agent_id": agent.agent_id,
                "port": agent.port,
                "is_available": agent.is_available,
                "current_task": agent.current_task,
                "capabilities": [cap.value for cap in agent.capabilities],
                "cpu_usage": agent.cpu_usage,
                "memory_usage": agent.memory_usage,
                "tasks_completed": agent.tasks_completed,
                "last_heartbeat": agent.last_heartbeat.isoformat()
            }
            for agent in agents
        ]
    }


@app.get("/agents/available")
async def get_available_agents(
    capability: Optional[str] = Query(default=None)
):
    """
    Get available agents, optionally filtered by capability.
    """
    cap = AgentCapability(capability) if capability else None
    available = await redis_manager.get_available_agents(cap)

    return {
        "available_agents": available,
        "count": len(available)
    }


# Background worker: dispatch tasks to agents
async def dispatch_tasks():
    """
    Background worker that assigns queued subtasks to available agents.
    Runs continuously, checking for ready tasks and available agents.
    """
    global background_tasks_running
    print("[Orchestrator] Dispatch worker started")

    while background_tasks_running:
        try:
            # Dequeue a task (non-blocking check)
            task_data = await redis_manager.dequeue_task(timeout=1)

            if not task_data:
                await asyncio.sleep(1)
                continue

            task_id = task_data["task_id"]
            from shared.models import SubTask
            subtask = SubTask(**task_data["subtask"])
            context = task_data["context"]

            # Find available agent with required capabilities
            for cap in subtask.required_capabilities:
                available_agents = await redis_manager.get_available_agents(cap)

                if available_agents:
                    agent_id = available_agents[0]

                    # Get agent details
                    agent_status = await redis_manager.get_agent_status(agent_id)
                    if not agent_status:
                        continue

                    # Send task to agent
                    try:
                        async with httpx.AsyncClient(timeout=10.0) as client:
                            response = await client.post(
                                f"http://localhost:{agent_status.port}/execute",
                                json={
                                    "task_id": task_id,
                                    "subtask": subtask.model_dump(),
                                    "task_context": context
                                }
                            )

                            if response.status_code == 200:
                                print(f"[Orchestrator] Assigned {subtask.id} to {agent_id}")
                                # Mark agent as busy
                                agent_status.is_available = False
                                agent_status.current_task = subtask.id
                                await redis_manager.update_agent_status(agent_status)
                                break
                            else:
                                print(f"[Orchestrator] Agent {agent_id} rejected task: {response.status_code}")

                    except Exception as e:
                        print(f"[Orchestrator] Error assigning to {agent_id}: {e}")
                        continue

            else:
                # No agent available, re-queue
                await redis_manager.enqueue_task(task_id, subtask, context)
                await asyncio.sleep(2)

        except Exception as e:
            print(f"[Orchestrator] Dispatch error: {e}")
            await asyncio.sleep(1)

    print("[Orchestrator] Dispatch worker stopped")


# Background worker: process completed subtask results
async def process_results():
    """
    Background worker that processes completed subtask results.
    Updates task status and queues dependent subtasks.
    """
    global background_tasks_running
    print("[Orchestrator] Results processor started")

    while background_tasks_running:
        try:
            # Dequeue result (non-blocking check)
            result = await redis_manager.dequeue_result(timeout=1)

            if not result:
                await asyncio.sleep(0.5)
                continue

            print(f"[Orchestrator] Processing result for {result.subtask_id}")

            # Save result to database
            await db_manager.save_subtask_result(result)

            # Get task to check completion
            task = await db_manager.get_task(result.task_id)
            if not task or not task.subtasks:
                continue

            # Get all results for this task
            all_results = await db_manager.get_subtask_results(result.task_id)
            completed_subtask_ids = {r.subtask_id for r in all_results}

            # Check if all subtasks completed
            all_complete = all(st.id in completed_subtask_ids for st in task.subtasks)

            if all_complete:
                # Aggregate results
                aggregated = {
                    "subtask_results": [
                        {
                            "subtask_id": r.subtask_id,
                            "agent_id": r.agent_id,
                            "status": r.status.value,
                            "output": r.output,
                            "execution_time": r.execution_time
                        }
                        for r in all_results
                    ],
                    "summary": f"Completed {len(all_results)} subtasks"
                }

                # Check if any failed
                any_failed = any(r.status == TaskStatus.FAILED for r in all_results)
                final_status = TaskStatus.FAILED if any_failed else TaskStatus.COMPLETED

                await db_manager.update_task_status(
                    result.task_id,
                    final_status,
                    result=aggregated if not any_failed else None,
                    error="Some subtasks failed" if any_failed else None
                )

                print(f"[Orchestrator] Task {result.task_id} {final_status.value}")

            else:
                # Check for newly ready subtasks (dependencies satisfied)
                for subtask in task.subtasks:
                    if subtask.id in completed_subtask_ids:
                        continue

                    # Check if all dependencies completed
                    deps_satisfied = all(dep in completed_subtask_ids for dep in subtask.dependencies)

                    if deps_satisfied:
                        # Build context from dependency results
                        dep_context = {
                            dep: next((r.output for r in all_results if r.subtask_id == dep), None)
                            for dep in subtask.dependencies
                        }

                        # Enqueue subtask
                        await redis_manager.enqueue_task(
                            task_id=result.task_id,
                            subtask=subtask,
                            context=dep_context
                        )
                        print(f"[Orchestrator] Queued dependent subtask {subtask.id}")

            # Update agent status to available
            agent_status = await redis_manager.get_agent_status(result.agent_id)
            if agent_status:
                agent_status.is_available = True
                agent_status.current_task = None
                agent_status.tasks_completed += 1
                await redis_manager.update_agent_status(agent_status)

        except Exception as e:
            print(f"[Orchestrator] Results processing error: {e}")
            await asyncio.sleep(0.5)

    print("[Orchestrator] Results processor stopped")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
