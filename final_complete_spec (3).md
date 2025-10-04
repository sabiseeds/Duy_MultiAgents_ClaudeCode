from typing import List, Dict, Any, Set
from shared.models import SubTask, AgentCapability
import uuid
import anthropic
from shared.config import settings
import json
import re

class TaskAnalyzer:
    """Analyzes and decomposes tasks using Claude"""
    
    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    
    async def analyze_and_decompose(self, task_description: str) -> List[SubTask]:
        """
        Use Claude to analyze task and break into subtasks
        
        Returns:
            List of SubTask objects with dependencies, capabilities, priorities
        """
        
        capabilities_str = ", ".join([c.value for c in AgentCapability])
        
        prompt = f"""You are a task planning AI. Analyze and decompose this task into subtasks.

Task: {task_description}

Available agent capabilities: {capabilities_str}

For each subtask, specify:
1. description: Clear, specific description
2. required_capabilities: List of capabilities needed (from above)
3. dependencies: Array of subtask indices this depends on (0-based)
4. priority: 0-10 (10 = highest priority)
5. estimated_duration: Estimated seconds to complete

Guidelines:
- Maximize parallelization (minimize dependencies)
- Each subtask should be independently executable
- Be specific about outputs/inputs
- Consider data flow between subtasks

Respond with ONLY a JSON array:
[
  {{
    "description": "Detailed subtask description",
    "required_capabilities": ["capability1", "capability2"],
    "dependencies": [0, 1],
    "priority": 7,
    "estimated_duration": 120
  }}
]"""

        try:
            message = self.client.messages.create(
                model=settings.CLAUDE_MODEL,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Extract JSON array
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                subtasks_data = json.loads(json_match.group())
            else:
                # Fallback: single subtask
                subtasks_data = [{
                    "description": task_description,
                    "required_capabilities": ["code_generation"],
                    "dependencies": [],
                    "priority": 5,
                    "estimated_duration": 120
                }]
            
            # Convert to SubTask objects
            subtasks = []
            subtask_id_map = {}  # index -> id mapping
            
            for idx, data in enumerate(subtasks_data):
                subtask_id = f"subtask_{uuid.uuid4().hex[:8]}"
                subtask_id_map[idx] = subtask_id
                
                subtask = SubTask(
                    id=subtask_id,
                    description=data["description"],
                    required_capabilities=[
                        AgentCapability(cap) 
                        for cap in data.get("required_capabilities", ["code_generation"])
                    ],
                    dependencies=[],  # Will be filled below
                    priority=data.get("priority", 5),
                    estimated_duration=data.get("estimated_duration", 60),
                    input_data=data.get("input_data", {})
                )
                subtasks.append(subtask)
            
            # Map dependency indices to IDs
            for idx, subtask in enumerate(subtasks):
                dep_indices = subtasks_data[idx].get("dependencies", [])
                subtask.dependencies = [
                    subtask_id_map[dep_idx] 
                    for dep_idx in dep_indices 
                    if dep_idx in subtask_id_map
                ]
            
            return subtasks
            
        except Exception as e:
            print(f"Error in task decomposition: {e}")
            # Fallback: create single subtask
            return [SubTask(
                id=f"subtask_{uuid.uuid4().hex[:8]}",
                description=task_description,
                required_capabilities=[AgentCapability.CODE_GENERATION],
                dependencies=[],
                priority=5,
                estimated_duration=120
            )]
    
    def build_execution_graph(self, subtasks: List[SubTask]) -> Dict[str, List[str]]:
        """
        Build dependency graph
        
        Returns:
            Dict mapping subtask_id -> list of dependency IDs
        """
        return {st.id: st.dependencies for st in subtasks}
    
    def get_ready_subtasks(
        self, 
        subtasks: List[SubTask], 
        completed_ids: Set[str]
    ) -> List[SubTask]:
        """
        Get subtasks ready to execute (all dependencies met)
        
        Args:
            subtasks: All subtasks
            completed_ids: Set of completed subtask IDs
            
        Returns:
            List of ready subtasks, sorted by priority
        """
        ready = []
        for subtask in subtasks:
            # Check if already completed
            if subtask.id in completed_ids:
                continue
            
            # Check if all dependencies are met
            if all(dep in completed_ids for dep in subtask.dependencies):
                ready.append(subtask)
        
        # Sort by priority (higher first)
        ready.sort(key=lambda x: x.priority, reverse=True)
        return ready
```

### 3.6 Agent Service with Claude Agent SDK (`agent/agent_service.py`)

```python
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import asyncio
import time
import psutil
import sys
from typing import Optional, Dict, Any
from pathlib import Path
import json

# Claude Agent SDK imports
from claude_agent_sdk import (
    ClaudeSDKClient, 
    ClaudeAgentOptions, 
    tool, 
    create_sdk_mcp_server,
    AssistantMessage,
    TextBlock
)

from shared.models import (
    TaskExecutionRequest, SubTaskResult, TaskStatus,
    AgentRegistration, AgentCapability, AgentStatus
)
from shared.database import db_manager
from shared.redis_manager import redis_manager
from shared.config import settings
import httpx

class AgentService:
    """Agent service powered by Claude Agent SDK"""
    
    def __init__(self, agent_id: str, port: int, capabilities: list):
        self.agent_id = agent_id
        self.port = port
        self.capabilities = capabilities
        self.current_task: Optional[str] = None
        self.is_available = True
        self.tasks_completed = 0
        
        # Create MCP server with custom tools
        self.mcp_server = self._create_mcp_server()
        
        self.app = FastAPI(title=f"Agent {agent_id} (Claude SDK)")
        self._setup_routes()
    
    def _create_mcp_server(self):
        """Create MCP server with shared resource tools"""
        
        @tool("query_database", "Execute SQL query on PostgreSQL", {
            "query": str,
            "params": list
        })
        async def query_database(args):
            """Query PostgreSQL database"""
            try:
                async with db_manager.pool.acquire() as conn:
                    result = await conn.fetch(
                        args['query'], 
                        *args.get('params', [])
                    )
                    rows = [dict(row) for row in result]
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Query returned {len(rows)} rows:\n{json.dumps(rows, indent=2)}"
                    }]
                }
            except Exception as e:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Database error: {str(e)}"
                    }],
                    "isError": True
                }
        
        @tool("generate_embedding", "Generate vector embedding for text", {"text": str})
        async def generate_embedding(args):
            """Call embedding API to generate vector"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        settings.EMBEDDING_API_URL,
                        json={"text": args['text']},
                        timeout=10.0
                    )
                    result = response.json()
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Generated embedding (dim={len(result.get('embedding', []))}):\n{result}"
                    }]
                }
            except Exception as e:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Embedding API error: {str(e)}"
                    }],
                    "isError": True
                }
        
        @tool("share_data", "Share data with other agents via Redis", {
            "key": str,
            "value": dict,
            "expire_seconds": int
        })
        async def share_data(args):
            """Store data in shared state for other agents"""
            try:
                await redis_manager.set_shared_state(
                    args['key'],
                    args['value'],
                    expire=args.get('expire_seconds', 3600)
                )
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Shared data with key: {args['key']}"
                    }]
                }
            except Exception as e:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Redis error: {str(e)}"
                    }],
                    "isError": True
                }
        
        @tool("get_shared_data", "Retrieve data shared by other agents", {"key": str})
        async def get_shared_data(args):
            """Retrieve shared state from Redis"""
            try:
                value = await redis_manager.get_shared_state(args['key'])
                if value is None:
                    return {
                        "content": [{
                            "type": "text",
                            "text": f"No data found for key: {args['key']}"
                        }]
                    }
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Retrieved data:\n{json.dumps(value, indent=2)}"
                    }]
                }
            except Exception as e:
                return {
                    "content": [{
                        "type": "text",
                        "text": f"Redis error: {str(e)}"
                    }],
                    "isError": True
                }
        
        # Create and return MCP server
        return create_sdk_mcp_server(
            name=f"{self.agent_id}_tools",
            version="1.0.0",
            tools=[query_database, generate_embedding, share_data, get_shared_data]
        )
    
    def _get_agent_options(
        self, 
        subtask: SubTask, 
        context: Dict[str, Any]
    ) -> ClaudeAgentOptions:
        """Create Claude Agent SDK options for subtask execution"""
        
        # Create task-specific workspace
        task_dir = settings.SHARED_FILES_PATH / subtask.id
        task_dir.mkdir(parents=True, exist_ok=True)
        
        # Create context files
        context_dir = task_dir / "context"
        context_dir.mkdir(exist_ok=True)
        
        # Write context to files for agent to explore
        (context_dir / "task.json").write_text(
            json.dumps({
                "description": subtask.description,
                "capabilities": [c.value for c in subtask.required_capabilities],
                "priority": subtask.priority,
                "estimated_duration": subtask.estimated_duration,
                "input_data": subtask.input_data
            }, indent=2)
        )
        
        if context:
            (context_dir / "previous_results.json").write_text(
                json.dumps(context, indent=2)
            )
        
        # Create output directory
        output_dir = task_dir / "output"
        output_dir.mkdir(exist_ok=True)
        
        # Determine allowed tools based on capabilities
        allowed_tools = ["Read", "Write", "Bash"]
        
        # Add WebSearch for web scraping agents
        if AgentCapability.WEB_SCRAPING in self.capabilities:
            allowed_tools.append("WebSearch")
        
        # Add MCP tools
        mcp_tool_prefix = f"mcp__{self.agent_id}_tools__"
        allowed_tools.extend([
            f"{mcp_tool_prefix}query_database",
            f"{mcp_tool_prefix}generate_embedding",
            f"{mcp_tool_prefix}share_data",
            f"{mcp_tool_prefix}get_shared_data"
        ])
        
        # Build system prompt
        system_prompt = f"""You are {self.agent_id}, an AI agent with the following capabilities:
{chr(10).join(f'• {cap.value}' for cap in self.capabilities)}

