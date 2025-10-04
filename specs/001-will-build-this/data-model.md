# Data Model: Claude Token SDK Migration

**Date**: 2025-10-04
**Feature**: Authentication migration - no changes to core data models

---

## Overview

This migration does not introduce new data entities. The existing data models (`Task`, `SubTask`, `SubTaskResult`, `AgentStatus`) remain unchanged. This document focuses on configuration and authentication-related data structures.

---

## Configuration Model

### Settings (Extended)

**Location**: `shared/config.py`

**Purpose**: Application configuration loaded from environment variables

**Existing Fields** (unchanged):
```python
ANTHROPIC_API_KEY: str
POSTGRES_URL: str = "postgresql://postgres:postgres@192.168.1.33:5432/multi_agent_db"
REDIS_URL: str = "redis://localhost:6379/0"
AGENT_ID: Optional[str] = None
AGENT_PORT: Optional[int] = None
AGENT_CAPABILITIES: Optional[str] = None
```

**New Fields** (added for Claude Code support):
```python
# Claude Code Integration
CLAUDECODE: str = Field(
    default="0",
    description="Claude Code environment flag (1=enabled, 0=disabled)"
)

CLAUDE_CODE_PATH: str = Field(
    default="claude",
    description="Path to Claude CLI executable"
)

CLAUDE_MODEL: str = Field(
    default="claude-sonnet-4-20250514",
    description="Claude model to use for task execution"
)

CLAUDE_PERMISSION_MODE: str = Field(
    default="bypassPermissions",
    description="SDK permission mode (auto|approveEdits|approveAll|bypassPermissions)"
)
```

**Validation Rules**:
- `CLAUDECODE` must be "0" or "1"
- `CLAUDE_PERMISSION_MODE` must be one of: `auto`, `approveEdits`, `approveAll`, `bypassPermissions`
- At least one authentication method must be available (CLAUDECODE=1 OR ANTHROPIC_API_KEY set)

**Usage**:
```python
from shared.config import settings

# Check which authentication method to use
if settings.CLAUDECODE == "1":
    # Use Claude Code integrated auth
    pass
elif settings.ANTHROPIC_API_KEY:
    # Use direct API auth
    pass
else:
    raise ValueError("No authentication method configured")
```

---

## Authentication Client Model

### HybridClaudeClient

**Location**: `shared/auth_client.py` (new file)

**Purpose**: Unified interface for Claude authentication that automatically selects between Claude Code and direct API

**Fields**:
```python
auth_method: str  # "claude_code" | "direct_api"
model: str  # Claude model name
permission_mode: str  # SDK permission mode
max_retries: int  # Number of retry attempts
timeout: float  # Request timeout in seconds
```

**Methods**:
```python
__init__(config: Optional[AuthConfig] = None)
    # Initialize with configuration
    # Auto-detects authentication method

_detect_auth_method() -> str
    # Returns: "claude_code" or "direct_api"
    # Logic: Check CLAUDECODE=1, fallback to API key

async query(prompt: str, system_prompt: Optional[str] = None) -> str
    # Execute Claude query using detected auth method
    # Returns: Response text
    # Raises: AuthenticationError, TimeoutError

async _query_claude_code(prompt: str, system_prompt: str) -> str
    # Internal: Query using Claude Code SDK
    # Temporarily removes API key from environment

async _query_direct_api(prompt: str, system_prompt: str) -> str
    # Internal: Query using direct Anthropic API
```

**State Transitions**:
```
Initialization:
  START → Detect Auth Method → READY

Query Execution:
  READY → Remove API Key (if claude_code) → Execute Query → Restore API Key → READY
  READY → Execute Query (if direct_api) → READY
```

**Validation Rules**:
- `auth_method` must be set before querying
- `max_retries` must be >= 0
- `timeout` must be > 0
- System prompt length < 10,000 characters
- User prompt length < 100,000 characters

---

## Authentication Configuration

