# Quick Setup & Test Guide

## Prerequisites Checklist
- [ ] PostgreSQL 15 installed and running on `192.168.1.33:5432`
- [ ] Redis installed and running on `localhost:6379`
- [ ] Python 3.11+ installed
- [ ] Anthropic API key available

---

## Step 1: Database Setup (2 minutes)

### Option A: Using psql command line
```bash
# Navigate to project directory
cd D:\CodebyAI\Duy_MultiAgents_ClaudeCode\MultiAgents_ClaudeCode

# Run the initialization script
psql -U postgres -h 192.168.1.33 -p 5432 -f scripts/init_database.sql
```

### Option B: Using pgAdmin or any PostgreSQL client
1. Connect to PostgreSQL server: `192.168.1.33:5432`, user: `postgres`, password: `postgres`
2. Open Query Tool
3. Copy and paste contents of `scripts/init_database.sql`
4. Execute

### Verify Database Created
```bash
psql -U postgres -h 192.168.1.33 -p 5432 -c "\l" | grep multi_agent_db
```

Expected output: `multi_agent_db | postgres | ...`

---

## Step 2: Python Environment Setup (3 minutes)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On Linux/Mac:
# source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify key packages installed
pip list | grep -E "fastapi|anthropic|asyncpg|redis|streamlit"
```

---

## Step 3: Environment Configuration (1 minute)

```bash
# Copy environment template
cp .env.example .env

# Edit .env file and add your API key
# Required: ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
```

Update `.env` with:
```ini
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
POSTGRES_URL=postgresql://postgres:postgres@192.168.1.33:5432/multi_agent_db
REDIS_URL=redis://localhost:6379/0
SDK_PERMISSION_MODE=auto
```

---

## Step 4: Verify Database Schema (1 minute)

```bash
# Connect to database and check tables
psql -U postgres -h 192.168.1.33 -p 5432 -d multi_agent_db -c "\dt"
```

Expected output:
```
              List of relations
 Schema |       Name        | Type  |  Owner
--------+-------------------+-------+----------
 public | agent_logs        | table | postgres
 public | subtask_results   | table | postgres
 public | tasks             | table | postgres
```

### Verify table structures:
```bash
# Check tasks table
psql -U postgres -h 192.168.1.33 -p 5432 -d multi_agent_db -c "\d tasks"

# Check indexes
psql -U postgres -h 192.168.1.33 -p 5432 -d multi_agent_db -c "\di"
```

---

## Step 5: Test Database Connectivity (2 minutes)

Create a test script `scripts/test_db.py`:

```python
import asyncio
import asyncpg
from datetime import datetime

async def test_database():
    # Connect to database
    conn = await asyncpg.connect(
        "postgresql://postgres:postgres@192.168.1.33:5432/multi_agent_db"
    )

    try:
        # Test: Insert a task
        task_id = "task_test_001"
        await conn.execute(
            """
            INSERT INTO tasks (id, user_id, description, status, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (id) DO NOTHING
            """,
            task_id, "test_user", "Test task description", "pending",
            datetime.utcnow(), datetime.utcnow()
        )
        print("✓ Task inserted successfully")

        # Test: Read the task
        row = await conn.fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        print(f"✓ Task retrieved: {row['id']} - {row['status']}")

        # Test: Insert subtask result
        await conn.execute(
            """
            INSERT INTO subtask_results
            (task_id, subtask_id, agent_id, status, output, execution_time)
            VALUES ($1, $2, $3, $4, $5, $6)
            """,
            task_id, "subtask_001", "agent_1", "completed",
            '{"result": "success"}', 2.5
        )
        print("✓ Subtask result inserted successfully")

        # Test: Insert log entry
        await conn.execute(
            """
            INSERT INTO agent_logs (agent_id, task_id, log_level, message)
            VALUES ($1, $2, $3, $4)
            """,
            "agent_1", task_id, "INFO", "Test log message"
        )
        print("✓ Agent log inserted successfully")

        # Test: Query with indexes
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM tasks WHERE status = $1", "pending"
        )
        print(f"✓ Index query successful: {count} pending tasks")

        # Cleanup
        await conn.execute("DELETE FROM subtask_results WHERE task_id = $1", task_id)
        await conn.execute("DELETE FROM agent_logs WHERE task_id = $1", task_id)
        await conn.execute("DELETE FROM tasks WHERE id = $1", task_id)
        print("✓ Cleanup successful")

        print("\n🎉 All database tests passed!")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_database())
```

Run the test:
```bash
python scripts/test_db.py
```

Expected output:
```
✓ Task inserted successfully
✓ Task retrieved: task_test_001 - pending
✓ Subtask result inserted successfully
✓ Agent log inserted successfully
✓ Index query successful: 1 pending tasks
✓ Cleanup successful