CURRENT TASK: {subtask.description}

WORKSPACE STRUCTURE:
- Current directory: {task_dir}
- Task details: ./context/task.json
- Previous results: ./context/previous_results.json (if available)
- Output directory: ./output/ (save your results here)

AVAILABLE TOOLS:
- Read/Write: For file operations in your workspace
- Bash: For running shell commands, searching files (grep, find, etc.)
- query_database: Execute SQL queries on shared PostgreSQL database
- generate_embedding: Create vector embeddings via API
- share_data: Share results with other agents via Redis
- get_shared_data: Retrieve data from other agents
{"- WebSearch: Search the web for information" if AgentCapability.WEB_SCRAPING in self.capabilities else ""}

INSTRUCTIONS:
1. Review the task details in ./context/task.json
2. Check ./context/previous_results.json for context from earlier subtasks
3. Use available tools to complete the task
4. Save your final results to ./output/result.json with this structure:
   {{
     "success": true/false,
     "data": {{...}},  
     "summary": "What you accomplished",
     "files_created": ["path1", "path2"],
     "next_steps": "Suggestions for follow-up tasks (optional)"
   }}

Complete the task efficiently and save results to output/result.json.
"""
        
        # Create options
        return ClaudeAgentOptions(
            cwd=str(task_dir),
            system_prompt=system_prompt,
            allowed_tools=allowed_tools,
            permission_mode=settings.SDK_PERMISSION_MODE,
            mcp_servers={f"{self.agent_id}_tools": self.mcp_server},
            max_turns=settings.SDK_MAX_TURNS
        )
    
    async def _execute_subtask(self, request: TaskExecutionRequest):
        """Execute subtask using Claude Agent SDK"""
        self.is_available = False
        self.current_task = request.subtask.id
        start_time = time.time()
        
        result = SubTaskResult(
            task_id=request.task_id,
            subtask_id=request.subtask.id,
            agent_id=self.agent_id,
            status=TaskStatus.IN_PROGRESS,
            execution_time=0
        )
        
        try:
            await db_manager.log_agent_activity(
                self.agent_id, "INFO",
                f"Starting execution: {request.subtask.description}",
                task_id=request.task_id
            )
            
            # Get SDK options
            options = self._get_agent_options(request.subtask, request.task_context)
            
            # Execute with Claude Agent SDK
            async with ClaudeSDKClient(options=options) as client:
                # Send initial query
                await client.query(
                    f"Complete this task: {request.subtask.description}\n\n"
                    f"Remember to save your results to ./output/result.json"
                )
                
                # Collect responses
                responses = []
                async for msg in client.receive_response():
                    if isinstance(msg, AssistantMessage):
                        for block in msg.content:
                            if isinstance(block, TextBlock):
                                responses.append(block.text)
                                
                                # Log progress
                                await db_manager.log_agent_activity(
                                    self.agent_id, "DEBUG",
                                    f"Response: {block.text[:200]}...",
                                    task_id=request.task_id
                                )
                
                # Read output
                output_file = Path(options.cwd) / "output" / "result.json"
                if output_file.exists():
                    output = json.loads(output_file.read_text())
                else:
                    # Fallback: use responses
                    output = {
                        "success": True,
                        "data": {"responses": responses},
                        "summary": f"Completed task (no result.json found)"
                    }
                
                result.status = TaskStatus.COMPLETED
                result.output = output
                
                await db_manager.log_agent_activity(
                    self.agent_id, "INFO",
                    f"Completed: {request.subtask.description}",
                    task_id=request.task_id,
                    metadata={"output": output}
                )
            
        except Exception as e:
            result.status = TaskStatus.FAILED
            result.error = str(e)
            
            await db_manager.log_agent_activity(
                self.agent_id, "ERROR",
                f"Failed: {str(e)}",
                task_id=request.task_id
            )
        
        finally:
            result.execution_time = time.time() - start_time
            self.is_available = True
            self.current_task = None
            self.tasks_completed += 1
            
            # Send result to queue
            await redis_manager.enqueue_task(
                settings.RESULT_QUEUE_NAME,
                result.dict()
            )
    
    async def _register_agent(self):
        """Register agent with Redis"""
        agent_data = {
            "agent_id": self.agent_id,
            "port": self.port,
            "is_available": self.is_available,
            "capabilities": [c.value for c in self.capabilities],
            "tasks_completed": self.tasks_completed,
            "sdk_enabled": True  # Flag for SDK-powered agents
        }
        await redis_manager.register_agent(self.agent_id, agent_data)
        await db_manager.log_agent_activity(
            self.agent_id, "INFO",
            f"Agent registered (Claude SDK) on port {self.port}"
        )
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeat"""
        while True:
            try:
                await redis_manager.update_agent_status(
                    self.agent_id,
                    {
                        "is_available": self.is_available,
                        "current_task": self.current_task,
                        "cpu_usage": psutil.cpu_percent(),
                        "memory_usage": psutil.virtual_memory().percent,
                        "tasks_completed": self.tasks_completed
                    }
                )
                await asyncio.sleep(settings.AGENT_HEARTBEAT_INTERVAL)
            except Exception as e:
                print(f"Heartbeat error: {e}")
                await asyncio.sleep(5)
    
    def _setup_routes(self):
        @self.app.on_event("startup")
        async def startup():
            await db_manager.initialize()
            await redis_manager.initialize()
            await self._register_agent()
            asyncio.create_task(self._heartbeat_loop())
        
        @self.app.on_event("shutdown")
        async def shutdown():
            await redis_manager.close()
            await db_manager.close()
        
        @self.app.get("/health")
        async def health_check():
            return {
                "status": "healthy",
                "agent_id": self.agent_id,
                "is_available": self.is_available,
                "current_task": self.current_task,
                "sdk_version": "claude-agent-sdk-1.0"
            }
        
        @self.app.get("/status")
        async def get_status():
            return AgentStatus(
                agent_id=self.agent_id,
                port=self.port,
                is_available=self.is_available,
                current_task=self.current_task,
                capabilities=self.capabilities,
                cpu_usage=psutil.cpu_percent(),
                memory_usage=psutil.virtual_memory().percent,
                tasks_completed=self.tasks_completed
            )
        
        @self.app.post("/execute")
        async def execute_task(
            request: TaskExecutionRequest,
            background_tasks: BackgroundTasks
        ):
            if not self.is_available:
                raise HTTPException(status_code=503, detail="Agent busy")
            
            background_tasks.add_task(self._execute_subtask, request)
            return {"status": "accepted", "agent_id": self.agent_id}

