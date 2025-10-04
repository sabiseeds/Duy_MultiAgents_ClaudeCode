# Research & Technical Decisions

## Claude Agent SDK Integration

**Decision**: Use official Claude Agent SDK (`claude-agent-sdk[all]>=1.0.0`) for all agent implementations

**Rationale**:
- Native tool integration via MCP servers (database, files, APIs)
- Built-in file operations (Read, Write, Bash) without custom implementation
- Subagent delegation for parallel specialized subtasks
- Checkpoint system for saving/restoring state in long tasks
- Automated hooks for triggering actions at specific points
- Configurable permission modes (approveEdits, approveAll, auto)
- Context as file system (navigate folders instead of prompt stuffing)

**Alternatives Considered**:
- Direct Anthropic API calls: Would require manual tool implementation, no native file ops, no checkpoints
- LangChain agents: Less integrated with Claude, more abstraction overhead
- Custom agent framework: Significant development time, reinventing solved problems

**Implementation Details**:
- ClaudeSDKClient with ClaudeAgentOptions for configuration
- MCP server creation via `create_sdk_mcp_server` with custom tools
- Task-specific workspaces with context/output/temp directories
- System prompts define agent capabilities and available tools
- Permission mode set via environment variable (SDK_PERMISSION_MODE)

---

## Task Decomposition Strategy

**Decision**: Use Claude API with prompt engineering for task analysis and decomposition

**Rationale**:
- Leverages Claude's natural language understanding and reasoning
- Can identify task dependencies through context analysis
- Estimates execution duration and priority based on task complexity
- Determines required capabilities from task description

**Alternatives Considered**:
- Rule-based decomposition: Too rigid, cannot handle diverse task types
- Fine-tuned model: Expensive, requires training data, maintenance overhead
- Manual decomposition: Defeats purpose of automated system

**Implementation Approach**:
```python
# Prompt structure
"""
Analyze and decompose this task into subtasks.
Task: {description}
Available capabilities: {capabilities_list}

For each subtask specify:
1. description (clear and specific)
2. required_capabilities (from list above)
3. dependencies (0-based subtask indices)
4. priority (0-10, higher = more important)
5. estimated_duration (seconds)

Respond with JSON array: [{"description": "...", ...}]
"""
```

**Output Handling**:
- Extract JSON array from Claude response via regex
- Map subtask indices to generated IDs for dependency tracking
- Fallback to single subtask if decomposition fails
- Validate that capabilities exist in system

---

## Message Queue Architecture

**Decision**: Redis LIST data structures with BLPOP/RPUSH for task and result queues

**Rationale**:
- Atomic operations ensure no race conditions
- BLPOP provides blocking dequeue (efficient waiting)
- Simple pub/sub for broadcasting
- Supports distributed coordination across services
- Low latency (<1ms for queue operations)

**Alternatives Considered**:
- RabbitMQ: Additional service dependency, higher complexity
- Kafka: Overkill for this scale, complex setup
- PostgreSQL LISTEN/NOTIFY: Less reliable for queuing, polling overhead
- In-memory queues: Not distributed, lost on restart

**Queue Design**:
```
agent_tasks (LIST)
  → Subtasks awaiting execution
  → Format: {"task_id": "...", "subtask": {...}, "context": {...}}
  → Producers: Orchestrator (initial tasks, newly-ready tasks)
  → Consumers: Task dispatcher (background worker)

agent_results (LIST)
  → Completed subtask results
  → Format: {"task_id": "...", "subtask_id": "...", "agent_id": "...", "status": "...", "output": {...}}
  → Producers: Agent services (after subtask execution)
  → Consumers: Result processor (background worker)
```

**Error Handling**:
- Failed dequeue returns None (handled gracefully)
- Re-queue on assignment failure
- Timeout for BLPOP prevents indefinite blocking

---

## Agent Capability Matching

**Decision**: Enum-based static capability assignment with Redis-based agent registry