### AuthConfig (Dataclass)

**Location**: `shared/auth_client.py`

**Purpose**: Type-safe configuration for authentication client

**Fields**:
```python
@dataclass
class AuthConfig:
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 1000
    temperature: float = 0.0
    system_prompt: Optional[str] = None
    permission_mode: str = "bypassPermissions"
    max_retries: int = 3
    timeout: float = 30.0
```

**Factory Methods**:
```python
@classmethod
def from_settings() -> AuthConfig:
    # Create from global Settings instance
    return AuthConfig(
        model=settings.CLAUDE_MODEL,
        permission_mode=settings.CLAUDE_PERMISSION_MODE
    )

@classmethod
def for_task_analyzer() -> AuthConfig:
    # Specific config for task decomposition
    return AuthConfig(
        system_prompt="You are a task decomposition agent...",
        max_tokens=2048
    )

@classmethod
def for_agent_execution() -> AuthConfig:
    # Specific config for task execution
    return AuthConfig(
        system_prompt="You are a specialized agent...",
        max_tokens=4096
    )
```

---

## Error Models

### AuthenticationError (Exception)

**Location**: `shared/exceptions.py` (new or existing)

**Purpose**: Specific exception for authentication failures

**Fields**:
```python
class AuthenticationError(Exception):
    message: str  # Error description
    auth_method: str  # Which method failed
    suggestion: str  # Actionable remediation
```

**Examples**:
```python
# No auth method available
AuthenticationError(
    message="No authentication method configured",
    auth_method="none",
    suggestion="Set CLAUDECODE=1 or provide ANTHROPIC_API_KEY in .env"
)

# Claude CLI not found
AuthenticationError(
    message="Claude CLI not found at path: claude",
    auth_method="claude_code",
    suggestion="Install with: npm install -g @anthropic-ai/claude-code"
)

# API key invalid
AuthenticationError(
    message="Invalid ANTHROPIC_API_KEY format",
    auth_method="direct_api",
    suggestion="Ensure API key starts with 'sk-ant-api03-'"
)
```

---

## Existing Data Models (Unchanged)

For reference, these existing models are **not modified** by this migration:

### Task
- Fields: `id`, `user_id`, `description`, `status`, `subtasks`, `result`, `error`, `created_at`, `updated_at`
- Location: `shared/models.py`
- Status: **NO CHANGES**

### SubTask
- Fields: `id`, `description`, `required_capabilities`, `dependencies`, `priority`, `estimated_duration`
- Location: `shared/models.py`
- Status: **NO CHANGES**

### SubTaskResult
- Fields: `task_id`, `subtask_id`, `agent_id`, `status`, `output`, `error`, `execution_time`, `created_at`
- Location: `shared/models.py`
- Status: **NO CHANGES**

### AgentStatus
- Fields: `agent_id`, `capabilities`, `is_available`, `current_task`, `cpu_usage`, `memory_usage`, `tasks_completed`, `last_heartbeat`
- Location: `shared/models.py`
- Status: **NO CHANGES**

---

## Database Schema (Unchanged)

No database migrations required. Existing tables remain unchanged:
- `tasks`
- `subtask_results`
- `agent_logs`

---

## Redis Keys (Unchanged)

No changes to Redis data structures:
- `agent_tasks` (LIST)
- `agent_results` (LIST)
- `agent:{agent_id}` (HASH)
- `active_agents` (SET)

---

## Summary

**New Models**:
1. `Settings` - Extended with 4 new Claude Code fields
2. `HybridClaudeClient` - Authentication abstraction layer
3. `AuthConfig` - Configuration dataclass
4. `AuthenticationError` - Specific exception type

**Unchanged Models**:
- All existing task/agent data models remain identical
- No database schema changes
- No Redis structure changes

**Validation Impact**:
- Settings validation enforced via Pydantic
- Authentication method validation at client initialization
- Existing validators for Task/SubTask/etc unchanged
