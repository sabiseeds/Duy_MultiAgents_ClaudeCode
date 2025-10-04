# Implementation Plan: Multi-Agent Task Execution System

**Branch**: `001-will-build-this` | **Date**: 2025-10-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `D:\CodebyAI\Duy_MultiAgents_ClaudeCode\MultiAgents_ClaudeCode\specs\001-will-build-this\spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path → ✓ LOADED
2. Fill Technical Context (scan for NEEDS CLARIFICATION) → ✓ COMPLETE
   → Detected Project Type: web (orchestrator + agents + UI)
   → Structure Decision: Multi-service architecture
3. Fill Constitution Check section → ✓ COMPLETE
4. Evaluate Constitution Check section
   → No violations detected
   → Update Progress Tracking: Initial Constitution Check → PASS
5. Execute Phase 0 → research.md → IN PROGRESS
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, CLAUDE.md
7. Re-evaluate Constitution Check section
8. Plan Phase 2 → Describe task generation approach
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 9. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary

Build a distributed multi-agent task execution system where users submit complex tasks via a web interface, which are automatically decomposed into subtasks and executed in parallel by 5 specialized Claude agents (powered by the official Claude Agent SDK). The system coordinates execution through a central orchestrator using shared resources (PostgreSQL for persistence, Redis for queuing, shared file storage), provides real-time monitoring via Streamlit dashboard, and aggregates results when all subtasks complete.

**Technical Approach**: Microservices architecture with FastAPI orchestrator, 5 independent agent services using Claude Agent SDK with MCP servers for tool integration, PostgreSQL for task/result storage, Redis for message queuing and agent coordination, Streamlit for user interface, and containerized deployment via Docker Compose.

## Technical Context
**Language/Version**: Python 3.11+
**Primary Dependencies**: FastAPI 0.104+, Claude Agent SDK 1.0+, Streamlit 1.28+, asyncpg, redis[asyncio], anthropic 0.7.7, httpx, psutil
**Storage**: PostgreSQL 15 (tasks, subtask_results, agent_logs tables)
**Testing**: pytest with pytest-asyncio for async tests, httpx for API testing, contract tests via OpenAPI validation
**Target Platform**: Docker containers on Linux (orchestrator, 5 agents, Streamlit UI, PostgreSQL, Redis)
**Project Type**: web (multi-service)
**Performance Goals**: <200ms API latency p95, parallel subtask execution, <1s task submission response, real-time UI updates every 2s
**Constraints**: <200ms orchestrator endpoints, <2GB memory per agent, 80% test coverage, TDD workflow, agent heartbeat every 10s
**Scale/Scope**: 5 concurrent agents, support 10+ parallel tasks, handle 100+ subtasks per task, 10k+ tasks in database

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Code Quality (NON-NEGOTIABLE)
- ✅ **PASS**: Code will follow camelCase for variables/functions, PascalCase for classes
- ✅ **PASS**: Functions will be single-purpose with descriptive names
- ✅ **PASS**: Max 50 lines per function (excluding tests)
- ✅ **PASS**: Max cyclomatic complexity 10
- ✅ **PASS**: No dead code, no magic numbers, DRY principle enforced

### Testing Standards (NON-NEGOTIABLE)
- ✅ **PASS**: TDD workflow: Tests → User approval → Fail → Implement → Pass → Refactor
- ✅ **PASS**: 80% minimum coverage for all new code
- ✅ **PASS**: Test pyramid: 70% unit, 20% integration, 10% contract
- ✅ **PASS**: Each test verifies one behavior, deterministic execution
- ✅ **PASS**: Tests run <5s (unit), <30s (integration)
- ✅ **PASS**: Coverage: happy path, errors, boundaries, edges, performance

### UX Consistency
- ✅ **PASS**: Streamlit UI provides intuitive web interface
- ✅ **PASS**: Clear error messages with actionable guidance
- ✅ **PASS**: Progress indicators for long operations (>2s)
- ✅ **PASS**: Real-time feedback on task status
- ✅ **PASS**: Quickstart guide enables success within 5 minutes

### Performance Requirements
- ✅ **PASS**: API endpoints <200ms p95 latency (orchestrator POST /tasks, GET /tasks/{id})
- ✅ **PASS**: UI updates <100ms feedback
- ✅ **PASS**: Memory <500MB baseline, <2GB peak per service
- ✅ **PASS**: Handle 10x expected load (50 concurrent tasks)
- ✅ **PASS**: Connection pooling (PostgreSQL pool size 2-20, Redis connection reuse)
- ✅ **PASS**: Benchmark tests for task submission, agent assignment, result aggregation

### Quality Gates
- ✅ **PASS**: All tests passing before merge
- ✅ **PASS**: 80% coverage enforced
- ✅ **PASS**: Linting (flake8/black), type checking (mypy optional)
- ✅ **PASS**: Code review with constitutional compliance check
- ✅ **PASS**: Performance benchmarks documented

**Initial Assessment**: No constitutional violations. System design aligns with all principles.

## Project Structure

### Documentation (this feature)
```
specs/001-will-build-this/
├── spec.md              # Feature specification
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
│   ├── orchestrator-api.yaml  # OpenAPI spec for orchestrator
│   ├── agent-api.yaml         # OpenAPI spec for agent endpoints
│   └── task-schema.json       # JSON schema for Task/SubTask models
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
shared/                          # Shared components across services
├── __init__.py
├── models.py                    # Pydantic models (Task, SubTask, Agent, etc.)
├── config.py                    # Settings and configuration
├── database.py                  # PostgreSQL manager
└── redis_manager.py             # Redis operations

