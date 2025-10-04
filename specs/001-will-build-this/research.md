# Research: Claude Token SDK Migration

**Date**: 2025-10-04
**Feature**: Migrate from Anthropic API key to Claude Code token authentication

---

## Overview

This research documents the investigation into migrating the Multi-Agent Task Execution System from Anthropic API key authentication to Claude Code integrated token authentication, based on the comprehensive guide in `CLAUDE_TOKEN_SDK_GUIDE.md`.

---

## 1. Authentication Architecture

### Decision: Hybrid Authentication Pattern

**What was chosen**: Implement a `HybridClaudeClient` class that automatically detects the runtime environment and chooses the appropriate authentication method.

**Rationale**:
1. **Flexibility**: Works seamlessly in both Claude Code environment (production) and standalone mode (development/testing)
2. **No breaking changes**: Existing API key configuration continues to work
3. **Cost optimization**: Automatically uses Claude Code tokens when available, eliminating API costs
4. **Developer experience**: Developers don't need to manually switch authentication methods

**Alternatives considered**:
- **Claude Code only**: Rejected because it would break development workflows and CI/CD pipelines that run outside Claude Code environment
- **API key only**: Rejected because it misses cost savings and integrated features of Claude Code
- **Manual switching**: Rejected because it adds complexity and error-prone configuration

---

## 2. SDK Integration Approach

### Decision: ClaudeSDKClient with AsyncAnthropic fallback

**What was chosen**: Replace direct `AsyncAnthropic()` usage with `ClaudeSDKClient` from `claude_code_sdk` when in Claude Code environment, maintaining `AsyncAnthropic` as fallback.

**Rationale**:
1. **Zero-config authentication**: In Claude Code environment, authentication is automatic via `CLAUDECODE=1`
2. **Connection reuse**: SDK handles connection pooling internally
3. **System prompt enforcement**: SDK ensures system prompts override user instructions (critical for agent behavior)
4. **Async compatibility**: SDK provides async/await interface matching existing code patterns

**Alternatives considered**:
- **Complete SDK replacement**: Rejected because it would require rewriting all Claude interaction code
- **Wrapper around AsyncAnthropic**: Rejected because it doesn't gain Claude Code integration benefits
- **Dual imports**: Rejected as too complex and error-prone

---

## 3. Environment Detection Strategy

### Decision: Environment variable + API key presence check

**What was chosen**: Use `CLAUDECODE=1` environment variable as primary indicator, with API key presence as secondary check.

**Rationale**:
1. **Explicit over implicit**: Clear environment variable makes runtime behavior predictable
2. **Easy configuration**: Single line in .env file to enable Claude Code mode
3. **CI/CD compatibility**: Easy to set in different environments
4. **Validation**: Can verify authentication setup before starting services

**Alternatives considered**:
- **Claude CLI detection**: Rejected because it requires subprocess calls and path detection
- **Automatic discovery**: Rejected because it's unreliable across platforms
- **Config file**: Rejected because environment variables are standard for 12-factor apps

---

## 4. API Key Suppression Pattern

### Decision: Temporary environment variable removal during Claude Code execution

**What was chosen**: When `CLAUDECODE=1`, temporarily remove `ANTHROPIC_API_KEY` from environment during SDK client creation, then restore it afterward.

**Rationale**:
1. **Forces integrated auth**: SDK will use Claude Code token when API key is absent
2. **Prevents accidental billing**: Ensures Claude Code environment uses free token
3. **Reversible**: Original API key restored after execution for other components
4. **Explicit intent**: Makes authentication method choice clear in code

**Alternatives considered**:
- **Permanent removal**: Rejected because other components might need API key
- **SDK configuration**: Rejected because SDK auto-detects based on environment
- **Separate clients**: Rejected as too complex for single operation

---

## 5. Configuration Management

### Decision: Extend existing Settings class with Claude Code options

**What was chosen**: Add Claude Code configuration to existing `pydantic-settings` based `Settings` class in `shared/config.py`.

**New configuration fields**:
```python
CLAUDECODE: str = Field(default="0", description="Claude Code environment flag (1=enabled)")
CLAUDE_CODE_PATH: str = Field(default="claude", description="Path to Claude CLI")
CLAUDE_MODEL: str = Field(default="claude-sonnet-4-20250514", description="Claude model to use")
CLAUDE_PERMISSION_MODE: str = Field(default="bypassPermissions", description="SDK permission mode")
```

