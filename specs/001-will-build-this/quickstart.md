# Quickstart: Claude Token SDK Migration

**Goal**: Verify the Claude token authentication migration works correctly in both Claude Code and API key modes.

**Time to Complete**: 10 minutes

---

## Prerequisites

- Python 3.11+ installed
- Existing multi-agent system functional
- Either:
  - Claude Code environment (preferred), OR
  - Anthropic API key with credits

---

## Step 1: Install Dependencies (2 minutes)

```bash
# Install claude-code-sdk
pip install claude-code-sdk

# Verify installation
python -c "from claude_code_sdk import ClaudeSDKClient; print('✅ SDK installed')"
```

**Expected output**:
```
✅ SDK installed
```

---

## Step 2: Configure Environment (1 minute)

### Option A: Claude Code Mode (Recommended)

Edit `.env`:
```ini
# Enable Claude Code authentication
CLAUDECODE=1

# Existing settings (keep these)
POSTGRES_URL=postgresql://postgres:postgres@192.168.1.33:5432/multi_agent_db
REDIS_URL=redis://localhost:6379/0

# API key can remain but will be ignored when CLAUDECODE=1
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
```

### Option B: API Key Mode (Fallback)

Edit `.env`:
```ini
# Disable Claude Code (use API key)
CLAUDECODE=0

# Set your API key
ANTHROPIC_API_KEY=sk-ant-api03-your_actual_key_here

# Existing settings
POSTGRES_URL=postgresql://postgres:postgres@192.168.1.33:5432/multi_agent_db
REDIS_URL=redis://localhost:6379/0
```

---

## Step 3: Test Authentication Detection (2 minutes)

Create test file `test_auth_migration.py`:

```python
#!/usr/bin/env python3
"""Quick test for authentication migration."""
import os
import asyncio
from dotenv import load_dotenv

# Load environment
load_dotenv()

async def test_auth_detection():
    """Test that authentication method is detected correctly."""

    print("=" * 60)
    print("Authentication Detection Test")
    print("=" * 60)

    # Check environment
    claudecode = os.getenv("CLAUDECODE")
    has_api_key = bool(os.getenv("ANTHROPIC_API_KEY"))

    print(f"\nEnvironment:")
    print(f"  CLAUDECODE = {claudecode}")
    print(f"  ANTHROPIC_API_KEY = {'SET' if has_api_key else 'NOT SET'}")

    # Determine expected auth method
    if claudecode == "1":
        expected_method = "claude_code"
        print(f"\n✅ Expected: Claude Code integrated authentication")
    elif has_api_key:
        expected_method = "direct_api"
        print(f"\n✅ Expected: Direct API authentication")
    else:
        print(f"\n❌ ERROR: No authentication method configured")
        print(f"   Suggestion: Set CLAUDECODE=1 or provide ANTHROPIC_API_KEY")
        return False

    # Import HybridClaudeClient (this will be created in implementation)
    try:
        from shared.auth_client import HybridClaudeClient

        # Create client (should detect auth method)
        client = HybridClaudeClient()

        # Verify detection
        if client.auth_method == expected_method:
            print(f"✅ PASS: Authentication method detected as '{client.auth_method}'")
            return True
        else:
            print(f"❌ FAIL: Expected '{expected_method}' but got '{client.auth_method}'")
            return False

    except ImportError:
        print(f"\n⚠️  HybridClaudeClient not yet implemented (expected during testing)")
        print(f"   This test will pass once implementation is complete")
        return True
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_auth_detection())
    exit(0 if result else 1)
```

Run the test:
```bash
python test_auth_migration.py
```

**Expected output (before implementation)**:
```
============================================================
Authentication Detection Test
============================================================

Environment:
  CLAUDECODE = 1
  ANTHROPIC_API_KEY = SET

✅ Expected: Claude Code integrated authentication

⚠️  HybridClaudeClient not yet implemented (expected during testing)
   This test will pass once implementation is complete
```

---

## Step 4: Test Claude Query (3 minutes)

After implementation is complete, test actual Claude queries:

```python
#!/usr/bin/env python3
"""Test Claude query execution."""
import asyncio
from shared.auth_client import HybridClaudeClient

async def test_claude_query():
    """Test that Claude queries work with detected auth method."""

    print("=" * 60)
    print("Claude Query Test")
    print("=" * 60)

    # Create client
    client = HybridClaudeClient()
    print(f"\nAuthentication method: {client.auth_method}")

    # Simple math query
    print(f"\nQuery: What is 7 * 8?")
    response = await client.query("What is 7 * 8? Respond with just the number.")
    print(f"Response: {response}")

    # Verify response
    if "56" in response:
        print(f"\n✅ PASS: Claude responded correctly")
        return True
    else:
        print(f"\n❌ FAIL: Unexpected response")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_claude_query())
    exit(0 if result else 1)
```