def create_agent_app(agent_id: str, port: int, capabilities: list):
    """Factory function to create agent app"""
    service = AgentService(agent_id, port, capabilities)
    return service.app

# Main entry point
if __name__ == "__main__":
    import uvicorn
    
    # Get agent config from command line
    agent_num = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    port = settings.AGENT_PORTS[agent_num - 1]
    
    # Capability assignments
    capabilities_map = {
        1: [AgentCapability.DATA_ANALYSIS, AgentCapability.CODE_GENERATION],
        2: [AgentCapability.WEB_SCRAPING, AgentCapability.API_INTEGRATION],
        3: [AgentCapability.FILE_PROCESSING, AgentCapability.DATABASE_OPERATIONS],
        4: [AgentCapability.CODE_GENERATION, AgentCapability.API_INTEGRATION],
        5: [AgentCapability.DATA_ANALYSIS, AgentCapability.DATABASE_OPERATIONS]
    }
    
    agent_id = f"agent_{agent_num}"
    caps = capabilities_map.get(agent_num, [AgentCapability.CODE_GENERATION])
    
    app = create_agent_app(agent_id, port, caps)
    
    print(f"Starting {agent_id} (Claude Agent SDK) on port {port}")
    print(f"Capabilities: {[c.value for c in caps]}")
    uvicorn.run(app, host="0.0.0.0", port=port)
```

### 3.7 Orchestrator Service (`orchestrator/orchestrator.py`)

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import uuid
import httpx
from typing import Dict, Any, List, Set
from datetime import datetime

from shared.models import Task, SubTask, TaskStatus, SubTaskResult
from shared.database import db_manager
from shared.redis_manager import redis_manager
from shared.config import settings
from orchestrator.task_analyzer import TaskAnalyzer

app = FastAPI(title="Multi-Agent Orchestrator v2.0")

# CORS for Streamlit
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

task_analyzer = TaskAnalyzer()

@app.on_event("startup")
async def startup():
    await db_manager.initialize()
    await redis_manager.initialize()
    
    # Start background workers
    asyncio.create_task(dispatch_tasks())
    asyncio.create_task(process_results())

@app.on_event("shutdown")
async def shutdown():
    await redis_manager.close()
    await db_manager.close()

@app.post("/tasks")
async def create_task(description: str, user_id: str = "default_user"):
    """Create a new task"""
    
    # Generate task ID
    task_id = f"task_{uuid.uuid4().hex[:12]}"
    
    # Analyze and decompose
    subtasks = await task_analyzer.analyze_and_decompose(description)
    
    # Create task
    task = Task(
        id=task_id,
        user_id=user_id,
        description=description,
        status=TaskStatus.PENDING,
        subtasks=subtasks
    )
    
    # Save to database
    await db_manager.save_task(task.dict())
    
    # Queue subtasks with no dependencies
    ready_subtasks = task_analyzer.get_ready_subtasks(subtasks, set())
    
    for subtask in ready_subtasks:
        await redis_manager.enqueue_task(
            settings.TASK_QUEUE_NAME,
            {
                "task_id": task_id,
                "subtask": subtask.dict(),
                "context": {}
            }
        )
    
    # Update task status
    if ready_subtasks:
        task.status = TaskStatus.IN_PROGRESS
        await db_manager.save_task(task.dict())
    
    return {
        "task_id": task_id,
        "status": "created",
        "subtasks_count": len(subtasks),
        "initial_subtasks_queued": len(ready_subtasks)
    }

@app.get("/tasks/{task_id}")
async def get_task_status(task_id: str):
    """Get task status and results"""
    task_data = await db_manager.get_task(task_id)
    if not task_data:
        raise HTTPException(status_code=404, detail="Task not found")
    
    results = await db_manager.get_subtask_results(task_id)
    
    return {
        "task": task_data,
        "subtask_results": results
    }

@app.get("/agents")
async def get_agents():
    """Get all registered agents"""
    agent_ids = await redis_manager.get_all_agents()
    agents = []
    
    for agent_id in agent_ids:
        status = await redis_manager.get_agent_status(agent_id)
        if status:
            agents.append(status)
    
    return {"agents": agents}

@app.get("/agents/available")
async def get_available_agents(capability: str = None):
    """Get available agents"""
    available = await redis_manager.get_available_agents(capability)
    return {"available_agents": available, "count": len(available)}

# Background Workers

async def dispatch_tasks():
    """Background worker to dispatch tasks to agents"""
    while True:
        try:
            # Dequeue task (blocking with 1s timeout)
            task_data = await redis_manager.dequeue_task(
                settings.TASK_QUEUE_NAME,
                timeout=1
            )
            
            if task_data:
                await assign_task_to_agent(task_data)
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"Dispatch error: {e}")
            await asyncio.sleep(1)

async def assign_task_to_agent(task_data: Dict[str, Any]):
    """Assign subtask to appropriate agent"""
    
    subtask = SubTask(**task_data["subtask"])
    task_id = task_data["task_id"]
    
    # Find agent with required capabilities
    best_agent = None
    for capability in subtask.required_capabilities:
        available = await redis_manager.get_available_agents(capability.value)
        if available:
            best_agent = available[0]
            break
    
    if not best_agent:
        # No agent available, re-queue
        await redis_manager.enqueue_task(settings.TASK_QUEUE_NAME, task_data)
        await asyncio.sleep(1)
        return
    
    # Get agent port
    agent_status = await redis_manager.get_agent_status(best_agent)
    if not agent_status:
        await redis_manager.enqueue_task(settings.TASK_QUEUE_NAME, task_data)
        return
    
    # Send to agent
    agent_url = f"{settings.AGENT_BASE_URL}:{agent_status['port']}/execute"
    
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.post(
                agent_url,
                json={
                    "task_id": task_id,
                    "subtask": subtask.dict(),
                    "task_context": task_data.get("context", {})
                }
            )
            
            if response.status_code == 200:
                print(f"✓ Assigned {subtask.id} to {best_agent}")
            else:
                await redis_manager.enqueue_task(settings.TASK_QUEUE_NAME, task_data)
                
    except Exception as e:
        print(f"Error assigning to agent: {e}")
        await redis_manager.enqueue_task(settings.TASK_QUEUE_NAME, task_data)

async def process_results():
    """Background worker to process subtask results"""
    while True:
        try:
            # Dequeue result
            result_data = await redis_manager.dequeue_task(
                settings.RESULT_QUEUE_NAME,
                timeout=1
            )
            
            if result_data:
                await handle_subtask_result(result_data)
            
            await asyncio.sleep(0.1)
            
        except Exception as e:
            print(f"Result processing error: {e}")
            await asyncio.sleep(1)

async def handle_subtask_result(result_data: Dict[str, Any]):
    """Handle completed subtask result"""
    
    result = SubTaskResult(**result_data)
    task_id = result.task_id
    
    # Save result
    await db_manager.save_subtask_result(result.dict())
    
    # Get task
    task_data = await db_manager.get_task(task_id)
    if not task_data:
        return
    
    # Get all results
    all_results = await db_manager.get_subtask_results(task_id)
    completed_ids = {r['subtask_id'] for r in all_results if r['status'] == 'completed'}
    
    # Parse subtasks
    import json
    subtasks = [SubTask(**st) for st in json.loads(task_data['subtasks'])]
    
    # Check if all complete
    if len(completed_ids) == len(subtasks):
        # All done - aggregate results
        task_data['status'] = TaskStatus.COMPLETED.value
        task_data['result'] = {
            "subtask_results": all_results,
            "summary": "All subtasks completed"
        }
        task_data['updated_at'] = datetime.utcnow()
        await db_manager.save_task(task_data)
        
        print(f"✓ Task {task_id} completed")
    else:
        # Queue newly-ready subtasks
        ready = task_analyzer.get_ready_subtasks(subtasks, completed_ids)
        
        for subtask in ready:
            # Build context from previous results
            context = {}
            for dep_id in subtask.dependencies:
                dep_result = next((r for r in all_results if r['subtask_id'] == dep_id), None)
                if dep_result:
                    context[dep_id] = dep_result.get('output', {})
            
            await redis_manager.enqueue_task(
                settings.TASK_QUEUE_NAME,
                {
                    "task_id": task_id,
                    "subtask": subtask.dict(),
                    "context": context
                }
            )
        
        # Update task status
        task_data['status'] = TaskStatus.IN_PROGRESS.value
        task_data['updated_at'] = datetime.utcnow()
        await db_manager.save_task(task_data)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=settings.ORCHESTRATOR_PORT)
```

