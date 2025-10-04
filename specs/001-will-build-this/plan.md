
# Implementation Plan: Claude Token SDK Migration

**Branch**: `001-will-build-this` | **Date**: 2025-10-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `D:\CodebyAI\Duy_MultiAgents_ClaudeCode\MultiAgents_ClaudeCode\specs\001-will-build-this\spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec from Input path
   → If not found: ERROR "No feature spec at {path}"
2. Fill Technical Context (scan for NEEDS CLARIFICATION)
   → Detect Project Type from file system structure or context (web=frontend+backend, mobile=app+api)
   → Set Structure Decision based on project type
3. Fill the Constitution Check section based on the content of the constitution document.
4. Evaluate Constitution Check section below
   → If violations exist: Document in Complexity Tracking
   → If no justification possible: ERROR "Simplify approach first"
   → Update Progress Tracking: Initial Constitution Check
5. Execute Phase 0 → research.md
   → If NEEDS CLARIFICATION remain: ERROR "Resolve unknowns"
6. Execute Phase 1 → contracts, data-model.md, quickstart.md, agent-specific template file (e.g., `CLAUDE.md` for Claude Code, `.github/copilot-instructions.md` for GitHub Copilot, `GEMINI.md` for Gemini CLI, `QWEN.md` for Qwen Code, or `AGENTS.md` for all other agents).
7. Re-evaluate Constitution Check section
   → If new violations: Refactor design, return to Phase 1
   → Update Progress Tracking: Post-Design Constitution Check
8. Plan Phase 2 → Describe task generation approach (DO NOT create tasks.md)
9. STOP - Ready for /tasks command
```

**IMPORTANT**: The /plan command STOPS at step 7. Phases 2-4 are executed by other commands:
- Phase 2: /tasks command creates tasks.md
- Phase 3-4: Implementation execution (manual or via tools)

## Summary

**Primary Requirement**: Migrate the Multi-Agent Task Execution System from Anthropic API key authentication to Claude Code integrated authentication using claude.ai tokens.

**Technical Approach**: Replace direct `anthropic.Anthropic()` client usage with `ClaudeSDKClient` from `claude_code_sdk`. Implement hybrid authentication that detects Claude Code environment (`CLAUDECODE=1`) and automatically uses integrated authentication, while maintaining fallback to API key for development scenarios. This migration will eliminate API credit costs, provide seamless integration with Claude Code features, and ensure automatic token management.

## Technical Context
**Language/Version**: Python 3.11+
**Primary Dependencies**:
- `claude-code-sdk` (Claude Code SDK for integrated authentication)
- `anthropic` (fallback for direct API)
- `asyncpg` (PostgreSQL async driver)
- `redis` (queue and coordination)
- `FastAPI` (orchestrator and agent services)
- `streamlit` (UI)
- `pydantic` (data validation)
- `pydantic-settings` (environment configuration)

**Storage**: PostgreSQL (tasks, results, logs) + Redis (queues, agent status)
**Testing**: pytest with pytest-asyncio for async code
**Target Platform**: Windows/Linux servers (multi-process architecture)
**Project Type**: Distributed system (orchestrator + 5 agents + UI)
**Performance Goals**: Same as original (agent task execution <30s, API <200ms p95)
**Constraints**:
- Must maintain backward compatibility with existing database schema
- Must work in both Claude Code environment and standalone mode
- Must not require manual token management
- Must eliminate API credit costs when running in Claude Code

**Scale/Scope**:
- 1 orchestrator service
- 5 agent services (requires updating 2 files each)
- 2 shared components (task_analyzer.py in orchestrator, agent_service.py in agent)
- Total: ~10 code files to modify

## Constitution Check
*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Code Quality (NON-NEGOTIABLE)
- ✅ **PASS**: Migration maintains existing naming conventions and module structure
- ✅ **PASS**: Changes isolated to authentication layer (task_analyzer.py, agent_service.py)
- ✅ **PASS**: Single-purpose wrapper classes for authentication (HybridClaudeClient pattern)
- ✅ **PASS**: No magic numbers (environment variables used for configuration)

### Testing Standards (NON-NEGOTIABLE)
- ✅ **PASS**: TDD workflow will be followed (write authentication tests first)
- ✅ **PASS**: Target 80%+ coverage for modified authentication modules
- ✅ **PASS**: Test pyramid: Unit tests (authentication methods), Integration tests (end-to-end task execution), Contract tests (Claude SDK responses)
- ✅ **PASS**: Tests will cover: Claude Code environment detection, API key fallback, token validation, error handling

### User Experience Consistency
- ✅ **PASS**: No changes to CLI/UI interfaces (internal authentication only)
- ✅ **PASS**: Error messages will include actionable guidance (e.g., "Set CLAUDECODE=1 or provide ANTHROPIC_API_KEY")
- ✅ **PASS**: Existing environment variable handling preserved
- ✅ **PASS**: No breaking changes to .env configuration

### Performance Requirements
- ✅ **PASS**: Response times unchanged (same Claude models used)
- ✅ **PASS**: Connection reuse pattern from guide eliminates overhead
- ✅ **PASS**: No memory impact (SDK handles connection pooling)
- ✅ **PASS**: Performance tests will verify no regressions

