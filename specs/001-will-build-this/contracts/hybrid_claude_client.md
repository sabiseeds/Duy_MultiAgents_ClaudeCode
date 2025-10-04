# Contract: HybridClaudeClient

**Component**: `shared/auth_client.py`
**Purpose**: Unified authentication interface for Claude Code and direct API

---

## Class Interface

### Constructor

```python
def __init__(self, config: Optional[AuthConfig] = None) -> None:
    """
    Initialize hybrid client with automatic authentication detection.

    Args:
        config: Optional authentication configuration.
                If None, loads from global settings.

    Raises:
        AuthenticationError: If no valid authentication method available

    Post-conditions:
        - self.auth_method is set to "claude_code" or "direct_api"
        - self.config contains validated configuration
    """
```

**Contract**:
- MUST detect authentication method during initialization
- MUST raise `AuthenticationError` if neither CLAUDECODE=1 nor ANTHROPIC_API_KEY available
- MUST validate config parameters (model, permission_mode, timeouts)
- MUST NOT make any Claude API calls during initialization

---

### Method: query

```python
async def query(
    self,
    prompt: str,
    system_prompt: Optional[str] = None
) -> str:
    """
    Execute Claude query using detected authentication method.

    Args:
        prompt: User prompt for Claude (10-100,000 characters)
        system_prompt: Optional system prompt (max 10,000 characters)
                      If None, uses config.system_prompt

    Returns:
        str: Claude response text (non-empty)

    Raises:
        AuthenticationError: Authentication failed
        TimeoutError: Request exceeded timeout
        ValueError: Invalid prompt (empty or too long)

    Side effects:
        - Claude Code mode: Temporarily removes/restores ANTHROPIC_API_KEY from environment
        - Direct API mode: No environment modifications

    Performance:
        - First call: <5s (includes SDK initialization)
        - Subsequent calls: <2s (connection reuse)
    """
```

**Contract**:
- MUST validate `prompt` is non-empty and <100,000 characters
- MUST validate `system_prompt` (if provided) is <10,000 characters
- MUST use `system_prompt` parameter if provided, else use `config.system_prompt`
- MUST return non-empty response
- MUST retry up to `config.max_retries` times on transient failures
- MUST restore environment state even if exception occurs (finally block)
- MUST raise specific `AuthenticationError` with actionable `suggestion` field

---

### Method: _detect_auth_method (Private)

```python
def _detect_auth_method(self) -> str:
    """
    Detect which authentication method to use.

    Returns:
        "claude_code" if CLAUDECODE=1
        "direct_api" if ANTHROPIC_API_KEY present

    Raises:
        AuthenticationError: Neither method available

    Priority:
        1. CLAUDECODE=1 (highest priority)
        2. ANTHROPIC_API_KEY (fallback)
        3. Raise AuthenticationError (no method)
    """
```

**Contract**:
- MUST check `os.getenv("CLAUDECODE") == "1"` first
- MUST check `os.getenv("ANTHROPIC_API_KEY")` second
- MUST raise `AuthenticationError` with suggestion="Set CLAUDECODE=1 or provide ANTHROPIC_API_KEY" if neither
- MUST NOT modify environment
- MUST be deterministic (same environment = same result)

---

### Method: _query_claude_code (Private)

```python
async def _query_claude_code(
    self,
    prompt: str,
    system_prompt: Optional[str]
) -> str:
    """
    Query using Claude Code SDK.

    Args:
        prompt: User prompt
        system_prompt: System prompt (optional)

    Returns:
        str: Response text

    Raises:
        AuthenticationError: Claude CLI not found / token invalid
        TimeoutError: SDK initialization or query timeout

    Side effects:
        - Removes ANTHROPIC_API_KEY from environment before SDK creation
        - Restores ANTHROPIC_API_KEY after SDK completion
    """
```

**Contract**:
- MUST use `ClaudeSDKClient` from `claude_code_sdk`
- MUST create `ClaudeCodeOptions` with:
  - `system_prompt=system_prompt`
  - `model=self.config.model`
  - `permission_mode=self.config.permission_mode`
- MUST temporarily remove `ANTHROPIC_API_KEY` before client creation
- MUST restore `ANTHROPIC_API_KEY` in finally block
- MUST use async context manager (`async with ClaudeSDKClient...`)
- MUST stream response via `async for message in client.receive_response()`
- MUST concatenate all text blocks from response

---

### Method: _query_direct_api (Private)

```python
async def _query_direct_api(
    self,
    prompt: str,
    system_prompt: Optional[str]
) -> str:
    """
    Query using direct Anthropic API.

    Args:
        prompt: User prompt
        system_prompt: System prompt (optional)

    Returns:
        str: Response text

    Raises:
        AuthenticationError: Invalid API key
        anthropic.RateLimitError: Rate limit exceeded
        anthropic.APIError: API error
    """
```