---

## 4. Data Flow

### 4.1 Complete Task Lifecycle

```
1. USER SUBMITS TASK
   └─> Streamlit UI: POST /tasks
       └─> Orchestrator receives request

2. TASK DECOMPOSITION
   └─> Orchestrator calls TaskAnalyzer
       └─> Claude API analyzes task
           └─> Returns subtasks with dependencies

3. TASK STORAGE
   └─> Save to PostgreSQL tasks table
       └─> Queue ready subtasks to Redis TASK_QUEUE

4. TASK DISPATCH (Background Loop)
   └─> Dispatcher dequeues from TASK_QUEUE
       └─> Find available agent with capabilities
           └─> POST to Agent /execute endpoint

5. AGENT EXECUTION (Claude Agent SDK)
   └─> Agent creates workspace directory
       ├─> Write context files
       ├─> Initialize ClaudeSDKClient with options
       │   ├─> MCP servers for DB, embeddings, shared state
       │   ├─> Permission mode (approveEdits/auto)
       │   └─> System prompt with task details
       └─> Execute via SDK
           ├─> Claude reads context files
           ├─> Uses tools (Read/Write/Bash/MCP)
           ├─> Can spawn subagents if needed
           └─> Saves result to output/result.json

6. RESULT COLLECTION
   └─> Agent reads output/result.json
       └─> Creates SubTaskResult
           └─> Enqueues to Redis RESULT_QUEUE

7. RESULT PROCESSING (Background Loop)
   └─> Processor dequeues from RESULT_QUEUE
       ├─> Save to PostgreSQL subtask_results
       ├─> Check if all subtasks complete
       └─> If not complete:
           ├─> Find newly-ready subtasks
           ├─> Build context from dependencies
           └─> Queue to TASK_QUEUE
       └─> If complete:
           ├─> Aggregate results
           └─> Update task status = COMPLETED

8. USER MONITORING
   └─> Streamlit polls GET /tasks/{id}
       └─> Displays real-time progress
```

### 4.2 Agent Heartbeat Flow

```
Every 10 seconds (per agent):

Agent Service
   ├─> Collect metrics (CPU, memory, availability)
   ├─> HSET agent:{agent_id} {...}
   └─> EXPIRE agent:{agent_id} 60

Redis stores:
   agent:agent_1 → {
     is_available: true,
     current_task: null,
     cpu_usage: 25.5,
     ...
   }
   TTL: 60 seconds

If agent crashes/dies:
   └─> Key expires after 60s
       └─> Orchestrator detects missing agent
           └─> Can reassign tasks
```

---

## 5. Database Schema

### 5.1 PostgreSQL Tables

```sql
-- Tasks table
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    status TEXT NOT NULL,
    subtasks JSONB,
    result JSONB,
    error TEXT
);

CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);

-- Subtask results table
CREATE TABLE subtask_results (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL,
    subtask_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL,
    output JSONB,
    error TEXT,
    execution_time FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
);

CREATE INDEX idx_subtask_results_task ON subtask_results(task_id);
CREATE INDEX idx_subtask_results_agent ON subtask_results(agent_id);

-- Agent logs table
CREATE TABLE agent_logs (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_id TEXT,
    log_level TEXT NOT NULL,
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_id);
CREATE INDEX idx_agent_logs_task ON agent_logs(task_id);
CREATE INDEX idx_agent_logs_created ON agent_logs(created_at DESC);
```

### 5.2 Redis Data Structures

```
Queues (Lists):
  agent_tasks → [task_data_1, task_data_2, ...]
  agent_results → [result_data_1, result_data_2, ...]

Sets:
  active_agents → {agent_1, agent_2, agent_3, agent_4, agent_5}

Hashes (Agent Status):
  agent:agent_1 → {
    agent_id: "agent_1",
    port: 8001,
    is_available: true,
    current_task: null,
    capabilities: ["data_analysis", "code_generation"],
    cpu_usage: 25.5,
    memory_usage: 42.0,
    tasks_completed: 15,
    sdk_enabled: true
  }
  TTL: 60 seconds

Shared State:
  state:* → arbitrary JSON data
  lock:* → distributed locks
  cache:* → cached results
```

---

## 6. API Specifications

### 6.1 Orchestrator API

**Base URL:** `http://localhost:8000`

#### POST /tasks
```http
POST /tasks?description=<task>&user_id=<user>

Response 200:
{
  "task_id": "task_abc123",
  "status": "created",
  "subtasks_count": 4,
  "initial_subtasks_queued": 2
}
```

#### GET /tasks/{task_id}
```http
GET /tasks/task_abc123

Response 200:
{
  "task": {
    "id": "task_abc123",
    "user_id": "demo_user",
    "description": "Analyze sales data...",
    "status": "in_progress",
    "subtasks": "[...]",
    "result": null
  },
  "subtask_results": [
    {
      "subtask_id": "subtask_1",
      "agent_id": "agent_1",
      "status": "completed",
      "output": {...},
      "execution_time": 12.5
    }
  ]
}
```

#### GET /agents
```http
GET /agents

Response 200:
{
  "agents": [
    {
      "agent_id": "agent_1",
      "port": 8001,
      "is_available": true,
      "capabilities": ["data_analysis", "code_generation"],
      "tasks_completed": 15,
      "sdk_enabled": true
    }
  ]
}
```

### 6.2 Agent API

**Base URL:** `http://localhost:800X` (X = 1-5)

#### GET /health
```http
GET /health

Response 200:
{
  "status": "healthy",
  "agent_id": "agent_1",
  "is_available": true,
  "current_task": null,
  "sdk_version": "claude-agent-sdk-1.0"
}
```

#### POST /execute
```http
POST /execute
Content-Type: application/json

{
  "task_id": "task_abc123",
  "subtask": {
    "id": "subtask_1",
    "description": "Calculate statistics",
    "required_capabilities": ["data_analysis"],
    ...
  },
  "task_context": {...}
}

Response 200:
{
  "status": "accepted",
  "agent_id": "agent_1"
}
```

---

## 7. File Structure

```
multi-agent-system/
│
├── shared/                          # Shared components
│   ├── __init__.py
│   ├── models.py                    # Pydantic models
│   ├── config.py                    # Configuration
│   ├── database.py                  # PostgreSQL manager
│   └── redis_manager.py             # Redis operations
│
├── orchestrator/                    # Orchestrator service
│   ├── __init__.py
│   ├── orchestrator.py              # Main FastAPI app
│   └── task_analyzer.py             # Task decomposition
│
├── agent/                           # Agent service
│   ├── __init__.py
│   └── agent_service.py             # Agent with Claude SDK
│
├── ui/                              # User interface
│   └── streamlit_app.py             # Streamlit dashboard
│
├── shared_files/                    # Shared workspace
│   └── {task_id}/                   # Per-task directories
│       ├── context/                 # Context files
│       │   ├── task.json
│       │   └── previous_results.json
│       ├── output/                  # Agent outputs
│       │   └── result.json
│       └── temp/                    # Temporary files
│
├── scripts/                         # Utility scripts
│   ├── start.sh                     # Start all services
│   ├── stop.sh                      # Stop all services
│   └── test_system.py               # System tests
│
├── tests/                           # Test suite
│   ├── __init__.py
│   ├── test_integration.py
│   ├── test_orchestrator.py
│   ├── test_agents.py
│   └── conftest.py
│
├── docker-compose.yml               # Docker Compose config
├── Dockerfile.orchestrator          # Orchestrator image
├── Dockerfile.agent                 # Agent image
├── Dockerfile.streamlit             # Streamlit image
│
├── requirements.txt                 # Python dependencies
├── .env.example                     # Environment template
├── .env                            # Environment (gitignored)
├── .gitignore
├── README.md
└── LICENSE
```