orchestrator/                    # Central orchestrator service
├── __init__.py
├── orchestrator.py              # FastAPI app, background workers
└── task_analyzer.py             # Task decomposition using Claude API

agent/                           # Agent service (5 instances)
├── __init__.py
└── agent_service.py             # FastAPI app with Claude Agent SDK

ui/                              # User interface
└── streamlit_app.py             # Streamlit dashboard

shared_files/                    # Shared workspace for agents
└── {task_id}/                   # Per-task directories
    ├── context/                 # Context files
    ├── output/                  # Agent outputs
    └── temp/                    # Temporary files

tests/
├── contract/                    # Contract tests (10% of tests)
│   ├── test_orchestrator_api.py
│   ├── test_agent_api.py
│   └── test_task_schemas.py
├── integration/                 # Integration tests (20% of tests)
│   ├── test_end_to_end.py
│   ├── test_task_lifecycle.py
│   └── test_agent_coordination.py
└── unit/                        # Unit tests (70% of tests)
    ├── test_models.py
    ├── test_database.py
    ├── test_redis_manager.py
    ├── test_task_analyzer.py
    └── test_agent_service.py

scripts/                         # Utility scripts
├── start.sh                     # Start all services
├── stop.sh                      # Stop all services
└── test_system.py               # System tests

