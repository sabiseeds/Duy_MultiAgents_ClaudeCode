# Testing Guide - Multi-Agent System

**Status**: Core implementation complete! Ready for testing via Streamlit UI

---

## 🎯 Quick Start (5 Minutes)

### Step 1: Set Up Environment (1 minute)

```bash
# Ensure you're in the project directory
cd D:\CodebyAI\Duy_MultiAgents_ClaudeCode\MultiAgents_ClaudeCode

# Make sure .env file exists with your API key
# Edit .env and set:
# ANTHROPIC_API_KEY=your_actual_key_here
notepad .env
```

**Required in .env**:
```ini
ANTHROPIC_API_KEY=sk-ant-your_actual_key
POSTGRES_URL=postgresql://postgres:postgres@192.168.1.33:5432/multi_agent_db
REDIS_URL=redis://localhost:6379/0
```

### Step 2: Start Redis (1 minute)

Redis must be running. Start it with:

```bash
# Option 1: Docker
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Option 2: Windows Service
Start-Service Redis

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

### Step 3: Start All Services (1 minute)

```bash
# Double-click start.bat OR run from command line:
start.bat
```

This will open 7 windows:
- 1 Orchestrator (port 8000)
- 5 Agents (ports 8001-8005)
- 1 Streamlit UI (port 8501)

Wait about 10-15 seconds for all services to start.

### Step 4: Open Streamlit UI (30 seconds)

The browser should open automatically. If not:
- Open: http://localhost:8501

### Step 5: Test the System (2 minutes)

1. **Submit a simple task**:
   - Go to "Submit Task" tab
   - Enter: `Calculate the factorial of 10`
   - Click "Submit Task"
   - Note the Task ID

2. **Monitor execution**:
   - Go to "Monitor Tasks" tab
   - Paste the Task ID
   - Click "Refresh Status" or enable "Auto-refresh"
   - Watch as the task progresses through: pending → in_progress → completed

3. **View agents**:
   - Go to "Agent Dashboard" tab
   - See all 5 agents and their status
   - Check which agent executed your task

---

## 📊 What's Implemented

### ✅ Core Components
- **Shared Models** (`shared/models.py`) - Pydantic data models
- **Configuration** (`shared/config.py`) - Environment settings
- **Database Manager** (`shared/database.py`) - PostgreSQL operations
- **Redis Manager** (`shared/redis_manager.py`) - Queue & agent coordination

### ✅ Orchestrator Service
- **Task Analyzer** (`orchestrator/task_analyzer.py`) - Claude AI task decomposition
- **FastAPI Endpoints** (`orchestrator/orchestrator.py`):
  - POST /tasks - Submit new tasks
  - GET /tasks/{id} - Get task status
  - GET /agents - List all agents
  - GET /agents/available - Filter by capability
- **Background Workers**:
  - `dispatch_tasks()` - Assigns tasks to agents
  - `process_results()` - Aggregates results

### ✅ Agent Service
- **Agent Implementation** (`agent/agent_service.py`) - Claude AI execution
- **Endpoints**:
  - GET /health - Health check
  - GET /status - Detailed status
  - POST /execute - Execute subtask
- **Heartbeat System** - 10-second intervals to Redis

### ✅ Streamlit UI
- **Task Submission** - User-friendly form
- **Task Monitoring** - Real-time status updates
- **Agent Dashboard** - Live agent metrics

---

## 🧪 Test Scenarios

### Scenario 1: Simple Calculation
```
Task: Calculate the factorial of 10
Expected: Single subtask, quick execution, result shows 3628800
```

### Scenario 2: Multi-Step Task
```
Task: Fetch data from an API, analyze it statistically, and create a summary report
Expected: 3 subtasks with different capabilities, sequential/parallel execution
```

### Scenario 3: Data Analysis
```
Task: Analyze a dataset of 100 numbers, find mean, median, mode, and standard deviation
Expected: Data analysis capability used, statistical results
```

### Scenario 4: Code Generation
```
Task: Write a Python function to sort a list using quicksort algorithm
Expected: Code generation capability, working Python code
```

---

## 🔧 Troubleshooting

### Redis Connection Error
**Symptom**: Services fail to start, "Connection refused" error

**Solution**:
```bash
# Start Redis
docker run -d -p 6379:6379 --name redis redis:7-alpine