---

## 8. Implementation Guide

### 8.1 Installation & Setup

**Step 1: Install Claude Agent SDK**
```bash
# Install Claude Code CLI (optional, for testing)
npm install -g @anthropic-ai/claude-code

# Install Python SDK
pip install claude-agent-sdk[all]
```

**Step 2: Clone and Setup**
```bash
# Create project
mkdir multi-agent-system
cd multi-agent-system

# Create directories
mkdir -p shared orchestrator agent ui shared_files tests scripts

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

**Step 3: Configure Environment**
```bash
# Create .env file
cat > .env << EOF
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
POSTGRES_PASSWORD=postgres
REDIS_HOST=localhost
SHARED_FILES_PATH=./shared_files
SDK_PERMISSION_MODE=approveEdits
SDK_MAX_TURNS=50
EOF
```

### 8.2 Requirements File

```txt
# requirements.txt

# Claude Agent SDK (CRITICAL - NEW)
claude-agent-sdk[all]>=1.0.0

# Core
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
anthropic==0.7.7

# Database
asyncpg==0.29.0

# Redis
redis[asyncio]==5.0.1

# HTTP
httpx==0.25.2

# Monitoring
psutil==5.9.6

# UI
streamlit==1.28.2
pandas==2.1.3

# Utilities
python-dotenv==1.0.0
anyio==4.0.0
```

### 8.3 Docker Compose Configuration

```yaml
# docker-compose.yml
version: '3.8'

services:
  postgres:
    image: postgres:15-alpine
    container_name: multi_agent_postgres
    environment:
      POSTGRES_DB: multi_agent_db
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-postgres}
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    container_name: multi_agent_redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5

  orchestrator:
    build:
      context: .
      dockerfile: Dockerfile.orchestrator
    container_name: orchestrator
    environment:
      POSTGRES_HOST: postgres
      REDIS_HOST: redis
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
    ports:
      - "8000:8000"
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./shared_files:/app/shared_files

  agent1:
    build:
      context: .
      dockerfile: Dockerfile.agent
    container_name: agent1
    environment:
      POSTGRES_HOST: postgres
      REDIS_HOST: redis
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      AGENT_NUM: 1
    ports:
      - "8001:8001"
    depends_on:
      - postgres
      - redis
      - orchestrator
    volumes:
      - ./shared_files:/app/shared_files

  agent2:
    build:
      context: .
      dockerfile: Dockerfile.agent
    container_name: agent2
    environment:
      POSTGRES_HOST: postgres
      REDIS_HOST: redis
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      AGENT_NUM: 2
    ports:
      - "8002:8002"
    depends_on:
      - postgres
      - redis
      - orchestrator
    volumes:
      - ./shared_files:/app/shared_files

  agent3:
    build:
      context: .
      dockerfile: Dockerfile.agent
    container_name: agent3
    environment:
      POSTGRES_HOST: postgres
      REDIS_HOST: redis
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      AGENT_NUM: 3
    ports:
      - "8003:8003"
    depends_on:
      - postgres
      - redis
      - orchestrator
    volumes:
      - ./shared_files:/app/shared_files

  agent4:
    build:
      context: .
      dockerfile: Dockerfile.agent
    container_name: agent4
    environment:
      POSTGRES_HOST: postgres
      REDIS_HOST: redis
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      AGENT_NUM: 4
    ports:
      - "8004:8004"
    depends_on:
      - postgres
      - redis
      - orchestrator
    volumes:
      - ./shared_files:/app/shared_files

  agent5:
    build:
      context: .
      dockerfile: Dockerfile.agent
    container_name: agent5
    environment:
      POSTGRES_HOST: postgres
      REDIS_HOST: redis
      ANTHROPIC_API_KEY: ${ANTHROPIC_API_KEY}
      AGENT_NUM: 5
    ports:
      - "8005:8005"
    depends_on:
      - postgres
      - redis
      - orchestrator
    volumes:
      - ./shared_files:/app/shared_files

  streamlit:
    build:
      context: .
      dockerfile: Dockerfile.streamlit
    container_name: streamlit_ui
    ports:
      - "8501:8501"
    depends_on:
      - orchestrator
    environment:
      ORCHESTRATOR_URL: http://orchestrator:8000

volumes:
  postgres_data:
  redis_data:
```

### 8.4 Dockerfiles

```dockerfile
# Dockerfile.orchestrator
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY shared/ ./shared/
COPY orchestrator/ ./orchestrator/

CMD ["python", "-m", "orchestrator.orchestrator"]

# ===================================

# Dockerfile.agent
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY shared/ ./shared/
COPY agent/ ./agent/

CMD ["sh", "-c", "python -m agent.agent_service ${AGENT_NUM}"]

# ===================================

# Dockerfile.streamlit
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy code
COPY ui/ ./ui/

CMD ["streamlit", "run", "ui/streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
```

### 8.5 Quick Start Commands

```bash
# Start with Docker
chmod +x scripts/start.sh scripts/stop.sh
./scripts/start.sh docker

# Or start locally
./scripts/start.sh local

# Run tests
python scripts/test_system.py

# View logs
docker-compose logs -f agent1

# Stop
./scripts/stop.sh
```

---

## 9. Testing Strategy

### 9.1 Unit Tests

```python
# tests/test_task_analyzer.py
import pytest
from orchestrator.task_analyzer import TaskAnalyzer

@pytest.mark.asyncio
async def test_task_decomposition():
    analyzer = TaskAnalyzer()
    subtasks = await analyzer.analyze_and_decompose(
        "Build a REST API for user management"
    )
    
    assert len(subtasks) > 0
    assert all(st.id for st in subtasks)
    assert all(st.description for st in subtasks)
    assert all(st.required_capabilities for st in subtasks)

@pytest.mark.asyncio
async def test_dependency_resolution():
    analyzer = TaskAnalyzer()
    subtasks = await analyzer.analyze_and_decompose(
        "Fetch data, clean it, analyze it, and create report"
    )
    
    # Check dependencies exist
    graph = analyzer.build_execution_graph(subtasks)
    assert len(graph) == len(subtasks)
    
    # First subtask should have no dependencies
    ready = analyzer.get_ready_subtasks(subtasks, set())
    assert len(ready) >= 1
```

### 9.2 Integration Tests

```python
# tests/test_integration.py
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_end_to_end_task():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        # Create task
        response = await client.post(
            "/tasks",
            params={"description": "Calculate factorial of 10", "user_id": "test"}
        )
        assert response.status_code == 200
        task_id = response.json()["task_id"]
        
        # Poll for completion
        import asyncio
        for _ in range(60):
            response = await client.get(f"/tasks/{task_id}")
            task = response.json()["task"]
            
            if task["status"] == "completed":
                assert task["result"] is not None
                return
            
            await asyncio.sleep(2)
        
        pytest.fail("Task did not complete in 120 seconds")
```

### 9.3 System Test Script

```python
# scripts/test_system.py
import asyncio
import httpx

async def test_system():
    print("🚀 Testing Multi-Agent System v2.0")
    
    tests = [
        ("Orchestrator Health", test_orchestrator),
        ("Agents Registered", test_agents),
        ("Simple Task", test_simple_task),
        ("Claude SDK Integration", test_sdk_features),
    ]
    
    results = {}
    for name, test_func in tests:
        print(f"\n🔍 {name}...")
        try:
            await test_func()
            results[name] = True
            print(f"✅ {name} PASSED")
        except Exception as e:
            results[name] = False
            print(f"❌ {name} FAILED: {e}")
    
    # Summary
    passed = sum(results.values())
    total = len(results)
    print(f"\n{'='*60}")
    print(f"📊 Results: {passed}/{total} tests passed")
    print(f"{'='*60}")
    
    return passed == total

async def test_orchestrator():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/agents")
        assert response.status_code == 200

async def test_agents():
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8000/agents")
        agents = response.json()["agents"]
        assert len(agents) >= 1
        
        # Check SDK enabled
        for agent in agents:
            assert agent.get("sdk_enabled") == True

async def test_simple_task():
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "http://localhost:8000/tasks",
            params={"description": "Test task", "user_id": "test"}
        )
        task_id = response.json()["task_id"]
        
        # Wait for completion
        for _ in range(30):
            response = await client.get(f"http://localhost:8000/tasks/{task_id}")
            if response.json()["task"]["status"] in ["completed", "failed"]:
                return
            await asyncio.sleep(2)

