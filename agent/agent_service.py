"""
Agent service powered by Claude AI.
Each agent executes subtasks using AI capabilities.
"""
import asyncio
import os
import psutil
import time
from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from shared.models import (
    TaskExecutionRequest, SubTaskResult, AgentStatus,
    AgentCapability, TaskStatus
)
from shared.redis_manager import redis_manager
from shared.config import settings
from shared.auth_client import HybridClaudeClient, AuthConfig


async def save_result_html(
    task_id: str,
    subtask_id: str,
    agent_id: str,
    html_content: str,
    execution_time: float
) -> str:
    """
    Save agent result as HTML file in task-specific directory.

    Returns:
        Relative path to the saved HTML file
    """
    # Create task directory with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    task_dir = Path("results") / f"{task_id}_{timestamp}"
    task_dir.mkdir(parents=True, exist_ok=True)

    # Create HTML file for this subtask
    filename = f"{subtask_id}_{agent_id}.html"
    html_file = task_dir / filename

    # Wrap content in full HTML document if not already wrapped
    if not html_content.strip().lower().startswith("<!doctype") and not html_content.strip().lower().startswith("<html"):
        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Task Result - {subtask_id}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .content {{
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1, h2, h3 {{ color: #333; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #667eea;
            color: white;
        }}
        pre {{
            background: #f4f4f4;
            padding: 15px;
            border-radius: 4px;
            overflow-x: auto;
        }}
        code {{
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: 'Courier New', monospace;
        }}
        .metadata {{
            font-size: 0.9em;
            color: #666;
            margin-top: 10px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Agent Task Result</h1>
        <div class="metadata">
            <strong>Task ID:</strong> {task_id}<br>
            <strong>Subtask ID:</strong> {subtask_id}<br>
            <strong>Agent:</strong> {agent_id}<br>
            <strong>Execution Time:</strong> {execution_time:.2f}s<br>
            <strong>Timestamp:</strong> {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </div>
    <div class="content">
        {html_content}
    </div>
</body>
</html>"""
    else:
        full_html = html_content

    # Write HTML file
    html_file.write_text(full_html, encoding='utf-8')

    # Return relative path (convert to string to avoid path resolution issues)
    return str(task_dir / filename).replace('\\', '/')



# Agent state
class AgentState:
    def __init__(self):
        self.is_busy = False
        self.current_task_id = None
        self.tasks_completed = 0


agent_state = AgentState()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    # Startup
    print(f"[Agent {settings.AGENT_ID}] Starting up on port {settings.AGENT_PORT}...")
    await redis_manager.connect()

    # Register agent
    await redis_manager.register_agent(settings.AGENT_ID)

    # Start heartbeat
    asyncio.create_task(send_heartbeat())

    print(f"[Agent {settings.AGENT_ID}] Ready")

    yield

    # Shutdown
    print(f"[Agent {settings.AGENT_ID}] Shutting down...")
    await redis_manager.disconnect()


# Create FastAPI app
app = FastAPI(
    title=f"Agent {settings.AGENT_ID}",
    version="1.0.0",
    lifespan=lifespan
)

# Claude client
# Initialize HybridClaudeClient for automatic auth detection
claude_client = HybridClaudeClient(
    config=AuthConfig(
        model=settings.CLAUDE_MODEL,
        max_tokens=4096,
        temperature=0.0
    )
)


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "agent_id": settings.AGENT_ID,
        "is_available": not agent_state.is_busy,
        "current_task": agent_state.current_task_id,
        "sdk_version": "claude-agent-sdk-1.0-mock"
    }


@app.get("/status")
async def get_status():
    """Get detailed agent status"""
    # Get capabilities from environment
    caps_str = settings.AGENT_CAPABILITIES
    capabilities = [AgentCapability(cap.strip()) for cap in caps_str.split(",")]

    # Get system metrics
    cpu_usage = psutil.cpu_percent(interval=0.1)
    memory = psutil.virtual_memory()

    return {
        "agent_id": settings.AGENT_ID,
        "port": settings.AGENT_PORT,
        "is_available": not agent_state.is_busy,
        "current_task": agent_state.current_task_id,
        "capabilities": [cap.value for cap in capabilities],
        "cpu_usage": cpu_usage,
        "memory_usage": memory.percent,
        "tasks_completed": agent_state.tasks_completed
    }


@app.post("/execute")
async def execute_subtask(request: TaskExecutionRequest):
    """
    Execute a subtask using Claude AI.
    Runs in background and enqueues result when complete.
    """
    if agent_state.is_busy:
        raise HTTPException(status_code=503, detail="Agent busy")

    # Mark as busy
    agent_state.is_busy = True
    agent_state.current_task_id = request.subtask.id

    # Execute in background
    asyncio.create_task(execute_task_async(request))

    return {
        "status": "accepted",
        "agent_id": settings.AGENT_ID
    }


async def execute_task_async(request: TaskExecutionRequest):
    """Execute subtask asynchronously"""
    start_time = time.time()

    try:
        print(f"[Agent {settings.AGENT_ID}] Executing {request.subtask.id}: {request.subtask.description}")

        # Check for attached files
        files_info = ""
        if request.task_context and request.task_context.get('attachments'):
            from shared.file_storage import file_storage
            files_list = []
            for att in request.task_context['attachments']:
                file_info = file_storage.get_file_info(att['file_path'])
                files_list.append(
                    f"  - {att['filename']} ({file_info.get('size_mb', 0)}MB, {att['mime_type']})\n"
                    f"    Path: {att['file_path']}"
                )

            if files_list:
                files_info = f"\n\nAttached Files:\n" + "\n".join(files_list)

        # Build prompt for Claude with HTML output requirement
        prompt = f"""You are an AI agent with the following capabilities:
{', '.join([cap.value for cap in request.subtask.required_capabilities])}

Execute this task:
{request.subtask.description}

Context from previous tasks:
{request.task_context.get('previous_results', 'None') if request.task_context else 'None'}{files_info}

IMPORTANT: Provide your response in well-formatted HTML. Structure your response as:
1. A summary section with key findings
2. Detailed results with proper headings
3. If applicable, include tables, lists, or code blocks
4. Use semantic HTML (h1, h2, p, ul, ol, table, pre, code)

Your HTML should be complete and ready to display in a web browser."""

        # Call Claude via HybridClaudeClient
        result_text = await claude_client.query(prompt)

        execution_time = time.time() - start_time

        # Save result as HTML file
        html_path = await save_result_html(
            task_id=request.task_id,
            subtask_id=request.subtask.id,
            agent_id=settings.AGENT_ID,
            html_content=result_text,
            execution_time=execution_time
        )

        # Create result
        result = SubTaskResult(
            task_id=request.task_id,
            subtask_id=request.subtask.id,
            agent_id=settings.AGENT_ID,
            status=TaskStatus.COMPLETED,
            output={
                "success": True,
                "result": result_text,
                "html_file": html_path,
                "summary": f"Completed by {settings.AGENT_ID}"
            },
            error=None,
            execution_time=execution_time
        )

        # Enqueue result
        await redis_manager.enqueue_result(result)

        print(f"[Agent {settings.AGENT_ID}] Completed {request.subtask.id} in {execution_time:.2f}s")

        # Update state
        agent_state.tasks_completed += 1

    except Exception as e:
        print(f"[Agent {settings.AGENT_ID}] Error executing {request.subtask.id}: {e}")

        execution_time = time.time() - start_time

        # Create error result
        result = SubTaskResult(
            task_id=request.task_id,
            subtask_id=request.subtask.id,
            agent_id=settings.AGENT_ID,
            status=TaskStatus.FAILED,
            output=None,
            error=str(e),
            execution_time=execution_time
        )

        # Enqueue error result
        await redis_manager.enqueue_result(result)

    finally:
        # Mark as available
        agent_state.is_busy = False
        agent_state.current_task_id = None


async def send_heartbeat():
    """Send periodic heartbeat to Redis"""
    while True:
        try:
            # Get capabilities
            caps_str = settings.AGENT_CAPABILITIES
            capabilities = [AgentCapability(cap.strip()) for cap in caps_str.split(",")]

            # Get system metrics
            cpu_usage = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()

            # Create status
            status = AgentStatus(
                agent_id=settings.AGENT_ID,
                port=settings.AGENT_PORT,
                is_available=not agent_state.is_busy,
                current_task=agent_state.current_task_id,
                capabilities=capabilities,
                cpu_usage=cpu_usage,
                memory_usage=memory.percent,
                tasks_completed=agent_state.tasks_completed
            )

            # Update in Redis
            await redis_manager.update_agent_status(status)

        except Exception as e:
            print(f"[Agent {settings.AGENT_ID}] Heartbeat error: {e}")

        await asyncio.sleep(10)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("AGENT_PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