**Gate Result**: ✅ **ALL GATES PASS** - No constitutional violations detected. Proceed to Phase 0.

## Project Structure

### Documentation (this feature)
```
specs/[###-feature]/
├── plan.md              # This file (/plan command output)
├── research.md          # Phase 0 output (/plan command)
├── data-model.md        # Phase 1 output (/plan command)
├── quickstart.md        # Phase 1 output (/plan command)
├── contracts/           # Phase 1 output (/plan command)
└── tasks.md             # Phase 2 output (/tasks command - NOT created by /plan)
```

### Source Code (repository root)
```
orchestrator/
├── task_analyzer.py        # [MODIFY] Replace AsyncAnthropic with HybridClaudeClient
└── orchestrator.py          # [NO CHANGE] Uses task_analyzer

agent/
├── agent_service.py         # [MODIFY] Replace AsyncAnthropic with HybridClaudeClient
└── __init__.py              # [NO CHANGE]

shared/
├── models.py                # [NO CHANGE] Data models
├── config.py                # [MODIFY] Add CLAUDECODE env var
├── database.py              # [NO CHANGE] Database manager
└── redis_manager.py         # [NO CHANGE] Redis operations

ui/
└── streamlit_app.py         # [NO CHANGE] UI layer

tests/
├── unit/
│   ├── test_auth_detection.py          # [NEW] Test environment detection
│   ├── test_hybrid_client.py           # [NEW] Test authentication methods
│   └── test_token_fallback.py          # [NEW] Test API key fallback
├── integration/
│   ├── test_task_execution_token.py    # [NEW] End-to-end with token auth
│   └── test_agent_coordination_token.py # [NEW] Multi-agent with token auth
└── contract/
    └── test_claude_sdk_contract.py     # [NEW] Validate SDK response format

.env                         # [MODIFY] Add CLAUDECODE=1
requirements.txt             # [MODIFY] Add claude-code-sdk
```

**Structure Decision**: Distributed system with single project layout. Existing module structure preserved. Authentication changes isolated to 2 core files (task_analyzer.py, agent_service.py) with new shared authentication utility. Tests organized by type following TDD pyramid.

## Phase 0: Outline & Research ✅ COMPLETE

**Research completed**: All technical decisions documented in `research.md`

**Key decisions made**:
1. **Authentication Architecture**: Hybrid pattern with automatic Claude Code detection
2. **SDK Integration**: ClaudeSDKClient with AsyncAnthropic fallback
3. **Environment Detection**: CLAUDECODE=1 environment variable
4. **API Key Handling**: Temporary suppression during Claude Code execution
5. **Configuration**: Extended Settings class with new Claude Code fields
6. **Testing**: Three-tier pyramid (unit/integration/contract) with auth-specific tests
7. **Migration Path**: 5-phase incremental migration with backward compatibility
8. **Error Handling**: Comprehensive with retry logic and actionable messages
9. **Performance**: Connection reuse and response streaming patterns

**Output**: ✅ research.md created with 9 research sections, all NEEDS CLARIFICATION resolved

## Phase 1: Design & Contracts
*Prerequisites: research.md complete*

1. **Extract entities from feature spec** → `data-model.md`:
   - Entity name, fields, relationships
   - Validation rules from requirements
   - State transitions if applicable

2. **Generate API contracts** from functional requirements:
   - For each user action → endpoint
   - Use standard REST/GraphQL patterns
   - Output OpenAPI/GraphQL schema to `/contracts/`

3. **Generate contract tests** from contracts:
   - One test file per endpoint
   - Assert request/response schemas
   - Tests must fail (no implementation yet)

4. **Extract test scenarios** from user stories:
   - Each story → integration test scenario
   - Quickstart test = story validation steps

5. **Update agent file incrementally** (O(1) operation):
   - Run `.specify/scripts/powershell/update-agent-context.ps1 -AgentType claude`
     **IMPORTANT**: Execute it exactly as specified above. Do not add or remove any arguments.
   - If exists: Add only NEW tech from current plan
   - Preserve manual additions between markers
   - Update recent changes (keep last 3)
   - Keep under 150 lines for token efficiency
   - Output to repository root

**Output**: data-model.md, /contracts/*, failing tests, quickstart.md, agent-specific file

## Phase 2: Task Planning Approach
*This section describes what the /tasks command will do - DO NOT execute during /plan*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design docs (contracts, data model, quickstart)
- Each contract → contract test task [P]
- Each entity → model creation task [P] 
- Each user story → integration test task
- Implementation tasks to make tests pass

**Ordering Strategy**:
- TDD order: Tests before implementation 
- Dependency order: Models before services before UI
- Mark [P] for parallel execution (independent files)

**Estimated Output**: 25-30 numbered, ordered tasks in tasks.md

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan

## Phase 3+: Future Implementation
*These phases are beyond the scope of the /plan command*

**Phase 3**: Task execution (/tasks command creates tasks.md)  
**Phase 4**: Implementation (execute tasks.md following constitutional principles)  
**Phase 5**: Validation (run tests, execute quickstart.md, performance validation)

## Complexity Tracking
*Fill ONLY if Constitution Check has violations that must be justified*

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |


## Progress Tracking
*This checklist is updated during execution flow*

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [ ] Phase 2: Task planning complete (/plan command - describe approach only)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none required)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*