async def test_sdk_features():
    # Verify agents have SDK capabilities
    async with httpx.AsyncClient() as client:
        for port in [8001, 8002, 8003, 8004, 8005]:
            response = await client.get(f"http://localhost:{port}/health")
            health = response.json()
            assert "sdk_version" in health

if __name__ == "__main__":
    success = asyncio.run(test_system())
    exit(0 if success else 1)
```

---

## 10. Deployment

### 10.1 Production Checklist

- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] Secure `ANTHROPIC_API_KEY` in secrets manager
- [ ] Configure `SDK_PERMISSION_MODE` appropriately
- [ ] Set up SSL/TLS for external access
- [ ] Configure firewall rules
- [ ] Enable logging and monitoring
- [ ] Set resource limits in Docker
- [ ] Configure backups for PostgreSQL
- [ ] Set up health check endpoints
- [ ] Document runbook for operations

### 10.2 Environment Variables

```bash
# .env.production
ANTHROPIC_API_KEY=<secret>
POSTGRES_PASSWORD=<secret>
POSTGRES_HOST=postgres.prod.internal
REDIS_HOST=redis.prod.internal
SDK_PERMISSION_MODE=approveAll  # or approveEdits for safety
SDK_MAX_TURNS=100
TASK_TIMEOUT=600
```

### 10.3 Monitoring

**Key Metrics to Track:**
- Task success rate
- Average task duration
- Agent utilization
- Queue lengths
- API response times
- SDK tool usage

**Logging:**
- All agent activity logged to PostgreSQL
- Structured logs for parsing
- Centralized log aggregation (ELK stack)

---

## 11. Summary of v2.0 Improvements

| Feature | Benefit |
|---------|---------|
| **Claude Agent SDK** | Native tool integration, built-in file ops, streaming |
| **MCP Servers** | In-process tools, no IPC overhead, declarative |
| **File System Context** | Scalable context management, grep/search capability |
| **Permission Modes** | Fine-grained control over autonomy |
| **Subagents** | Parallel specialized work |
| **Hooks** | Automated quality gates |
| **Checkpoints** | Safe exploration of complex tasks |

---

**This specification provides everything needed to build a production-grade multi-agent system powered by the Claude Agent SDK!** 🚀# Multi-Agent Claude System - Complete Specification v2.0
## Using Official Claude Agent SDK

---

## 📋 Table of Contents
1. [System Overview](#1-system-overview)
2. [Architecture](#2-architecture)
3. [Component Specifications](#3-component-specifications)
4. [Data Flow](#4-data-flow)
5. [Database Schema](#5-database-schema)
6. [API Specifications](#6-api-specifications)
7. [File Structure](#7-file-structure)
8. [Implementation Guide](#8-implementation-guide)
9. [Testing Strategy](#9-testing-strategy)
10. [Deployment](#10-deployment)

---

## 1. System Overview

### 1.1 Purpose
A distributed multi-agent system where 5 independent Claude agents, powered by the **official Claude Agent SDK**, execute tasks in parallel. Agents share resources (PostgreSQL, Redis, file storage, embedding API) and coordinate through a central orchestrator.

### 1.2 Core Capabilities

**✨ New Features with Claude Agent SDK:**
- **Native Tool Integration**: MCP servers for database, files, APIs
- **Built-in File Operations**: Read, Write, Bash execution
- **Subagent Delegation**: Parallel specialized subtasks
- **Checkpoint System**: Save/restore state for long tasks
- **Automated Hooks**: Trigger actions at specific points
- **Permission Control**: Configurable autonomy levels
- **Context as File System**: Navigate folders instead of prompt stuffing

### 1.3 Technology Stack

```yaml
Frontend:         Streamlit 1.28+
Backend:          FastAPI 0.104+
Agent Runtime:    Claude Agent SDK 1.0+ ⭐ NEW
AI Model:         Claude Sonnet 4.5 (claude-sonnet-4-5-20250929)
Database:         PostgreSQL 15
Cache/Queue:      Redis 7
Language:         Python 3.11+
Container:        Docker & Docker Compose
```

### 1.4 Key Differences from v1.0

| Feature | v1.0 (Basic API) | v2.0 (Agent SDK) |
|---------|------------------|------------------|
| **Claude Integration** | Basic API calls | ClaudeSDKClient with streaming |
| **Tool Access** | Hard-coded in prompts | MCP servers, declarative |
| **File Operations** | Manual implementation | Built-in Read/Write/Bash |
| **Context** | JSON in prompts | File system navigation |
| **Parallel Work** | Manual coordination | Native subagents |
| **Safety** | Custom logic | Built-in permissions |
| **State Management** | None | Checkpoints |

---

## 2. Architecture

### 2.1 System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────┐
│                    USER INTERFACE LAYER                           │
│                                                                    │
│   ┌────────────────────────────────────────────────────────┐    │
│   │           Streamlit Control Center (Port 8501)          │    │
│   │                                                          │    │
│   │  Features:                                              │    │
│   │  • Task Creation & Submission                           │    │
│   │  • Real-time Task Monitoring                            │    │
│   │  • Agent Status Dashboard                               │    │
│   │  • Live Logs & Results Viewer                           │    │
│   │  • Analytics & Metrics                                  │    │
│   └────────────────────────────────────────────────────────┘    │
└────────────────────────────┬─────────────────────────────────────┘
                             │ HTTP REST API
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│               ORCHESTRATION LAYER (Port 8000)                     │
│                                                                    │
│   ┌────────────────────────────────────────────────────────┐    │
│   │              Orchestrator Service                       │    │
│   │                                                          │    │
│   │  ┌────────────────────────────────────────────┐        │    │
│   │  │  Task Analyzer (Claude API)                │        │    │
│   │  │  • Decomposes tasks into subtasks          │        │    │
│   │  │  • Identifies dependencies                 │        │    │
│   │  │  • Determines required capabilities        │        │    │
│   │  │  • Estimates duration & priority           │        │    │
│   │  └────────────────────────────────────────────┘        │    │
│   │                                                          │    │
│   │  ┌────────────────────────────────────────────┐        │    │
│   │  │  Task Dispatcher (Background Worker)       │        │    │
│   │  │  • Polls TASK_QUEUE from Redis             │        │    │
│   │  │  • Capability-based agent selection        │        │    │
│   │  │  • Load balancing across agents            │        │    │
│   │  │  • Retry logic for failures                │        │    │
│   │  └────────────────────────────────────────────┘        │    │
│   │                                                          │    │
│   │  ┌────────────────────────────────────────────┐        │    │
│   │  │  Result Processor (Background Worker)      │        │    │
│   │  │  • Polls RESULT_QUEUE from Redis           │        │    │
│   │  │  • Aggregates subtask results              │        │    │
│   │  │  • Handles dependency resolution           │        │    │
│   │  │  • Queues newly-ready subtasks             │        │    │
│   │  └────────────────────────────────────────────┘        │    │
│   └────────────────────────────────────────────────────────┘    │
└────────────────────────────┬─────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         │                   │                   │
         ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                   AGENT EXECUTION LAYER                           │
│                   (Powered by Claude Agent SDK)                   │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │   Agent 1    │  │   Agent 2    │  │   Agent 3    │           │
│  │  Port 8001   │  │  Port 8002   │  │  Port 8003   │           │
│  ├──────────────┤  ├──────────────┤  ├──────────────┤           │
│  │              │  │              │  │              │           │
│  │ Capabilities:│  │ Capabilities:│  │ Capabilities:│           │
│  │ • Data       │  │ • Web        │  │ • File       │           │
│  │   Analysis   │  │   Scraping   │  │   Processing │           │
│  │ • Code Gen   │  │ • API Integ  │  │ • DB Ops     │           │
│  │              │  │              │  │              │           │
│  │ ┌──────────┐ │  │ ┌──────────┐ │  │ ┌──────────┐ │           │
│  │ │ Claude   │ │  │ │ Claude   │ │  │ │ Claude   │ │           │
│  │ │ SDK      │ │  │ │ SDK      │ │  │ │ SDK      │ │           │
│  │ │ Client   │ │  │ │ Client   │ │  │ │ Client   │ │           │
│  │ └──────────┘ │  │ └──────────┘ │  │ └──────────┘ │           │
│  │              │  │              │  │              │           │
│  │ MCP Servers: │  │ MCP Servers: │  │ MCP Servers: │           │
│  │ • PostgreSQL │  │ • PostgreSQL │  │ • PostgreSQL │           │
│  │ • Embeddings │  │ • Embeddings │  │ • Embeddings │           │
│  │ • SharedState│  │ • SharedState│  │ • SharedState│           │
│  │              │  │              │  │              │           │
│  │ Features:    │  │ Features:    │  │ Features:    │           │
│  │ • Subagents  │  │ • Subagents  │  │ • Subagents  │           │
│  │ • Hooks      │  │ • Hooks      │  │ • Hooks      │           │
│  │ • Checkpoints│  │ • Checkpoints│  │ • Checkpoints│           │
│  │ • File Ops   │  │ • File Ops   │  │ • File Ops   │           │
│  │ • Bash       │  │ • Bash       │  │ • Bash       │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                    │
│  ┌──────────────┐  ┌──────────────┐                              │
│  │   Agent 4    │  │   Agent 5    │                              │
│  │  Port 8004   │  │  Port 8005   │                              │
│  │  (similar)   │  │  (similar)   │                              │
│  └──────────────┘  └──────────────┘                              │
└────────────────────────────┬─────────────────────────────────────┘
                             │
         ┌───────────────────┼───────────────────┐
         ▼                   ▼                   ▼
┌──────────────────────────────────────────────────────────────────┐
│                    SHARED RESOURCES LAYER                         │
│                                                                    │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────┐   │
│  │   PostgreSQL     │  │      Redis       │  │ File Storage │   │
│  │   (Port 5432)    │  │   (Port 6379)    │  │ (./shared)   │   │
│  ├──────────────────┤  ├──────────────────┤  ├──────────────┤   │
│  │                  │  │                  │  │              │   │
│  │ Tables:          │  │ Queues:          │  │ Structure:   │   │
│  │ • tasks          │  │ • agent_tasks    │  │ • /tasks/    │   │
│  │ • subtask_       │  │ • agent_results  │  │   └─ {id}/   │   │
│  │   results        │  │                  │  │     ├─ ctx/  │   │
│  │ • agent_logs     │  │ Sets:            │  │     ├─ out/  │   │
│  │                  │  │ • active_agents  │  │     └─ temp/ │   │
│  │ Indexes:         │  │                  │  │              │   │
│  │ • task_status    │  │ Hashes:          │  │              │   │
│  │ • task_user      │  │ • agent:*        │  │              │   │
│  │ • subtask_task   │  │   (status data)  │  │              │   │
│  │                  │  │                  │  │              │   │
│  │                  │  │ State:           │  │              │   │
│  │                  │  │ • state:*        │  │              │   │
│  │                  │  │ • lock:*         │  │              │   │
│  │                  │  │ • cache:*        │  │              │   │
│  └──────────────────┘  └──────────────────┘  └──────────────┘   │
│                                                                    │
│  ┌──────────────────┐                                             │
│  │  Embedding API   │                                             │
│  │  (Port 8080)     │                                             │
│  ├──────────────────┤                                             │
│  │ POST /embed      │                                             │
│  │ • Text → Vector  │                                             │
│  │ • Batch support  │                                             │
│  └──────────────────┘                                             │
└──────────────────────────────────────────────────────────────────┘
```