**Contract**:
- MUST use `anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))`
- MUST call `client.messages.create()` with:
  - `model=self.config.model`
  - `max_tokens=self.config.max_tokens`
  - `temperature=self.config.temperature`
  - `system=system_prompt` (if provided)
  - `messages=[{"role": "user", "content": prompt}]`
- MUST extract text from `response.content[0].text`
- MUST handle `anthropic.RateLimitError` specifically (suggest retry delay)

---

## Exception Hierarchy

```python
class AuthenticationError(Exception):
    """Raised when authentication fails."""
    def __init__(self, message: str, auth_method: str, suggestion: str):
        self.message = message
        self.auth_method = auth_method  # "claude_code" | "direct_api" | "none"
        self.suggestion = suggestion    # Actionable remediation step
```

**Contract**:
- MUST include actionable `suggestion` field
- MUST specify which `auth_method` failed
- MUST provide clear `message` explaining what went wrong

---

## Configuration Contract

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

**Contract**:
- `model`: MUST be valid Claude model name
- `max_tokens`: MUST be >0 and <=200000
- `temperature`: MUST be >=0.0 and <=1.0
- `permission_mode`: MUST be one of ["auto", "approveEdits", "approveAll", "bypassPermissions"]
- `max_retries`: MUST be >=0
- `timeout`: MUST be >0

---

## Usage Examples

### Example 1: Basic usage (auto-detection)

```python
client = HybridClaudeClient()
response = await client.query("Calculate 2+2")
# Returns: "4" or similar
```

### Example 2: Custom configuration

```python
config = AuthConfig(
    system_prompt="You are a math tutor.",
    max_tokens=2048,
    temperature=0.7
)
client = HybridClaudeClient(config)
response = await client.query("Explain calculus")
```

### Example 3: Error handling

```python
try:
    client = HybridClaudeClient()
    response = await client.query("Hello")
except AuthenticationError as e:
    print(f"Auth failed: {e.message}")
    print(f"Suggestion: {e.suggestion}")
except TimeoutError:
    print("Request timed out, please retry")
```

---

## Testing Contract

### Unit Tests Required

1. **test_detect_auth_method_claude_code**:
   - Given: `CLAUDECODE=1`, `ANTHROPIC_API_KEY=sk-ant-...`
   - When: `_detect_auth_method()` called
   - Then: Returns `"claude_code"` (Claude Code takes priority)

2. **test_detect_auth_method_api_key**:
   - Given: `CLAUDECODE=0`, `ANTHROPIC_API_KEY=sk-ant-...`
   - When: `_detect_auth_method()` called
   - Then: Returns `"direct_api"`

3. **test_detect_auth_method_none**:
   - Given: `CLAUDECODE=0`, no `ANTHROPIC_API_KEY`
   - When: `_detect_auth_method()` called
   - Then: Raises `AuthenticationError` with suggestion

4. **test_query_claude_code_success**:
   - Given: `CLAUDECODE=1`, valid prompt
   - When: `query()` called
   - Then: Returns non-empty response, API key removed/restored

5. **test_query_direct_api_success**:
   - Given: `ANTHROPIC_API_KEY` set, valid prompt
   - When: `query()` called
   - Then: Returns non-empty response, environment unchanged

6. **test_query_invalid_prompt**:
   - Given: Empty prompt `""`
   - When: `query()` called
   - Then: Raises `ValueError`

7. **test_query_retry_logic**:
   - Given: Transient failure on first attempt
   - When: `query()` called with `max_retries=3`
   - Then: Retries and succeeds

8. **test_environment_restoration**:
   - Given: Exception during Claude Code query
   - When: `query()` called
   - Then: `ANTHROPIC_API_KEY` restored in environment

---

## Performance Contract

- **Initialization**: <100ms
- **First query**: <5s (includes SDK initialization)
- **Subsequent queries**: <2s (connection reuse)
- **Memory overhead**: <10MB per client instance

---

## Thread Safety

- ❌ **NOT thread-safe**: Each thread MUST create own instance
- ✅ **Async-safe**: Safe for concurrent async calls within same event loop

---

## Backward Compatibility

- MUST work with existing code that uses `AsyncAnthropic` directly
- MUST NOT break existing `.env` configurations
- MUST default to API key mode if `CLAUDECODE` not set

---

## Security Contract

- MUST NOT log API keys or tokens
- MUST NOT persist authentication credentials to disk
- MUST restore environment state to prevent accidental credential exposure
- MUST validate all inputs before passing to Claude API