docker-compose.yml               # Docker Compose configuration
Dockerfile.orchestrator          # Orchestrator image
Dockerfile.agent                 # Agent image
Dockerfile.streamlit             # Streamlit UI image
requirements.txt                 # Python dependencies
.env.example                     # Environment template
.env                            # Environment variables (gitignored)
.gitignore
README.md
```

**Structure Decision**: Web application architecture with multiple services (orchestrator, 5 agents, UI) coordinating via shared resources. Each service is independently deployable as a Docker container. Shared code in `shared/` directory, service-specific code in dedicated directories, comprehensive test coverage in `tests/` with contract/integration/unit split per testing pyramid.

## Phase 0: Outline & Research

**No NEEDS CLARIFICATION items detected** - specification files provide comprehensive technical details.

### Research Topics

1. **Claude Agent SDK Integration**
   - Decision: Use official Claude Agent SDK for agent implementation
   - Rationale: Provides native tool integration, MCP servers, file operations, subagent delegation, checkpoints
   - Key features: ClaudeSDKClient, ClaudeAgentOptions, MCP server creation, permission modes

2. **Task Decomposition Strategy**
   - Decision: Use Claude API (Anthropic client) for analyzing and decomposing tasks
   - Rationale: Leverages Claude's reasoning to break complex tasks into subtasks with dependencies
   - Approach: Prompt engineering to extract subtask descriptions, capabilities, dependencies, priorities

3. **Message Queue Architecture**
   - Decision: Redis with LIST data structure (BLPOP/RPUSH) for task and result queues
   - Rationale: Atomic operations, blocking dequeue, simple pub/sub, supports distributed coordination
   - Queues: `agent_tasks` (pending subtasks), `agent_results` (completed subtask results)

4. **Agent Capability Matching**
   - Decision: Enum-based capabilities (DATA_ANALYSIS, WEB_SCRAPING, CODE_GENERATION, FILE_PROCESSING, DATABASE_OPERATIONS, API_INTEGRATION)
   - Rationale: Static assignment enables predictable routing, agents register capabilities in Redis
   - Matching: Dispatcher finds first available agent with required capability

5. **Shared State Management**
   - Decision: Combination of PostgreSQL (persistent state), Redis (ephemeral state), file storage (large data)
   - Rationale: PostgreSQL for audit trail and historical data, Redis for real-time coordination, files for outputs
   - Patterns: Task status in DB, agent availability in Redis, subtask results in both

6. **Error Handling and Retry**
   - Decision: Mark failures in database, block dependent subtasks, support manual retry
   - Rationale: Explicit failure tracking prevents cascading errors, preserves audit trail
   - No auto-retry: Requires user intervention to prevent infinite loops

7. **Performance Optimization**
   - Decision: PostgreSQL connection pooling (2-20 connections), Redis connection reuse, async/await throughout
   - Rationale: Minimize connection overhead, maximize concurrency with asyncio
   - Indexes: task status, user_id, created_at, subtask_id for fast queries

8. **Monitoring and Observability**
   - Decision: PostgreSQL agent_logs table, Streamlit real-time polling, agent heartbeat via Redis
   - Rationale: Centralized logging, simple UI refresh, TTL-based agent health detection
   - Metrics: CPU/memory via psutil, execution time per subtask, queue lengths

**Output**: research.md created

---

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

### Entity Extraction → data-model.md

**Entities Identified** (from feature spec):
1. Task - User-submitted work request
2. SubTask - Individual unit of work
3. Agent - Independent execution unit
4. SubTaskResult - Output from subtask execution
5. AgentCapability - Agent specialization enum
6. TaskQueue - Ordered collection of pending subtasks
7. SharedState - Key-value storage for coordination

**Data Model Created**:
- Entity definitions with fields, validation rules, state transitions
- Relationship diagrams (Task 1:N SubTask, SubTask N:N SubTask dependencies)
- PostgreSQL schema with indexes
- Redis data structures
- Pydantic model code references

**Output**: `data-model.md` created

---

### API Contracts → contracts/

**Orchestrator API Endpoints**:
- POST /tasks - Create and submit task
- GET /tasks/{task_id} - Get task status and results
- GET /agents - Get all registered agents
- GET /agents/available - Get available agents by capability

**Agent API Endpoints**:
- GET /health - Health check
- GET /status - Detailed agent status
- POST /execute - Execute subtask

**Outputs**:
- `contracts/orchestrator-api.yaml` - OpenAPI 3.0 spec
- `contracts/agent-api.yaml` - OpenAPI 3.0 spec

---

### Test Scenarios → quickstart.md

**Quickstart Guide Created**:
1. **Step 1**: Clone and setup environment (1 min)
2. **Step 2**: Start all services via Docker Compose (2 min)
3. **Step 3**: Submit simple task via UI or API (30 sec)
4. **Step 4**: Monitor execution in real-time (1 min)
5. **Step 5**: Try complex multi-step task (1 min)

**Validation Scenarios**:
- All 5 agents registered and available
- Simple task completes successfully
- Complex task decomposes into multiple subtasks
- Results aggregated correctly
- UI shows real-time updates

**Time to first success**: < 5 minutes ✓

**Output**: `quickstart.md` created

---

### Agent Context Update → CLAUDE.md

**Script Executed**: `.specify/scripts/powershell/update-agent-context.ps1 -AgentType claude`

**Context Added**:
- Language: Python 3.11+
- Framework: FastAPI 0.104+, Claude Agent SDK 1.0+, Streamlit 1.28+
- Database: PostgreSQL 15
- Project Type: web (multi-service)

**Output**: `CLAUDE.md` updated at repository root

---

## Phase 1 Completion: Re-evaluate Constitution Check

### Code Quality (NON-NEGOTIABLE)
- ✅ **PASS**: Design maintains single-purpose components (orchestrator, agent, UI)
- ✅ **PASS**: Clear naming in data model and API contracts
- ✅ **PASS**: Function complexity manageable (background workers, API handlers)

### Testing Standards (NON-NEGOTIABLE)
- ✅ **PASS**: Contract tests defined in quickstart (validate API schemas)
- ✅ **PASS**: Integration tests planned (end-to-end task lifecycle)
- ✅ **PASS**: Unit tests scoped to shared modules (models, database, redis)
- ✅ **PASS**: Test pyramid maintained (70% unit, 20% integration, 10% contract)

### UX Consistency
- ✅ **PASS**: Streamlit UI provides intuitive interface
- ✅ **PASS**: API error responses include actionable detail
- ✅ **PASS**: Quickstart guide enables 5-minute success
- ✅ **PASS**: Real-time feedback via polling (every 2s)

### Performance Requirements
- ✅ **PASS**: PostgreSQL indexes on all query patterns
- ✅ **PASS**: Connection pooling configured (2-20 connections)
- ✅ **PASS**: Async/await throughout for concurrency
- ✅ **PASS**: Redis TTL for agent heartbeat (60s expiration)
- ✅ **PASS**: File-based storage for large results (no DB bloat)

**Post-Design Assessment**: No new constitutional violations. Design passes all quality gates.

---

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:

1. **Load Base Template**:
   - Read `.specify/templates/tasks-template.md`
   - Extract task structure and numbering scheme

2. **Generate from Contracts** (10% - Contract Tests):
   - `contracts/orchestrator-api.yaml` → 3 contract test tasks
     - T001 [P] Contract test POST /tasks
     - T002 [P] Contract test GET /tasks/{id}
     - T003 [P] Contract test GET /agents
   - `contracts/agent-api.yaml` → 2 contract test tasks
     - T004 [P] Contract test GET /health
     - T005 [P] Contract test POST /execute

3. **Generate from Data Model** (20% - Integration Tests):
   - Task lifecycle → 1 integration test
     - T006 Integration test: Create task → Decompose → Execute → Aggregate
   - Agent coordination → 1 integration test
     - T007 Integration test: Multiple agents executing parallel subtasks
   - Error handling → 1 integration test
     - T008 Integration test: Failed subtask blocks dependents

4. **Generate from Entities** (30% - Unit Tests & Models):
   - Task, SubTask, Agent, SubTaskResult models → 1 unit test task
     - T009 [P] Unit tests for Pydantic models (validation, serialization)
   - DatabaseManager → 1 unit test task
     - T010 [P] Unit tests for database operations (CRUD, queries)
   - RedisManager → 1 unit test task
     - T011 [P] Unit tests for Redis operations (queues, hashes, locks)
   - TaskAnalyzer → 1 unit test task
     - T012 [P] Unit tests for task decomposition logic

5. **Generate Implementation Tasks** (40% - Core Features):
   - **Setup Phase** (3 tasks):
     - T013 Create project structure (directories, __init__.py files)
     - T014 Create requirements.txt with all dependencies
     - T015 [P] Create docker-compose.yml and Dockerfiles

   - **Shared Components** (3 tasks):
     - T016 Implement shared/models.py (Pydantic models)
     - T017 Implement shared/config.py (Settings class)
     - T018 Implement shared/database.py (DatabaseManager with pool)
     - T019 Implement shared/redis_manager.py (RedisManager with queues)

   - **Orchestrator Service** (4 tasks):
     - T020 Implement orchestrator/task_analyzer.py (Claude API decomposition)
     - T021 Implement orchestrator/orchestrator.py (FastAPI app)
     - T022 Implement background worker: dispatch_tasks()
     - T023 Implement background worker: process_results()

   - **Agent Service** (2 tasks):
     - T024 Implement agent/agent_service.py (Claude SDK integration)
     - T025 Implement MCP server tools (database, embedding, shared state)

   - **Streamlit UI** (1 task):
     - T026 Implement ui/streamlit_app.py (dashboard, task submission, monitoring)

   - **Utility Scripts** (1 task):
     - T027 [P] Implement scripts/start.sh, stop.sh, test_system.py

**Ordering Strategy**:

1. **TDD Order**: Tests before implementation
   - Contract tests (T001-T005) MUST be written first
   - Integration tests (T006-T008) MUST fail initially
   - Unit tests (T009-T012) MUST be written before each component
   - Implementation tasks only after corresponding tests exist

2. **Dependency Order**:
   - Setup (T013-T015) blocks everything else
   - Shared components (T016-T019) block orchestrator and agents
   - Models (T016) blocks database (T018) and all services
   - Orchestrator (T020-T023) and Agents (T024-T025) can be parallel
   - UI (T026) requires orchestrator running

3. **Parallelization** ([P] marker):
   - Contract tests are independent ([P] on all)
   - Unit tests for different modules are independent ([P])
   - Docker files can be written in parallel ([P])
   - Scripts can be written in parallel ([P])

**Estimated Output**: 27 numbered tasks in `tasks.md`

**Task Format**:
```
- [ ] T001 [P] Contract test POST /tasks in tests/contract/test_orchestrator_api.py
      Validate request schema, response codes, response body structure
```

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

---

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)
**Phase 4**: Implementation (execute tasks following TDD workflow)
**Phase 5**: Validation (run full test suite, execute quickstart.md, performance benchmarks)

---

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

No violations detected. This section is empty.

---

## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved (none existed)
- [x] Complexity deviations documented (none required)

**Artifacts Generated**:
- [x] specs/001-will-build-this/plan.md (this file)
- [x] specs/001-will-build-this/research.md
- [x] specs/001-will-build-this/data-model.md
- [x] specs/001-will-build-this/quickstart.md
- [x] specs/001-will-build-this/contracts/orchestrator-api.yaml
- [x] specs/001-will-build-this/contracts/agent-api.yaml
- [x] CLAUDE.md (repository root)

---

## Summary

**Planning Complete**: All design artifacts generated, no constitutional violations, ready for task generation via `/tasks` command.

**Next Step**: Run `/tasks` to generate the ordered, testable task list in `tasks.md`.

---

*Based on Constitution v1.0.0 - See `.specify/memory/constitution.md`*