### 2.2 Component Overview

| Component | Technology | Port | Purpose |
|-----------|-----------|------|---------|
| Streamlit UI | Streamlit | 8501 | User interface & monitoring |
| Orchestrator | FastAPI | 8000 | Task management & coordination |
| Agent 1 | FastAPI + Claude SDK | 8001 | Data Analysis, Code Generation |
| Agent 2 | FastAPI + Claude SDK | 8002 | Web Scraping, API Integration |
| Agent 3 | FastAPI + Claude SDK | 8003 | File Processing, DB Operations |
| Agent 4 | FastAPI + Claude SDK | 8004 | Code Generation, API Integration |
| Agent 5 | FastAPI + Claude SDK | 8005 | Data Analysis, DB Operations |
| PostgreSQL | PostgreSQL 15 | 5432 | Persistent storage |
| Redis | Redis 7 | 6379 | Message queue & cache |
| Embedding API | Custom/External | 8080 | Vector embeddings (optional) |

---

## 3. Component Specifications

### 3.1 Shared Models (`shared/models.py`)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class TaskStatus(str, Enum):
    """Task execution status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentCapability(str, Enum):
    """Agent specialized capabilities"""
    DATA_ANALYSIS = "data_analysis"
    WEB_SCRAPING = "web_scraping"
    CODE_GENERATION = "code_generation"
    FILE_PROCESSING = "file_processing"
    DATABASE_OPERATIONS = "database_operations"
    API_INTEGRATION = "api_integration"

class SubTask(BaseModel):
    """Individual subtask within a task"""
    id: str
    description: str
    required_capabilities: List[AgentCapability]
    dependencies: List[str] = []  # Subtask IDs this depends on
    priority: int = Field(default=5, ge=0, le=10)
    estimated_duration: Optional[int] = None  # seconds
    input_data: Dict[str, Any] = {}

class Task(BaseModel):
    """Main task submitted by user"""
    id: str
    user_id: str
    description: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    status: TaskStatus = TaskStatus.PENDING
    subtasks: List[SubTask] = []
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class SubTaskResult(BaseModel):
    """Result from subtask execution"""
    task_id: str  # Parent task ID
    subtask_id: str
    agent_id: str
    status: TaskStatus
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float  # seconds
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AgentStatus(BaseModel):
    """Agent runtime status"""
    agent_id: str
    port: int
    is_available: bool
    current_task: Optional[str] = None
    capabilities: List[AgentCapability]
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    tasks_completed: int = 0
    last_heartbeat: datetime = Field(default_factory=datetime.utcnow)

class TaskExecutionRequest(BaseModel):
    """Request to execute a subtask"""
    task_id: str  # Parent task ID
    subtask: SubTask
    task_context: Dict[str, Any] = {}  # Context from previous subtasks
```

### 3.2 Configuration (`shared/config.py`)

```python
import os
from pathlib import Path
from typing import List

class Settings:
    """System-wide configuration"""
    
    # PostgreSQL
    POSTGRES_HOST: str = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT: int = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "multi_agent_db")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    
    @property
    def DATABASE_URL(self) -> str:
        return (f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    
    # Anthropic / Claude
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    CLAUDE_MODEL: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
    
    # Service Ports
    ORCHESTRATOR_PORT: int = int(os.getenv("ORCHESTRATOR_PORT", "8000"))
    STREAMLIT_PORT: int = int(os.getenv("STREAMLIT_PORT", "8501"))
    AGENT_PORTS: List[int] = [8001, 8002, 8003, 8004, 8005]
    AGENT_BASE_URL: str = "http://localhost"
    
    # File Storage
    SHARED_FILES_PATH: Path = Path(os.getenv("SHARED_FILES_PATH", "./shared_files"))
    
    # Embedding API (optional)
    EMBEDDING_API_URL: str = os.getenv("EMBEDDING_API_URL", "http://localhost:8080/embed")
    
    # Queue Names
    TASK_QUEUE_NAME: str = "agent_tasks"
    RESULT_QUEUE_NAME: str = "agent_results"
    
    # Timeouts & Intervals
    TASK_TIMEOUT: int = int(os.getenv("TASK_TIMEOUT", "300"))
    AGENT_HEARTBEAT_INTERVAL: int = int(os.getenv("AGENT_HEARTBEAT_INTERVAL", "10"))
    
    # Claude Agent SDK Settings
    SDK_PERMISSION_MODE: str = os.getenv("SDK_PERMISSION_MODE", "approveEdits")
    SDK_MAX_TURNS: int = int(os.getenv("SDK_MAX_TURNS", "50"))
    
    def __post_init__(self):
        # Ensure shared files directory exists
        self.SHARED_FILES_PATH.mkdir(parents=True, exist_ok=True)

settings = Settings()
```

### 3.3 Database Manager (`shared/database.py`)

```python
import asyncpg
from typing import Optional, List, Dict, Any
from shared.config import settings
import json
from datetime import datetime

class DatabaseManager:
    """Manages PostgreSQL connections and operations"""
    
    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None
    
    async def initialize(self):
        """Initialize database connection pool and create tables"""
        self.pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=2,
            max_size=20,
            command_timeout=60
        )
        await self._create_tables()
    
    async def close(self):
        """Close database connection pool"""
        if self.pool:
            await self.pool.close()
    
    async def _create_tables(self):
        """Create database schema"""
        async with self.pool.acquire() as conn:
            # Tasks table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    updated_at TIMESTAMP NOT NULL,
                    status TEXT NOT NULL,
                    subtasks JSONB,
                    result JSONB,
                    error TEXT
                )
            ''')
            
            # Subtask results table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS subtask_results (
                    id SERIAL PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    subtask_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    output JSONB,
                    error TEXT,
                    execution_time FLOAT,
                    created_at TIMESTAMP DEFAULT NOW(),
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
            ''')
            
            # Agent logs table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id SERIAL PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    task_id TEXT,
                    log_level TEXT NOT NULL,
                    message TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            ''')
            
            # Create indexes
            await conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
                CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_created ON tasks(created_at DESC);
                CREATE INDEX IF NOT EXISTS idx_subtask_results_task ON subtask_results(task_id);
                CREATE INDEX IF NOT EXISTS idx_subtask_results_agent ON subtask_results(agent_id);
                CREATE INDEX IF NOT EXISTS idx_agent_logs_agent ON agent_logs(agent_id);
                CREATE INDEX IF NOT EXISTS idx_agent_logs_task ON agent_logs(task_id);
                CREATE INDEX IF NOT EXISTS idx_agent_logs_created ON agent_logs(created_at DESC);
            ''')
    
    async def save_task(self, task: Dict[str, Any]):
        """Insert or update a task"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO tasks (id, user_id, description, created_at, updated_at, status, subtasks, result, error)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    updated_at = EXCLUDED.updated_at,
                    subtasks = EXCLUDED.subtasks,
                    result = EXCLUDED.result,
                    error = EXCLUDED.error
            ''', task['id'], task['user_id'], task['description'],
                task['created_at'], task.get('updated_at', datetime.utcnow()),
                task['status'], json.dumps(task.get('subtasks', [])),
                json.dumps(task.get('result')), task.get('error'))
    
    async def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve task by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow('SELECT * FROM tasks WHERE id = $1', task_id)
            return dict(row) if row else None
    
    async def save_subtask_result(self, result: Dict[str, Any]):
        """Save subtask execution result"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO subtask_results 
                (task_id, subtask_id, agent_id, status, output, error, execution_time)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            ''', result['task_id'], result['subtask_id'], result['agent_id'],
                result['status'], json.dumps(result.get('output')),
                result.get('error'), result['execution_time'])
    
    async def get_subtask_results(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all subtask results for a task"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM subtask_results WHERE task_id = $1 ORDER BY created_at',
                task_id
            )
            return [dict(row) for row in rows]
    
    async def log_agent_activity(
        self, agent_id: str, level: str, message: str,
        task_id: Optional[str] = None, metadata: Optional[Dict] = None
    ):
        """Log agent activity"""
        async with self.pool.acquire() as conn:
            await conn.execute('''
                INSERT INTO agent_logs (agent_id, task_id, log_level, message, metadata)
                VALUES ($1, $2, $3, $4, $5)
            ''', agent_id, task_id, level, message, json.dumps(metadata or {}))