# Verify
redis-cli ping
```

### Database Connection Error
**Symptom**: "Connection to database failed"

**Solution**:
```bash
# Verify PostgreSQL is accessible
python scripts/test_db.py

# Should see: [SUCCESS] All database tests passed!
```

### Agent Not Registering
**Symptom**: Agents don't show in dashboard

**Solution**:
- Wait 10-15 seconds for heartbeat
- Check Redis is running
- Verify agent windows show "Ready" message

### Task Stuck in Pending
**Symptom**: Task status doesn't change from "pending"

**Solution**:
- Check agents are registered (Agent Dashboard tab)
- Verify orchestrator background workers are running
- Check orchestrator logs for errors

### Streamlit Won't Start
**Symptom**: "ModuleNotFoundError: No module named 'streamlit'"

**Solution**:
```bash
pip install -r requirements.txt
```

---

## 📝 API Testing (Optional)

### Test with cURL

```bash
# 1. Submit a task
curl -X POST "http://localhost:8000/tasks?description=Calculate%20factorial%20of%205"

# Response: {"task_id":"task_xxxxx",...}

# 2. Check task status
curl "http://localhost:8000/tasks/task_xxxxx"

# 3. List all agents
curl "http://localhost:8000/agents"

# 4. Get available agents with specific capability
curl "http://localhost:8000/agents/available?capability=data_analysis"
```

### Test with Python

```python
import httpx

# Submit task
response = httpx.post(
    "http://localhost:8000/tasks",
    params={"description": "Calculate factorial of 10"}
)
print(response.json())

# Get status
task_id = response.json()["task_id"]
status = httpx.get(f"http://localhost:8000/tasks/{task_id}")
print(status.json())
```

---

## 🎨 UI Features

### Task Submission Tab
- **Description Input**: Multi-line text area (10-5000 chars)
- **User ID**: Optional identifier
- **Submit Button**: Initiates task processing
- **Success Message**: Shows task ID and subtask count

### Monitor Tasks Tab
- **Task ID Input**: Enter or auto-populate from last submission
- **Auto-refresh**: Toggle for real-time updates (2s interval)
- **Status Metrics**: Status, subtasks, completed, failed
- **Progress Bar**: Visual completion indicator
- **Subtask Details**: Expandable sections for each subtask
- **Results Display**: JSON output from completed tasks

### Agent Dashboard Tab
- **Summary Metrics**: Total, available, completed tasks, avg CPU
- **Agent Cards**: Expandable details for each agent
- **Status Indicators**: 🟢 Available / 🔴 Busy
- **System Metrics**: CPU, memory, tasks completed
- **Auto-refresh**: 5-second interval option

---

## 🚀 Next Steps

### After Successful Testing

1. **Try Complex Tasks**: Submit multi-step workflows
2. **Test Concurrency**: Submit multiple tasks simultaneously
3. **Monitor Performance**: Check agent CPU/memory usage
4. **View Logs**: Check database for agent_logs entries

### Development Tasks (Optional)

- **T011-T015**: Add remaining unit tests
- **T027**: Full integration testing
- **T028-T030**: Scripts, documentation, validation

---

## 📊 System Architecture

```
User (Streamlit UI:8501)
    ↓
Orchestrator (FastAPI:8000)
    ↓
Redis (Queues:6379)
    ↓
Agents (FastAPI:8001-8005) → Claude AI
    ↓
PostgreSQL (Database:5432)
```

**Data Flow**:
1. User submits task via Streamlit
2. Orchestrator decomposes task using Claude AI
3. Subtasks queued in Redis
4. Dispatcher assigns to available agents
5. Agents execute using Claude AI
6. Results queued back to Redis
7. Orchestrator aggregates and stores in PostgreSQL
8. UI displays final results

---

## ✅ Success Criteria

You'll know it's working when:

- ✅ All 7 service windows start without errors
- ✅ Streamlit UI loads at http://localhost:8501
- ✅ Agent Dashboard shows 5 registered agents
- ✅ Task submission returns a task ID
- ✅ Task status changes from pending → in_progress → completed
- ✅ Final results appear in the Monitor tab
- ✅ Agents show as busy then available again

---

## 🎉 You're Ready!

**Current Implementation Status**:
- Core: 100% ✅
- UI: 100% ✅
- Testing: Ready ✅

**To start testing**: Run `start.bat` and open http://localhost:8501

Enjoy exploring your Multi-Agent Task Execution System! 🤖