🎉 All database tests passed!
```

---

## Step 6: Test Redis Connectivity (1 minute)

Create test script `scripts/test_redis.py`:

```python
import asyncio
import redis.asyncio as redis

async def test_redis():
    # Connect to Redis
    client = await redis.from_url("redis://localhost:6379/0")

    try:
        # Test: Ping
        pong = await client.ping()
        print(f"✓ Redis ping: {pong}")

        # Test: Set and get
        await client.set("test_key", "test_value")
        value = await client.get("test_key")
        print(f"✓ Redis get: {value.decode()}")

        # Test: List operations (queue simulation)
        await client.rpush("test_queue", "item1", "item2")
        length = await client.llen("test_queue")
        print(f"✓ Redis queue length: {length}")

        item = await client.lpop("test_queue")
        print(f"✓ Redis dequeue: {item.decode()}")

        # Test: Hash operations (agent status simulation)
        await client.hset("agent:test", mapping={
            "agent_id": "agent_1",
            "is_available": "true",
            "cpu_usage": "25.5"
        })
        status = await client.hgetall("agent:test")
        print(f"✓ Redis hash: {len(status)} fields stored")

        # Cleanup
        await client.delete("test_key", "test_queue", "agent:test")
        print("✓ Cleanup successful")

        print("\n🎉 All Redis tests passed!")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_redis())
```

Run the test:
```bash
python scripts/test_redis.py
```

---

## Step 7: Verify Contract Tests Fail (TDD Verification)

This step confirms our TDD approach is working - tests should FAIL before implementation:

```bash
# Run contract tests (should fail - no implementation yet)
pytest tests/contract/test_orchestrator_api.py -v

# Expected: All tests FAILED (connection refused or 404)
```

Expected output:
```
tests/contract/test_orchestrator_api.py::TestPostTasks::test_post_tasks_valid_request FAILED
tests/contract/test_orchestrator_api.py::TestGetTask::test_get_task_valid_id FAILED
...
====== X failed in X.XXs ======
```

**This is CORRECT!** Tests should fail because we haven't implemented the orchestrator yet (T016-T023).

---

## Summary Checklist

After completing all steps, verify:

- [x] ✅ PostgreSQL database `multi_agent_db` created
- [x] ✅ 3 tables created: `tasks`, `subtask_results`, `agent_logs`
- [x] ✅ 10 indexes created (verified with `\di`)
- [x] ✅ Python virtual environment activated
- [x] ✅ All dependencies installed (FastAPI, Claude SDK, asyncpg, redis, etc.)
- [x] ✅ `.env` file configured with ANTHROPIC_API_KEY
- [x] ✅ Database connectivity test passed
- [x] ✅ Redis connectivity test passed
- [x] ✅ Contract tests fail (TDD verification)

---

## What's Working Now

✅ **Infrastructure**:
- PostgreSQL database with complete schema
- Redis connection ready
- Python environment with all dependencies

✅ **Testing Framework**:
- Contract tests written (10 test files, 40+ test cases)
- Integration tests written (2 test files, 14+ test cases)
- All tests currently fail (expected - TDD approach)

❌ **Not Yet Implemented** (Tasks T011-T030):
- Pydantic models (shared/models.py)
- Database manager (shared/database.py)
- Redis manager (shared/redis_manager.py)
- Orchestrator service
- Agent services
- Streamlit UI

---

## Next Steps

Once the database and Redis tests pass, you're ready to proceed with:

1. **T011-T015**: Write unit tests (models, database, redis, task_analyzer)
2. **T016-T019**: Implement shared components (models, config, database, redis)
3. **T020-T023**: Implement orchestrator service
4. **T024-T025**: Implement agent services
5. **T026**: Implement Streamlit UI
6. **T027**: End-to-end integration
7. **T028-T030**: Polish and validation

---

## Troubleshooting

**PostgreSQL connection refused**:
```bash
# Check PostgreSQL is running
# Windows: Open Services, find PostgreSQL, ensure it's Running
# Or restart: net stop postgresql-x64-15 && net start postgresql-x64-15
```

**Redis connection refused**:
```bash
# Check Redis is running
# Windows: Open Services, find Redis, ensure it's Running
# Or start manually: redis-server
```

**Import errors**:
```bash
# Verify virtual environment is activated
# Should see (venv) in your prompt
# Re-install dependencies: pip install -r requirements.txt
```

**psql command not found**:
```bash
# Add PostgreSQL bin to PATH:
# Windows: Add C:\Program Files\PostgreSQL\15\bin to System PATH
# Or use full path: "C:\Program Files\PostgreSQL\15\bin\psql.exe"
```