# Global instance
db_manager = DatabaseManager()
```

### 3.4 Redis Manager (`shared/redis_manager.py`)

```python
import redis.asyncio as aioredis
import json
from typing import Optional, Dict, Any, List
from shared.config import settings

class RedisManager:
    """Manages Redis connections for queuing, caching, and coordination"""
    
    def __init__(self):
        self.redis: Optional[aioredis.Redis] = None
        self.pubsub = None
    
    async def initialize(self):
        """Initialize Redis connection"""
        self.redis = await aioredis.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/{settings.REDIS_DB}",
            encoding="utf-8",
            decode_responses=True
        )
        self.pubsub = self.redis.pubsub()
    
    async def close(self):
        """Close Redis connection"""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis:
            await self.redis.close()
    
    # Task Queue Operations
    async def enqueue_task(self, queue_name: str, task_data: Dict[str, Any]):
        """Add task to queue"""
        await self.redis.rpush(queue_name, json.dumps(task_data))
    
    async def dequeue_task(self, queue_name: str, timeout: int = 0) -> Optional[Dict[str, Any]]:
        """Remove and return task from queue (blocking)"""
        result = await self.redis.blpop(queue_name, timeout=timeout)
        if result:
            _, data = result
            return json.loads(data)
        return None
    
    async def get_queue_length(self, queue_name: str) -> int:
        """Get number of items in queue"""
        return await self.redis.llen(queue_name)
    
    # Agent Management
    async def register_agent(self, agent_id: str, agent_data: Dict[str, Any]):
        """Register agent with Redis"""
        await self.redis.hset(f"agent:{agent_id}", mapping={
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            for k, v in agent_data.items()
        })
        await self.redis.sadd("active_agents", agent_id)
        await self.redis.expire(f"agent:{agent_id}", 60)  # Expire in 60s
    
    async def update_agent_status(self, agent_id: str, updates: Dict[str, Any]):
        """Update agent status"""
        await self.redis.hset(f"agent:{agent_id}", mapping={
            k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
            for k, v in updates.items()
        })
        await self.redis.expire(f"agent:{agent_id}", 60)
    
    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent status"""
        data = await self.redis.hgetall(f"agent:{agent_id}")
        if not data:
            return None
        
        result = {}
        for k, v in data.items():
            try:
                result[k] = json.loads(v)
            except (json.JSONDecodeError, TypeError):
                result[k] = v
        return result
    
    async def get_all_agents(self) -> List[str]:
        """Get all registered agent IDs"""
        return list(await self.redis.smembers("active_agents"))
    
    async def get_available_agents(self, capability: Optional[str] = None) -> List[str]:
        """Get available agents, optionally filtered by capability"""
        all_agents = await self.get_all_agents()
        available = []
        
        for agent_id in all_agents:
            status = await self.get_agent_status(agent_id)
            if status and status.get('is_available'):
                if capability is None or capability in status.get('capabilities', []):
                    available.append(agent_id)
        
        return available
    
    # Distributed Locking
    async def acquire_lock(self, lock_name: str, timeout: int = 10) -> bool:
        """Acquire distributed lock"""
        acquired = await self.redis.set(f"lock:{lock_name}", "1", nx=True, ex=timeout)
        return bool(acquired)
    
    async def release_lock(self, lock_name: str):
        """Release distributed lock"""
        await self.redis.delete(f"lock:{lock_name}")
    
    # Shared State
    async def set_shared_state(self, key: str, value: Any, expire: Optional[int] = None):
        """Set shared state value"""
        await self.redis.set(f"state:{key}", json.dumps(value), ex=expire)
    
    async def get_shared_state(self, key: str) -> Optional[Any]:
        """Get shared state value"""
        value = await self.redis.get(f"state:{key}")
        return json.loads(value) if value else None
    
    async def delete_shared_state(self, key: str):
        """Delete shared state value"""
        await self.redis.delete(f"state:{key}")

# Global instance
redis_manager = RedisManager()
```

### 3.5 Task Analyzer (`orchestrator/task_analyzer.py`)

```python
from typing import List, Dict, Any, Set
from shared.