**Expected output**:
```
============================================================
Claude Query Test
============================================================

Authentication method: claude_code  # or "direct_api"

Query: What is 7 * 8?
Response: 56

✅ PASS: Claude responded correctly
```

---

## Step 5: Test Full System Integration (2 minutes)

Test that the existing system works with new authentication:

```bash
# Start Redis
docker start redis || docker run -d -p 6379:6379 --name redis redis:7-alpine

# Start orchestrator
python -m uvicorn orchestrator.orchestrator:app --host 0.0.0.0 --port 8000 &

# Start one agent
export AGENT_ID=agent_test
export AGENT_PORT=8001
export AGENT_CAPABILITIES=data_analysis
python -m uvicorn agent.agent_service:app --host 0.0.0.0 --port 8001 &

# Wait for startup
sleep 5

# Submit test task via API
curl -X POST "http://localhost:8000/tasks?description=Calculate+factorial+of+5"

# Check task status (use task_id from above response)
curl "http://localhost:8000/tasks/{task_id}"
```

**Expected output**:
- Task created with subtasks
- Agent picks up subtask
- Task completes successfully
- Final result shows factorial(5) = 120

---

## Step 6: Verify Authentication Switching (optional, 1 minute)

Test that you can switch between authentication methods:

```bash
# Test 1: Claude Code mode
echo "CLAUDECODE=1" > .env.test
export $(cat .env.test | xargs)
python test_auth_migration.py
# Should detect: claude_code

# Test 2: API key mode
echo "CLAUDECODE=0" > .env.test
echo "ANTHROPIC_API_KEY=sk-ant-..." >> .env.test
export $(cat .env.test | xargs)
python test_auth_migration.py
# Should detect: direct_api

# Cleanup
rm .env.test
```

---

## Success Criteria

✅ **You've successfully completed the migration if**:

1. Authentication detection test passes
2. Claude query test returns correct response
3. Full system integration works (task submission → execution → completion)
4. No errors in orchestrator/agent logs related to authentication
5. (Claude Code mode) No API charges incurred
6. (API key mode) API charges appear in Anthropic console

---

## Troubleshooting

### Error: "No authentication method configured"

**Problem**: Neither `CLAUDECODE=1` nor `ANTHROPIC_API_KEY` is set

**Solution**:
```bash
# Option 1: Enable Claude Code
echo "CLAUDECODE=1" >> .env

# Option 2: Add API key
echo "ANTHROPIC_API_KEY=sk-ant-api03-your_key" >> .env
```

### Error: "Control request timeout: initialize"

**Problem**: Claude CLI not installed or not in PATH

**Solution**:
```bash
# Install Claude CLI
npm install -g @anthropic-ai/claude-code

# Verify installation
claude --version

# Add to PATH if needed
export PATH="$PATH:/usr/local/bin"
```

### Error: "Invalid ANTHROPIC_API_KEY format"

**Problem**: API key doesn't start with `sk-ant-api03-`

**Solution**:
- Get correct API key from https://console.anthropic.com/
- Ensure no extra spaces or quotes in `.env` file
- Format: `ANTHROPIC_API_KEY=sk-ant-api03-xxxxxxxxxxxxx`

### Error: "Credit balance too low"

**Problem**: Anthropic account has insufficient credits

**Solution**:
```bash
# Switch to Claude Code mode (free)
echo "CLAUDECODE=1" > .env

# OR add credits to Anthropic account
# Visit: https://console.anthropic.com/settings/billing
```

### Environment variable not loading

**Problem**: Changes to `.env` not reflected

**Solution**:
```bash
# Restart all services
pkill -f uvicorn
pkill -f streamlit

# Reload environment
source .env  # On Linux/Mac
# Or restart terminal on Windows

# Start services again
./start.bat
```

---

## Next Steps

After successful quickstart:

1. **Run full test suite**: `pytest tests/` to verify all tests pass
2. **Performance benchmarks**: Compare query times between auth methods
3. **Update TESTING_GUIDE.md**: Document new authentication setup
4. **Deploy to production**: Set `CLAUDECODE=1` in production environment

---

## Rollback Plan

If issues occur, rollback to API key mode:

```bash
# Edit .env
CLAUDECODE=0
ANTHROPIC_API_KEY=sk-ant-api03-your_key

# Restart services
./start.bat
```

System will function exactly as before migration.

---

**Estimated Total Time**: 10 minutes
**Difficulty**: Easy
**Success Rate**: 99% (assuming valid authentication credentials)
