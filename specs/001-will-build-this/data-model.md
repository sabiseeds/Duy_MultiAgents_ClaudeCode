# Data Model

## Entity Definitions

### Task
**Description**: User-submitted work request that gets decomposed into subtasks

**Fields**:
- `id` (string, PK): Unique identifier (format: `task_{uuid}`)
- `user_id` (string): Identifier of user who submitted task
- `description` (string): Natural language task description
- `created_at` (datetime): Submission timestamp (UTC)
- `updated_at` (datetime): Last modification timestamp (UTC)
- `status` (enum: TaskStatus): Current execution status
- `subtasks` (array<SubTask>): List of decomposed subtasks
- `result` (object, nullable): Aggregated final output when complete
- `error` (string, nullable): Error message if failed

**Status Values**:
- `pending`: Task created, subtasks not yet queued
- `in_progress`: At least one subtask executing or queued
- `completed`: All subtasks completed successfully
- `failed`: At least one subtask failed critically
- `cancelled`: User cancelled execution

**Validation Rules**:
- description: Min length 10 characters, max 5000 characters
- user_id: Non-empty string
- created_at <= updated_at
- If status is "completed", result must be non-null
- If status is "failed", error must be non-null

**State Transitions**:
```
pending → in_progress (when first subtask queued)
in_progress → completed (when all subtasks complete)
in_progress → failed (when critical subtask fails)
pending/in_progress → cancelled (user action)
failed → in_progress (on manual retry)
```

---

### SubTask
**Description**: Individual unit of work within a task

**Fields**:
- `id` (string, PK): Unique identifier (format: `subtask_{uuid}`)
- `description` (string): Clear description of work to be done
- `required_capabilities` (array<AgentCapability>): Capabilities needed to execute
- `dependencies` (array<string>): IDs of subtasks that must complete first
- `priority` (integer): Execution priority (0-10, higher = more urgent)
- `estimated_duration` (integer, nullable): Expected seconds to complete
- `input_data` (object): Additional context or parameters

**Validation Rules**:
- description: Min length 10 characters, max 1000 characters
- required_capabilities: At least one capability, all must be valid enum values
- dependencies: Cannot contain own ID (no self-dependency)
- priority: Range 0-10 inclusive
- estimated_duration: If present, must be > 0

**Dependency Rules**:
- All referenced dependency IDs must exist in same task's subtasks
- No circular dependencies allowed (validated by graph algorithm)
- Subtask can only execute when all dependencies have status "completed"

---

### Agent
**Description**: Independent execution unit (Claude Agent SDK instance)

**Fields**:
- `agent_id` (string, PK): Unique identifier (format: `agent_{number}`)
- `port` (integer): Network port for HTTP endpoint
- `is_available` (boolean): Whether agent can accept new tasks
- `current_task` (string, nullable): ID of subtask currently executing
- `capabilities` (array<AgentCapability>): Agent's specializations
- `cpu_usage` (float): Current CPU utilization percentage (0-100)
- `memory_usage` (float): Current memory utilization percentage (0-100)
- `tasks_completed` (integer): Total subtasks completed by this agent
- `last_heartbeat` (datetime): Timestamp of most recent heartbeat

**Validation Rules**:
- port: Must be in range 8001-8005
- capabilities: At least one capability required
- cpu_usage: Range 0-100
- memory_usage: Range 0-100
- tasks_completed: >= 0
- If is_available is false, current_task should be non-null
- Agent considered "dead" if (now - last_heartbeat) > 60 seconds

---

### SubTaskResult
**Description**: Output from completed subtask execution

**Fields**:
- `task_id` (string, FK → Task): Parent task identifier
- `subtask_id` (string): Subtask identifier
- `agent_id` (string, FK → Agent): Agent that executed this subtask
- `status` (enum: TaskStatus): Execution outcome
- `output` (object, nullable): Result data if successful
- `error` (string, nullable): Error message if failed
- `execution_time` (float): Seconds taken to execute
- `created_at` (datetime): Completion timestamp

**Status Values** (subset of TaskStatus):
- `completed`: Subtask executed successfully
- `failed`: Subtask execution encountered error

**Validation Rules**:
- If status is "completed", output must be non-null
- If status is "failed", error must be non-null
- execution_time: Must be > 0

---

### AgentCapability
**Description**: Categorization of agent specialization

**Enum Values**:
- `data_analysis`: Statistical analysis, data visualization, report generation
- `web_scraping`: HTTP requests, HTML parsing, web data extraction
- `code_generation`: Writing code, refactoring, code analysis
- `file_processing`: File I/O, format conversion, data transformation
- `database_operations`: SQL queries, schema changes, data migration
- `api_integration`: External API calls, authentication, response handling

**Validation**: All capability strings must match one of these enum values exactly

---

### TaskQueue
**Description**: Ordered collection of subtasks awaiting execution

**Structure** (Redis LIST, not persisted in database):
- Queue name: `agent_tasks`
- Item format: JSON object with:
  - `task_id` (string): Parent task ID
  - `subtask` (SubTask): Full subtask object
  - `context` (object): Results from dependency subtasks