**Rationale**:
- Predictable routing (agents don't change capabilities at runtime)
- Fast lookup via Redis SET for active agents + HASH for capabilities
- No complex scoring or load balancing initially (first available)
- Clear categorization of agent specializations

**Capabilities**:
1. **DATA_ANALYSIS**: Statistical analysis, data visualization, report generation
2. **WEB_SCRAPING**: HTTP requests, HTML parsing, web data extraction
3. **CODE_GENERATION**: Writing code, refactoring, code analysis
4. **FILE_PROCESSING**: File I/O, format conversion, data transformation
5. **DATABASE_OPERATIONS**: SQL queries, schema changes, data migration
6. **API_INTEGRATION**: External API calls, authentication, response handling

**Agent Assignments**:
- Agent 1 (port 8001): DATA_ANALYSIS, CODE_GENERATION
- Agent 2 (port 8002): WEB_SCRAPING, API_INTEGRATION
- Agent 3 (port 8003): FILE_PROCESSING, DATABASE_OPERATIONS
- Agent 4 (port 8004): CODE_GENERATION, API_INTEGRATION
- Agent 5 (port 8005): DATA_ANALYSIS, DATABASE_OPERATIONS

**Matching Algorithm**:
1. For each required capability in subtask (in order)
2. Query Redis for available agents with that capability
3. If found, assign to first available agent
4. If not found, re-queue subtask and retry later

**Future Enhancements** (not in scope):
- Load balancing (least busy agent)
- Capability scoring (match quality)
- Dynamic capability learning

---

## Shared State Management

**Decision**: Hybrid approach using PostgreSQL, Redis, and file storage

**PostgreSQL** (persistent, audit trail):
- `tasks` table: All task data including subtasks (JSONB), status, timestamps
- `subtask_results` table: Individual subtask outputs, execution time, agent_id
- `agent_logs` table: Activity logs for debugging and monitoring

**Redis** (ephemeral, real-time):
- `agent:{agent_id}` HASH: Current agent status (availability, CPU, memory, current_task)
- `active_agents` SET: List of registered agent IDs
- `state:{key}` STRING: Shared state between agents (expire after TTL)
- `lock:{name}` STRING: Distributed locks for coordination

**File Storage** (`./shared_files`):
- `{task_id}/context/`: Task details and previous results (JSON files)
- `{task_id}/output/`: Agent results (result.json, generated files)
- `{task_id}/temp/`: Temporary files during execution

**Rationale**:
- PostgreSQL: Historical queries, complex filtering, ACID guarantees
- Redis: Low-latency reads, TTL expiration, pub/sub notifications
- Files: Large outputs don't bloat database, agents can read/write naturally

**Data Flow**:
1. Task created → PostgreSQL (persistent record)
2. Subtasks queued → Redis LIST (fast distribution)
3. Agent picks subtask → Redis HASH updated (status tracking)
4. Agent writes output → File storage (large data)
5. Result enqueued → Redis LIST (fast notification)
6. Result processed → PostgreSQL (audit trail)

---

## Error Handling and Retry

**Decision**: Explicit failure tracking with manual retry, no automatic retry

**Failure Detection**:
- Agent service catches exceptions during subtask execution
- Sets subtask status to "failed" with error message
- Logs error to PostgreSQL agent_logs table
- Enqueues failure result to result queue

**Dependency Blocking**:
- Result processor checks if failed subtask has dependents
- Marks all dependent subtasks as "blocked" (not queued)
- Updates task status to "failed" if critical path blocked
- User sees which subtask failed and which are blocked

**Manual Retry**:
- User reviews error message in UI
- User can reset failed subtask to "pending"
- System re-queues subtask for execution
- Blocked dependents automatically unblocked when prerequisite succeeds

**Rationale**:
- Auto-retry can cause infinite loops with persistent errors
- Manual intervention allows fixing root cause (bad input, configuration)
- Explicit blocking prevents partial execution of broken workflows
- Audit trail preserved (original failure logged)

**No Retry Scenarios**:
- Invalid input data (user must correct)
- Missing API credentials (user must configure)
- Agent capability mismatch (user must reassign)
- Timeout exceeded (user must adjust task complexity)

---

## Performance Optimization

**Connection Pooling**:
- **PostgreSQL**: asyncpg pool with min_size=2, max_size=20, command_timeout=60s
- **Redis**: Single connection per service, reused for all operations
- **HTTP (agent-to-orchestrator)**: httpx.AsyncClient with timeout=5s

**Rationale**:
- Pool prevents connection creation overhead on every query
- Async operations allow concurrent I/O without blocking
- Timeouts prevent hanging on network issues

**Indexing Strategy**:
```sql
-- Fast task lookups by status/user/time
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_user ON tasks(user_id);
CREATE INDEX idx_tasks_created ON tasks(created_at DESC);

-- Fast subtask result queries
CREATE INDEX idx_subtask_results_task ON subtask_results(task_id);
CREATE INDEX idx_subtask_results_agent ON subtask_results(agent_id);

-- Fast log queries
CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_id);
CREATE INDEX idx_agent_logs_task ON agent_logs(task_id);
CREATE INDEX idx_agent_logs_created ON agent_logs(created_at DESC);
```

**Async/Await Throughout**:
- All I/O operations use async/await (database, Redis, HTTP, file)
- Background workers run as asyncio tasks
- Prevents thread blocking, maximizes concurrency

**Caching** (future enhancement):
- Task decomposition results (avoid re-analyzing identical tasks)
- Agent capability lookups (reduce Redis queries)
- User session data (reduce database hits)

---

## Monitoring and Observability

**Logging**:
- **PostgreSQL `agent_logs` table**: Centralized activity log
  - Columns: agent_id, task_id, log_level (INFO/DEBUG/ERROR), message, metadata (JSONB), created_at
  - Retention: Unlimited (can add partitioning/archiving later)
  - Query: Filter by agent, task, level, time range

**Real-time Monitoring**:
- **Streamlit UI**: Polls orchestrator every 2 seconds
  - GET /tasks/{id}: Task status, subtask progress, agent assignments
  - GET /agents: All agent statuses (availability, CPU, memory, task count)
  - Displays: Progress bar, subtask list with status, agent health dashboard

**Agent Health**:
- **Heartbeat**: Every 10 seconds, agent updates Redis `agent:{id}` with:
  - is_available, current_task, cpu_usage (via psutil), memory_usage (via psutil), tasks_completed
  - TTL set to 60 seconds (agent considered dead if no heartbeat)
- **Detection**: Orchestrator queries Redis for active agents
  - Missing agents (TTL expired) removed from available pool
  - Tasks assigned to dead agents can be detected and reassigned (future enhancement)

**Metrics** (logged in database):
- Task submission time → completion time (end-to-end latency)
- Subtask execution time (per agent, stored in subtask_results.execution_time)
- Queue lengths (agent_tasks, agent_results)
- Agent utilization (% time busy vs idle)
- Error rate (failed subtasks / total subtasks)

**Future Enhancements**:
- Export metrics to Prometheus
- Grafana dashboards
- Alerting on agent failures
- Performance regression detection

---

## Summary

All technical decisions are documented with clear rationale and alternatives considered. No NEEDS CLARIFICATION items remain. System is ready for Phase 1 design.