**Rationale**:
1. **Consistency**: Maintains existing configuration pattern
2. **Validation**: Pydantic validates environment variables automatically
3. **Type safety**: Typed configuration prevents runtime errors
4. **Documentation**: Field descriptions serve as inline documentation

---

## 6. Testing Strategy

### Decision: Three-tier test pyramid with authentication-specific tests

**Test organization**:

**Unit tests** (70% of tests):
- `test_auth_detection.py`: Environment variable detection logic
- `test_hybrid_client.py`: Authentication method selection
- `test_token_fallback.py`: API key fallback behavior
- `test_config_validation.py`: Configuration validation logic

**Integration tests** (20% of tests):
- `test_task_execution_token.py`: End-to-end task execution with token auth
- `test_agent_coordination_token.py`: Multi-agent coordination with token auth
- `test_auth_switching.py`: Switching between authentication methods

**Contract tests** (10% of tests):
- `test_claude_sdk_contract.py`: Validate SDK response format matches expectations
- `test_system_prompt_enforcement.py`: Verify system prompts override user input

---

## 7. Migration Path

### Decision: Incremental migration with backward compatibility

**Migration phases**:

**Phase 1**: Infrastructure (no behavior change)
- Add `claude-code-sdk` to requirements.txt
- Add `CLAUDECODE` environment variable to config
- Update `.env.example` with new variables

**Phase 2**: Hybrid client implementation
- Create `HybridClaudeClient` class
- Implement authentication detection
- Implement both authentication paths

**Phase 3**: Integration
- Update `orchestrator/task_analyzer.py` to use hybrid client
- Update `agent/agent_service.py` to use hybrid client

**Phase 4**: Validation
- Run full test suite with `CLAUDECODE=0` (API key mode)
- Run full test suite with `CLAUDECODE=1` (token mode)
- Performance benchmarks to verify no regressions

**Phase 5**: Production deployment
- Set `CLAUDECODE=1` in production environment
- Monitor for authentication errors
- Validate cost reduction (no API charges)

---

## 8. Error Handling and Resilience

### Decision: Comprehensive error handling with retry logic and actionable messages

**Error categories**:
- **Control request timeout**: Claude CLI not installed or not in PATH
- **Credit balance too low**: Fallback to API key or prompt for Claude Code setup
- **Authentication failure**: Check token validity and environment setup
- **Rate limiting**: Implement backoff and retry

**Implementation requirements**:
- Authentication validation before execution
- Timeout handling for SDK initialization
- Retry logic for transient failures
- User-friendly error messages with remediation steps

---

## 9. Performance Considerations

### Decision: Connection reuse and response streaming

**Performance optimizations**:
- Connection reuse pattern (`OptimizedClaudeClient` with context manager)
- Batch processing with rate limiting
- Response streaming for large outputs

**Performance targets**:
- SDK initialization: <2s (cached after first request)
- Query response: <200ms p95 (same as current API)
- Memory overhead: <50MB (SDK connection pool)
- Concurrent requests: 5 agents × 1 request each = 5 concurrent

---

## Research Summary

All technical unknowns have been resolved. The migration path is clear:

1. ✅ **Authentication architecture**: Hybrid pattern with automatic detection
2. ✅ **SDK integration**: ClaudeSDKClient with AsyncAnthropic fallback
3. ✅ **Environment detection**: CLAUDECODE environment variable
4. ✅ **API key handling**: Temporary suppression pattern
5. ✅ **Configuration**: Extended Settings class
6. ✅ **Testing**: Three-tier pyramid with specific auth tests
7. ✅ **Migration**: Incremental with backward compatibility
8. ✅ **Error handling**: Comprehensive with retry logic
9. ✅ **Performance**: Connection reuse and streaming

**No NEEDS CLARIFICATION remain**. Ready for Phase 1 (Design & Contracts).

---

**References**:
- `CLAUDE_TOKEN_SDK_GUIDE.md`: Comprehensive guide covering all authentication methods
- Existing codebase: `orchestrator/task_analyzer.py`, `agent/agent_service.py`
- Constitution: Testing Standards (TDD), Code Quality (maintainability)