**Operations**:
- RPUSH: Add subtask to end of queue (enqueue)
- BLPOP: Remove and return first subtask (dequeue, blocking)
- LLEN: Get current queue length

---

### SharedState
**Description**: Key-value storage for inter-agent coordination

**Structure** (Redis STRING, TTL-based expiration):
- Key format: `state:{key_name}`
- Value: JSON-encoded data
- TTL: Configurable expiration time (default: 1 hour)

**Operations**:
- SET: Store value with key and optional TTL
- GET: Retrieve value by key
- DELETE: Remove key

**Use Cases**:
- Agents sharing intermediate results
- Coordination flags between agents
- Cached computations for reuse

---

## Relationships

```
Task (1) ─── (N) SubTask
  - One task contains zero or more subtasks
  - Subtasks reference parent task via task_id (not stored in subtask itself)

SubTask (N) ─── (N) SubTask (via dependencies)
  - Subtasks can depend on other subtasks in same task
  - Represented as array of dependency IDs
  - No circular dependencies enforced at creation

SubTask (N) ─── (1) Agent (via assignment)
  - Each subtask assigned to one agent at execution time
  - Agent can execute multiple subtasks sequentially
  - Assignment not persisted in subtask, only in SubTaskResult

Task (1) ─── (N) SubTaskResult
  - One task produces multiple subtask results
  - Foreign key relationship via task_id

SubTaskResult (N) ─── (1) Agent
  - Each result produced by one agent
  - Agent can produce many results over time
  - Foreign key relationship via agent_id
```

---

## Database Schema (PostgreSQL)

```sql
-- Tasks table
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    description TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
    subtasks JSONB,
    result JSONB,
    error TEXT,
    CONSTRAINT description_length CHECK (LENGTH(description) BETWEEN 10 AND 5000)
);

-- Indexes for fast lookups
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);

-- Subtask results table
CREATE TABLE subtask_results (
    id SERIAL PRIMARY KEY,
    task_id TEXT NOT NULL,
    subtask_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
    output JSONB,
    error TEXT,
    execution_time FLOAT NOT NULL CHECK (execution_time > 0),
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
    CHECK ((status = 'completed' AND output IS NOT NULL) OR (status = 'failed' AND error IS NOT NULL))
);

-- Indexes for subtask results
CREATE INDEX idx_subtask_results_task ON subtask_results(task_id);
CREATE INDEX idx_subtask_results_agent ON subtask_results(agent_id);
CREATE INDEX idx_subtask_results_created ON subtask_results(created_at DESC);

-- Agent logs table
CREATE TABLE agent_logs (
    id SERIAL PRIMARY KEY,
    agent_id TEXT NOT NULL,
    task_id TEXT,
    log_level TEXT NOT NULL CHECK (log_level IN ('INFO', 'DEBUG', 'ERROR', 'WARN')),
    message TEXT NOT NULL,
    metadata JSONB,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
);

-- Indexes for log queries
CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_id);
CREATE INDEX idx_agent_logs_task ON agent_logs(task_id);
CREATE INDEX idx_agent_logs_level ON agent_logs(log_level);
CREATE INDEX idx_agent_logs_created ON agent_logs(created_at DESC);
```

---

## Redis Data Structures

```
# Queues (LIST)
agent_tasks → ["task_data_1", "task_data_2", ...]
agent_results → ["result_data_1", "result_data_2", ...]

# Agent Registry (SET)
active_agents → {"agent_1", "agent_2", "agent_3", "agent_4", "agent_5"}

# Agent Status (HASH per agent, TTL=60s)
agent:agent_1 → {
  "agent_id": "agent_1",
  "port": "8001",
  "is_available": "true",
  "current_task": "null",
  "capabilities": "[\"data_analysis\", \"code_generation\"]",
  "cpu_usage": "25.5",
  "memory_usage": "42.0",
  "tasks_completed": "15",
  "sdk_enabled": "true"
}

# Shared State (STRING with TTL)
state:{key} → "{\"data\": \"value\"}"

# Distributed Locks (STRING with TTL)
lock:{resource} → "1"
```

---

## Pydantic Models (Code Reference)

```python
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class AgentCapability(str, Enum):
    DATA_ANALYSIS = "data_analysis"
    WEB_SCRAPING = "web_scraping"
    CODE_GENERATION = "code_generation"
    FILE_PROCESSING = "file_processing"
    DATABASE_OPERATIONS = "database_operations"
    API_INTEGRATION = "api_integration"

class SubTask(BaseModel):
    id: str
    description: str
    required_capabilities: List[AgentCapability]
    dependencies: List[str] = []
    priority: int = Field(default=5, ge=0, le=10)
    estimated_duration: Optional[int] = None
    input_data: Dict[str, Any] = {}

class Task(BaseModel):
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
    task_id: str
    subtask_id: str
    agent_id: str
    status: TaskStatus
    output: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time: float
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AgentStatus(BaseModel):
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
    task_id: str
    subtask: SubTask
    task_context: Dict[str, Any] = {}
```
