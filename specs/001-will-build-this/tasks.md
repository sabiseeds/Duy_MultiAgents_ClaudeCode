# Tasks: Multi-Agent Task Execution System

**Input**: Design documents from `specs/001-will-build-this/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

## Execution Flow
```
1. Load plan.md → Tech stack: Python 3.11+, FastAPI, Claude Agent SDK, PostgreSQL, Redis, Streamlit
2. Load design documents:
   → data-model.md: 7 entities (Task, SubTask, Agent, SubTaskResult, AgentCapability, TaskQueue, SharedState)
   → contracts/: 2 files (orchestrator-api.yaml, agent-api.yaml)
   → quickstart.md: 3 test scenarios (simple task, complex task, agent availability)
3. Generate tasks by category:
   → Setup: Project structure, dependencies, Docker
   → Tests: 5 contract tests, 3 integration tests, 4 unit test suites
   → Core: Models, services, orchestrator, agents, UI
   → Polish: Documentation, scripts
4. Apply TDD ordering: Tests before implementation
5. Mark parallel tasks with [P]
6. Total tasks: 30 (T001-T030)
```

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- Include exact file paths in descriptions

---

## Phase 3.1: Setup (3 tasks)

- [ ] **T001** Create project directory structure
  - Create directories: `shared/`, `orchestrator/`, `agent/`, `ui/`, `tests/contract/`, `tests/integration/`, `tests/unit/`, `shared_files/`, `scripts/`
  - Create all `__init__.py` files in Python packages
  - Create `.env.example` with template variables (ANTHROPIC_API_KEY, POSTGRES_URL, REDIS_URL, SDK_PERMISSION_MODE)
  - Verify structure matches plan.md

- [ ] **T002** Create requirements.txt with all dependencies
  - Add: `fastapi>=0.104.0`, `uvicorn[standard]>=0.24.0`, `claude-agent-sdk[all]>=1.0.0`, `anthropic>=0.7.7`
  - Add: `asyncpg>=0.29.0`, `redis[asyncio]>=5.0.0`, `httpx>=0.25.0`, `psutil>=5.9.0`
  - Add: `streamlit>=1.28.0`, `pydantic>=2.4.0`, `python-dotenv>=1.0.0`
  - Add dev dependencies: `pytest>=7.4.0`, `pytest-asyncio>=0.21.0`, `black>=23.10.0`, `flake8>=6.1.0`

- [ ] **T003** [P] Create Docker configuration files
  - Create `docker-compose.yml` with services: postgres, redis, orchestrator, agent1-5, streamlit
  - Create `Dockerfile.orchestrator` (Python 3.11-slim base, install requirements, run orchestrator)
  - Create `Dockerfile.agent` (Python 3.11-slim base, install requirements, run agent_service)
  - Create `Dockerfile.streamlit` (Python 3.11-slim base, install requirements, run streamlit_app)
  - Configure environment variables, ports (8000-8005, 8501), volumes (shared_files, postgres, redis)

---

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3

**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests (5 tasks, all [P])

- [ ] **T004** [P] Contract test POST /tasks in `tests/contract/test_orchestrator_api.py`
  - Validate request query parameters (description: minLength=10, maxLength=5000, user_id: optional)
  - Test response codes: 200 (success), 400 (invalid description), 500 (decomposition error)
  - Validate response schema: task_id (string), status (enum: created), subtasks_count (integer), initial_subtasks_queued (integer)
  - Assert OpenAPI schema compliance against `contracts/orchestrator-api.yaml`

- [ ] **T005** [P] Contract test GET /tasks/{task_id} in `tests/contract/test_orchestrator_api.py`
  - Test response codes: 200 (task found), 404 (task not found)
  - Validate response schema: task (Task object), subtask_results (array of SubTaskResult)
  - Test Task object fields: id, user_id, description, status, created_at, updated_at, subtasks, result, error
  - Assert OpenAPI schema compliance against `contracts/orchestrator-api.yaml`

- [ ] **T006** [P] Contract test GET /agents in `tests/contract/test_orchestrator_api.py`
  - Test response code: 200
  - Validate response schema: agents (array of AgentStatus objects)
  - Test AgentStatus fields: agent_id, port, is_available, current_task, capabilities, cpu_usage, memory_usage, tasks_completed, last_heartbeat
  - Assert OpenAPI schema compliance against `contracts/orchestrator-api.yaml`

- [ ] **T007** [P] Contract test GET /health in `tests/contract/test_agent_api.py`
  - Test response code: 200
  - Validate response schema: status (enum: healthy), agent_id (string), is_available (boolean), current_task (nullable string), sdk_version (string)
  - Assert OpenAPI schema compliance against `contracts/agent-api.yaml`

- [ ] **T008** [P] Contract test POST /execute in `tests/contract/test_agent_api.py`
  - Validate request schema: task_id (string), subtask (SubTask object), task_context (object)
  - Test response codes: 200 (accepted), 503 (agent busy)
  - Validate response schema: status (enum: accepted), agent_id (string)
  - Assert OpenAPI schema compliance against `contracts/agent-api.yaml`

### Integration Tests (3 tasks, all [P])

- [ ] **T009** [P] Integration test: End-to-end simple task in `tests/integration/test_end_to_end.py`
  - Scenario: Submit task "Calculate factorial of 10" → Verify task created → Poll until status=completed → Verify result contains factorial_10=3628800
  - Assert: Task transitions from pending → in_progress → completed
  - Assert: Subtask count = 1, single subtask result, execution_time > 0
  - Verify: Database records in tasks and subtask_results tables
  - This tests quickstart.md Step 3 scenario

- [ ] **T010** [P] Integration test: Multi-step task lifecycle in `tests/integration/test_task_lifecycle.py`
  - Scenario: Submit complex task requiring 3 subtasks with dependencies
  - Assert: Task decomposed into subtasks with correct required_capabilities
  - Assert: Subtasks execute in dependency order (dependent waits for prerequisite)
  - Assert: Final result aggregates all subtask outputs
  - Verify: All subtask_results have correct agent_id assignments

- [ ] **T011** [P] Integration test: Agent coordination and failure handling in `tests/integration/test_agent_coordination.py`
  - Scenario: Submit task with 2 parallel subtasks → One subtask fails
  - Assert: Failed subtask has status=failed, error message populated
  - Assert: Dependent subtasks blocked (not executed)
  - Assert: Task status transitions to failed
  - Verify: Agent logs contain error details in agent_logs table

### Unit Tests (4 suites, all [P])

- [ ] **T012** [P] Unit tests for Pydantic models in `tests/unit/test_models.py`
  - Test Task model: validation rules (description length 10-5000, status enum, created_at <= updated_at)
  - Test SubTask model: validation rules (priority 0-10, required_capabilities non-empty, no self-dependencies)
  - Test AgentStatus model: validation rules (port 8001-8005, cpu_usage 0-100, memory_usage 0-100)
  - Test SubTaskResult model: validation rules (completed requires output, failed requires error, execution_time > 0)
  - Test serialization/deserialization to JSON

- [ ] **T013** [P] Unit tests for database operations in `tests/unit/test_database.py`
  - Test DatabaseManager: connection pool creation (min_size=2, max_size=20)
  - Test create_task(): Insert task, verify returned Task object, check database record
  - Test get_task(): Retrieve task by ID, handle not found case
  - Test update_task_status(): Update status, verify updated_at timestamp changes
  - Test save_subtask_result(): Insert result, verify foreign key constraints
  - Test query with indexes: Filter by status, user_id, created_at (verify query performance)

- [ ] **T014** [P] Unit tests for Redis operations in `tests/unit/test_redis_manager.py`
  - Test RedisManager: connection creation and reuse
  - Test enqueue_task(): RPUSH to agent_tasks, verify LLEN increases
  - Test dequeue_task(): BLPOP from agent_tasks, verify returns correct item, timeout handling
  - Test enqueue_result(): RPUSH to agent_results
  - Test update_agent_status(): HSET to agent:{id}, verify TTL=60s, verify fields
  - Test get_available_agents(): Query active_agents SET, filter by capability

- [ ] **T015** [P] Unit tests for task decomposition in `tests/unit/test_task_analyzer.py`
  - Test TaskAnalyzer.decompose_task(): Call Claude API with prompt, verify subtasks extracted
  - Test: Simple task → 1 subtask with correct capability
  - Test: Complex task → Multiple subtasks with dependencies array
  - Test: Invalid task description → Fallback to single subtask
  - Test: Prompt engineering structure (includes available capabilities, asks for JSON response)
  - Mock Claude API responses to avoid actual API calls

---

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Shared Components (4 tasks)

- [ ] **T016** [P] Implement `shared/models.py` (Pydantic models)
  - Implement TaskStatus enum (PENDING, IN_PROGRESS, COMPLETED, FAILED, CANCELLED)
  - Implement AgentCapability enum (DATA_ANALYSIS, WEB_SCRAPING, CODE_GENERATION, FILE_PROCESSING, DATABASE_OPERATIONS, API_INTEGRATION)
  - Implement SubTask model with validation (Field validators for priority, dependencies)
  - Implement Task model with validation
  - Implement SubTaskResult model with conditional validation (completed/failed)
  - Implement AgentStatus model
  - Implement TaskExecutionRequest model
  - All models should match data-model.md and contracts

- [ ] **T017** [P] Implement `shared/config.py` (Settings class)
  - Create Settings class using pydantic BaseSettings
  - Load from environment: ANTHROPIC_API_KEY, POSTGRES_URL, REDIS_URL, SDK_PERMISSION_MODE
  - Provide defaults: POSTGRES_URL=postgresql://postgres:postgres@localhost:5432/multi_agent_db
  - Provide defaults: REDIS_URL=redis://localhost:6379/0
  - Validate: ANTHROPIC_API_KEY must be non-empty
  - Export singleton: `settings = Settings()`

- [ ] **T018** Implement `shared/database.py` (DatabaseManager with connection pool)
  - Create DatabaseManager class with asyncpg pool
  - Method: `async def connect()`: Create pool with min_size=2, max_size=20, command_timeout=60
  - Method: `async def disconnect()`: Close pool
  - Method: `async def create_task(task: Task) -> Task`: INSERT task, return Task
  - Method: `async def get_task(task_id: str) -> Optional[Task]`: SELECT task by ID
  - Method: `async def update_task_status(task_id: str, status: TaskStatus, result/error)`: UPDATE task
  - Method: `async def save_subtask_result(result: SubTaskResult)`: INSERT subtask_results
  - Method: `async def get_subtask_results(task_id: str) -> List[SubTaskResult]`: SELECT results by task_id
  - Method: `async def log_agent_activity(agent_id, task_id, level, message, metadata)`: INSERT agent_logs
  - Execute schema from data-model.md on first connection (CREATE TABLE IF NOT EXISTS)

- [ ] **T019** Implement `shared/redis_manager.py` (RedisManager for queues and agent registry)
  - Create RedisManager class with redis.asyncio client
  - Method: `async def connect()`: Create Redis connection
  - Method: `async def disconnect()`: Close connection
  - Method: `async def enqueue_task(task_id: str, subtask: SubTask, context: dict)`: RPUSH to agent_tasks
  - Method: `async def dequeue_task(timeout: int = 5) -> Optional[dict]`: BLPOP from agent_tasks
  - Method: `async def enqueue_result(result: SubTaskResult)`: RPUSH to agent_results
  - Method: `async def dequeue_result(timeout: int = 5) -> Optional[SubTaskResult]`: BLPOP from agent_results
  - Method: `async def register_agent(agent_id: str)`: SADD to active_agents
  - Method: `async def update_agent_status(agent_status: AgentStatus)`: HSET to agent:{id}, EXPIRE 60s
  - Method: `async def get_available_agents(capability: Optional[AgentCapability]) -> List[str]`: Query active_agents, filter by capability from hash

### Orchestrator Service (4 tasks)

- [ ] **T020** Implement `orchestrator/task_analyzer.py` (Claude API for task decomposition)
  - Create TaskAnalyzer class
  - Method: `async def decompose_task(description: str) -> List[SubTask]`
  - Use anthropic.AsyncAnthropic client with settings.ANTHROPIC_API_KEY
  - Construct prompt: "Analyze and decompose this task... Available capabilities: [list]... Respond with JSON array: [{description, required_capabilities, dependencies, priority, estimated_duration}]"
  - Call Claude API: `client.messages.create(model="claude-3-5-sonnet-20241022", messages=[...])`
  - Extract JSON from response via regex
  - Map subtask indices to generated UUIDs (subtask_{uuid})
  - Fallback: If decomposition fails, return single subtask with all capabilities
  - Return List[SubTask]

- [ ] **T021** Implement `orchestrator/orchestrator.py` (FastAPI app with endpoints)
  - Create FastAPI app instance
  - Initialize DatabaseManager, RedisManager on startup
  - Endpoint: POST /tasks (query params: description, user_id) → Create Task, decompose via TaskAnalyzer, save to DB, enqueue ready subtasks (no dependencies), return task_id
  - Endpoint: GET /tasks/{task_id} → Get task from DB, get subtask_results from DB, return combined response
  - Endpoint: GET /agents → Get all agents from Redis (query active_agents, get status hashes), return agents list
  - Endpoint: GET /agents/available (query param: capability) → Filter agents by capability, return available_agents list
  - Error handling: Return 400 for invalid description, 404 for task not found, 500 for internal errors

- [ ] **T022** Implement background worker: `dispatch_tasks()` in `orchestrator/orchestrator.py`
  - Create async background task that runs continuously
  - Loop: Check agent_tasks queue length via RedisManager
  - For each ready subtask (dependencies satisfied):
    - Find available agent with required capabilities via RedisManager.get_available_agents()
    - If agent found: Send POST /execute to agent endpoint (http://localhost:{port}/execute)
    - If agent accepts: Update agent status to busy in Redis
    - If no agent available: Re-queue subtask and retry later
  - Sleep 1 second between iterations
  - Handle errors: Log failed assignments, re-queue subtask

- [ ] **T023** Implement background worker: `process_results()` in `orchestrator/orchestrator.py`
  - Create async background task that runs continuously
  - Loop: Dequeue from agent_results via RedisManager.dequeue_result()
  - Save result to database via DatabaseManager.save_subtask_result()
  - Check if all subtasks for task completed: Query subtask_results count vs subtasks count
  - If all completed: Aggregate results, update task status to completed, set task.result
  - If any failed: Check dependencies, mark dependent subtasks as blocked, update task status to failed
  - Check for newly ready subtasks (dependencies satisfied): Enqueue via RedisManager.enqueue_task()
  - Update agent status to available in Redis
  - Sleep 0.5 seconds between iterations

### Agent Service (2 tasks)

- [ ] **T024** Implement `agent/agent_service.py` (Claude SDK integration with FastAPI)
  - Create FastAPI app instance with agent_id and port from environment (AGENT_ID, AGENT_PORT)
  - Initialize capabilities from environment (AGENT_CAPABILITIES comma-separated)
  - Create ClaudeSDKClient with ClaudeAgentOptions (permission_mode from settings.SDK_PERMISSION_MODE)
  - Create MCP server via `create_sdk_mcp_server()` with custom tools (database access, file operations)
  - Endpoint: GET /health → Return status=healthy, agent_id, is_available, current_task, sdk_version
  - Endpoint: GET /status → Return full AgentStatus (cpu_usage via psutil.cpu_percent(), memory_usage via psutil.virtual_memory().percent)
  - Endpoint: POST /execute → Accept TaskExecutionRequest, validate agent available, execute subtask via Claude SDK, enqueue result to Redis, return status=accepted
  - Background task: Send heartbeat every 10 seconds via RedisManager.update_agent_status()
  - Error handling: Return 503 if agent busy

- [ ] **T025** Implement MCP server tools in `agent/agent_service.py`
  - Tool: `database_query(query: str)` → Execute read-only SQL query via DatabaseManager, return results
  - Tool: `read_file(path: str)` → Read file from shared_files/{task_id}/, return contents
  - Tool: `write_file(path: str, content: str)` → Write file to shared_files/{task_id}/output/, return success
  - Tool: `get_shared_state(key: str)` → GET from Redis state:{key}, return value
  - Tool: `set_shared_state(key: str, value: str, ttl: int)` → SET to Redis state:{key} with TTL
  - Tool: `embedding_search(query: str)` → Placeholder for future embedding search (return empty for now)
  - Register tools with MCP server during initialization

### Streamlit UI (1 task)

- [ ] **T026** Implement `ui/streamlit_app.py` (Dashboard for task submission and monitoring)
  - Title: "Multi-Agent Task Execution System"
  - Section 1: Task Submission
    - Text area: Task description input
    - Button: "Submit Task" → POST to /tasks, display returned task_id
  - Section 2: Task Monitoring
    - Input: Task ID to monitor
    - Button: "Refresh Status" → GET /tasks/{id}, display task status, subtasks, results
    - Auto-refresh: Poll every 2 seconds if task is in_progress
    - Display: Progress bar (completed subtasks / total subtasks)
  - Section 3: Agent Dashboard
    - Display: GET /agents → Show table with agent_id, is_available, current_task, capabilities, cpu_usage, memory_usage, tasks_completed
    - Auto-refresh: Poll every 5 seconds
  - Section 4: Agent Logs
    - Display: Recent logs from agent_logs table (via custom endpoint or direct DB query)
    - Filter by: agent_id, log_level, time range
  - Error handling: Display error messages in red if API calls fail

---

## Phase 3.4: Integration (1 task)

- [ ] **T027** End-to-end integration: Connect all services and verify communication
  - Verify orchestrator can connect to PostgreSQL and Redis on startup
  - Verify agents register themselves in Redis on startup (via heartbeat)
  - Verify orchestrator dispatch_tasks() can assign tasks to agents
  - Verify agents can execute subtasks and enqueue results
  - Verify orchestrator process_results() can aggregate results and update task status
  - Verify Streamlit UI can communicate with orchestrator API
  - Test: Start all services via Docker Compose, run quickstart.md Step 3 scenario
  - Assert: All 5 agents show in /agents endpoint within 30 seconds
  - Assert: Simple task completes successfully end-to-end

---

## Phase 3.5: Polish (3 tasks)

- [ ] **T028** [P] Implement utility scripts in `scripts/`
  - Create `scripts/start.sh`: Run `docker-compose up -d`, wait for services, verify health
  - Create `scripts/stop.sh`: Run `docker-compose down`
  - Create `scripts/test_system.py`: Automated system test (submit 3 tasks, verify all complete, check agent utilization)
  - Make all scripts executable: `chmod +x scripts/*.sh`

- [ ] **T029** [P] Create documentation files
  - Create `README.md`: Project overview, architecture diagram, quickstart link, contributing guidelines
  - Update `.env.example`: Add comments explaining each variable
  - Create `docs/api.md`: Document all orchestrator and agent endpoints with examples (copy from contracts/)
  - Create `docs/architecture.md`: Explain system design, data flow, technologies used (reference research.md and plan.md)

- [ ] **T030** Run validation checklist from quickstart.md
  - Execute all steps in quickstart.md (Steps 1-5)
  - Verify all validation checklist items pass
  - Run performance benchmarks: Measure API latency (<200ms p95), task throughput (10+ parallel tasks), memory usage (<2GB per agent)
  - Run coverage report: `pytest --cov=. tests/` → Assert ≥80% coverage
  - Run linting: `flake8 .` and `black --check .` → Assert no errors
  - Document results: Create `VALIDATION.md` with benchmark results and coverage report

---

## Dependencies

**Critical TDD Order**:
- Tests (T004-T015) MUST be written and MUST FAIL before implementation (T016-T027)

**Setup Blocks Everything**:
- T001-T003 must complete before any other tasks

**Shared Components Block Services**:
- T016 (models.py) blocks: T018, T020, T021, T024
- T017 (config.py) blocks: T018, T019, T020, T024
- T018 (database.py) blocks: T020, T021, T022, T023, T024
- T019 (redis_manager.py) blocks: T020, T021, T022, T023, T024

**Orchestrator Components Sequential**:
- T020 (task_analyzer.py) blocks T021 (orchestrator.py)
- T021 (orchestrator.py) blocks T022, T023 (background workers)

**Agent Components Sequential**:
- T024 (agent_service.py) blocks T025 (MCP tools)

**Integration Requires Core Complete**:
- T027 (integration) requires: T021, T023, T024, T026 complete

**Polish After Everything**:
- T028-T030 require: T027 complete

---

## Parallel Execution Examples

**Contract Tests (T004-T008) - All Parallel**:
```bash
# All contract tests can run together (different test files or test functions)
Task: "Contract test POST /tasks in tests/contract/test_orchestrator_api.py"
Task: "Contract test GET /tasks/{id} in tests/contract/test_orchestrator_api.py"
Task: "Contract test GET /agents in tests/contract/test_orchestrator_api.py"
Task: "Contract test GET /health in tests/contract/test_agent_api.py"
Task: "Contract test POST /execute in tests/contract/test_agent_api.py"
```

**Integration Tests (T009-T011) - All Parallel**:
```bash
# All integration tests are independent (different test files)
Task: "Integration test: End-to-end simple task in tests/integration/test_end_to_end.py"
Task: "Integration test: Multi-step task lifecycle in tests/integration/test_task_lifecycle.py"
Task: "Integration test: Agent coordination in tests/integration/test_agent_coordination.py"
```

**Unit Tests (T012-T015) - All Parallel**:
```bash
# All unit tests are independent (different test files)
Task: "Unit tests for Pydantic models in tests/unit/test_models.py"
Task: "Unit tests for database operations in tests/unit/test_database.py"
Task: "Unit tests for Redis operations in tests/unit/test_redis_manager.py"
Task: "Unit tests for task decomposition in tests/unit/test_task_analyzer.py"
```

**Shared Components (T016-T017) - Parallel**:
```bash
# models.py and config.py are independent
Task: "Implement shared/models.py (Pydantic models)"
Task: "Implement shared/config.py (Settings class)"
```

**Documentation (T029) - Parallel with Scripts (T028)**:
```bash
# Documentation and scripts are independent
Task: "Implement utility scripts in scripts/"
Task: "Create documentation files"
```

---

## Validation Checklist
*GATE: All items must pass before marking feature complete*

- [ ] All 30 tasks completed
- [ ] All contract tests pass (T004-T008)
- [ ] All integration tests pass (T009-T011)
- [ ] All unit tests pass (T012-T015)
- [ ] Coverage ≥80% (verified in T030)
- [ ] All services start successfully via docker-compose (T027)
- [ ] Quickstart.md scenarios work (T030)
- [ ] API endpoints match OpenAPI contracts (T004-T008)
- [ ] No linting errors (T030)
- [ ] Performance benchmarks documented (T030)

---

## Notes

- **TDD Enforcement**: Tasks T004-T015 create failing tests, tasks T016-T027 make them pass
- **Parallel Safety**: [P] tasks modify different files and have no dependencies
- **Constitution Compliance**: Max 50 lines per function, max complexity 10, 80% coverage enforced in T030
- **File Paths**: All paths are relative to repository root (D:\CodebyAI\Duy_MultiAgents_ClaudeCode\MultiAgents_ClaudeCode)
- **Docker Ports**: Orchestrator=8000, Agents=8001-8005, Streamlit=8501, PostgreSQL=5432, Redis=6379
- **Agent Capabilities Assignment** (from research.md):
  - Agent 1 (8001): DATA_ANALYSIS, CODE_GENERATION
  - Agent 2 (8002): WEB_SCRAPING, API_INTEGRATION
  - Agent 3 (8003): FILE_PROCESSING, DATABASE_OPERATIONS
  - Agent 4 (8004): CODE_GENERATION, API_INTEGRATION
  - Agent 5 (8005): DATA_ANALYSIS, DATABASE_OPERATIONS

---

**Task Generation Complete**: 30 tasks ready for execution following TDD workflow.

**Next Step**: Execute tasks sequentially (respecting dependencies) or in parallel where marked [P].

**Estimated Completion Time**: 20-30 hours (with parallel execution of test tasks and independent implementations).
