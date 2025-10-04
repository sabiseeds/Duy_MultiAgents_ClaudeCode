<!--
Sync Impact Report:
Version change: [Not versioned] → 1.0.0
Modified principles: N/A (initial constitution)
Added sections:
  - Core Principles (4 principles: Code Quality, Testing Standards, UX Consistency, Performance Requirements)
  - Quality Gates
  - Development Workflow
  - Governance
Templates requiring updates:
  ✅ plan-template.md - Constitution Check section references verified
  ✅ spec-template.md - Requirement alignment verified
  ✅ tasks-template.md - Task categorization aligns with principles
Follow-up TODOs: None
-->

# MultiAgents_ClaudeCode Constitution

## Core Principles

### I. Code Quality (NON-NEGOTIABLE)

**Code MUST be maintainable, readable, and follow established patterns.**

- All code MUST follow consistent naming conventions (camelCase for variables/functions, PascalCase for classes)
- Functions MUST be single-purpose with clear, descriptive names
- Maximum function length: 50 lines (excluding tests)
- Maximum cyclomatic complexity: 10 per function
- Dead code MUST be removed before commit
- Magic numbers MUST be replaced with named constants
- Code duplication MUST be refactored (DRY principle)

**Rationale**: Maintainable code reduces technical debt, accelerates onboarding, and minimizes defects. Complexity limits ensure code remains understandable and testable.

### II. Testing Standards (NON-NEGOTIABLE)

**Test-Driven Development (TDD) is mandatory; all features MUST have comprehensive test coverage.**

- **TDD Workflow**: Tests written → User approved → Tests fail → Implementation → Tests pass → Refactor
- **Minimum Coverage**: 80% code coverage for all new code
- **Test Pyramid**:
  - Unit tests: Fast, isolated, cover edge cases (70% of tests)
  - Integration tests: Verify component interactions (20% of tests)
  - Contract tests: Validate API contracts (10% of tests)
- **Test Quality**:
  - Each test MUST verify one behavior
  - Tests MUST be deterministic (no flakiness)
  - Test names MUST describe expected behavior
  - Tests MUST run in <5 seconds (unit), <30 seconds (integration)
- **Non-negotiable test scenarios**:
  - Happy path
  - Error conditions
  - Boundary cases
  - Edge cases
  - Performance regression tests

**Rationale**: TDD ensures features meet requirements, prevents regressions, enables fearless refactoring, and serves as living documentation.

### III. User Experience Consistency

**All user-facing interfaces MUST provide consistent, intuitive experiences.**

- **CLI Interfaces**:
  - Follow standard conventions (--help, --version flags)
  - Provide clear error messages with actionable guidance
  - Support both interactive and non-interactive modes
  - Input via stdin/args, output to stdout, errors to stderr
  - Support both JSON and human-readable output formats
- **Error Handling**:
  - Error messages MUST explain what went wrong and how to fix it
  - Exit codes MUST follow POSIX conventions (0=success, 1-255=error types)
  - Validation errors MUST specify which field and why it failed
- **Documentation**:
  - Every user-facing feature MUST have usage examples
  - Quickstart guides MUST enable first success within 5 minutes
  - API documentation MUST be generated from code (not manually written)
- **Feedback**:
  - Long operations (>2s) MUST show progress indicators
  - Destructive actions MUST require confirmation
  - Success feedback MUST confirm what changed

**Rationale**: Consistent UX reduces learning curve, minimizes user errors, and builds trust through predictable behavior.

### IV. Performance Requirements

**All features MUST meet defined performance targets and scale gracefully.**

- **Response Time Requirements**:
  - API endpoints: <200ms p95 latency
  - CLI commands: <1s for standard operations
  - UI interactions: <100ms feedback, <16ms for animations (60fps)
- **Resource Constraints**:
  - Memory: <500MB baseline, <2GB peak for standard workloads
  - CPU: <20% idle, <80% under load
  - Storage: Efficient data structures, indexed queries
- **Scalability**:
  - Features MUST handle 10x expected load
  - Graceful degradation under resource pressure
  - Connection pooling for external services
  - Caching for expensive operations (with TTL)
- **Performance Testing**:
  - Benchmark tests for critical paths
  - Load tests before production deployment
  - Performance budgets enforced in CI/CD
  - No performance regressions allowed

**Rationale**: Performance impacts user satisfaction directly. Proactive performance management prevents technical debt and costly rewrites.

## Quality Gates

**All code changes MUST pass these gates before merge:**

1. **Automated Checks**:
   - All tests passing (unit, integration, contract)
   - Code coverage ≥ 80% for changed files
   - Linting rules passing (no warnings)
   - Type checking passing (if applicable)
   - No security vulnerabilities (SAST scan)

2. **Code Review Requirements**:
   - At least one approval from code owner
   - All review comments resolved
   - Constitution compliance verified
   - Architecture patterns followed

3. **Performance Gates**:
   - Benchmark tests pass
   - No regressions in response times
   - Memory usage within budgets
   - Load test results documented

4. **Documentation Gates**:
   - API changes reflected in docs
   - Breaking changes documented in CHANGELOG
   - Quickstart guide updated if applicable

**Violation Handling**: If constitutional principles cannot be met, justification MUST be documented in Complexity Tracking section of plan.md, with explicit approval required.

## Development Workflow

**Standard process for feature development:**

1. **Feature Specification** (`/specify`):
   - Document user scenarios and requirements
   - Mark all ambiguities with [NEEDS CLARIFICATION]
   - Define acceptance criteria (testable)

2. **Implementation Planning** (`/plan`):
   - Pass Constitution Check (gates enforcement)
   - Research unknowns (Phase 0)
   - Design contracts and data models (Phase 1)
   - Document complexity deviations if any

3. **Task Generation** (`/tasks`):
   - Generate ordered, dependency-aware tasks
   - Enforce TDD: tests before implementation
   - Mark parallel-safe tasks with [P]

4. **Implementation** (`/implement` or manual):
   - Execute tasks in order
   - Commit after each task completion
   - Run tests continuously
   - Update documentation inline

5. **Validation**:
   - Run full test suite
   - Execute quickstart.md scenarios
   - Validate performance benchmarks
   - Review against acceptance criteria

**Branch Strategy**:
- Feature branches: `###-feature-name`
- Pull requests required for all changes
- CI/CD runs all quality gates
- Merge only when all gates pass

## Governance

**This Constitution supersedes all other development practices and guidelines.**

### Amendment Process
- Constitution changes require documentation of rationale
- Version increments follow semantic versioning:
  - **MAJOR**: Breaking changes to governance (backward incompatible)
  - **MINOR**: New principles or expanded guidance
  - **PATCH**: Clarifications, wording fixes, non-semantic refinements
- All amendments MUST update dependent templates (plan, spec, tasks)
- Amendment approval requires project owner sign-off

### Compliance
- All pull requests MUST verify constitutional compliance
- Automated checks enforce quantitative rules (coverage, performance, complexity)
- Code reviews enforce qualitative principles (clarity, patterns)
- Complexity deviations require explicit justification and approval

### Versioning & History
- Constitution changes tracked in git history
- Sync Impact Report prepended as HTML comment on updates
- Templates reference constitution version for traceability

### Enforcement
- CI/CD pipelines enforce automated gates
- Code review checklist includes constitutional compliance
- Performance budgets enforced via benchmark tests
- Documentation completeness verified before merge

**Version**: 1.0.0 | **Ratified**: 2025-10-04 | **Last Amended**: 2025-10-04
