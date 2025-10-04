# Multi-Agent Claude System - Complete Specification v2.0
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