# Quickstart Guide: Multi-Agent Task Execution System

**Goal**: Submit your first task and see it execute across multiple agents within 5 minutes.

---

## Prerequisites

- Docker and Docker Compose installed
- `ANTHROPIC_API_KEY` environment variable set
- At least 8GB RAM available
- Ports 8000-8005 and 8501 available

---

## Step 1: Clone and Setup (1 minute)

```bash
# Clone repository (or navigate to it)
cd MultiAgents_ClaudeCode

# Copy environment template
cp .env.example .env

# Edit .env and add your API key
# ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxx
nano .env  # or use your preferred editor
```

---

## Step 2: Start All Services (2 minutes)

```bash
# Start PostgreSQL, Redis, Orchestrator, 5 Agents, and Streamlit UI
docker-compose up -d

# Wait for services to initialize (approximately 30 seconds)
# Check logs to ensure all services are healthy
docker-compose logs -f orchestrator
# You should see: "Uvicorn running on http://0.0.0.0:8000"
# Press Ctrl+C to stop following logs

# Verify all agents registered
curl http://localhost:8000/agents
# Should return JSON with 5 agents
```

**Expected Output**:
```json
{
  "agents": [
    {
      "agent_id": "agent_1",
      "port": 8001,
      "is_available": true,
      "capabilities": ["data_analysis", "code_generation"],
      "tasks_completed": 0
    },
    // ... 4 more agents
  ]
}
```

---

## Step 3: Submit a Simple Task (30 seconds)

**Option A: Via Streamlit UI (Recommended)**

```bash
# Open browser to Streamlit dashboard
open http://localhost:8501  # macOS
# or navigate manually to http://localhost:8501

# In the UI:
# 1. Enter task description: "Calculate factorial of 10"
# 2. Click "Submit Task"
# 3. Watch real-time progress as task executes
```

**Option B: Via API**

```bash
# Submit task via POST request
curl -X POST "http://localhost:8000/tasks?description=Calculate%20factorial%20of%2010&user_id=quickstart_user"
```

**Expected Response**:
```json
{
  "task_id": "task_abc123def456",
  "status": "created",
  "subtasks_count": 1,
  "initial_subtasks_queued": 1
}
```

---

## Step 4: Monitor Task Execution (1 minute)

**Via Streamlit UI**:
- Real-time updates show task progress
- See which agent is executing the subtask
- View completion status and results

**Via API**:
```bash
# Get task status (replace task_id with actual ID from Step 3)
curl http://localhost:8000/tasks/task_abc123def456
```

**Expected Response** (when completed):
```json
{
  "task": {
    "id": "task_abc123def456",
    "description": "Calculate factorial of 10",
    "status": "completed",
    "created_at": "2025-10-04T10:00:00Z",
    "updated_at": "2025-10-04T10:00:15Z",
    "result": {
      "subtask_results": [
        {
          "subtask_id": "subtask_xyz789",
          "agent_id": "agent_1",
          "status": "completed",
          "output": {
            "success": true,
            "data": {"factorial_10": 3628800},
            "summary": "Calculated factorial of 10 = 3,628,800"
          },
          "execution_time": 2.5
        }
      ],
      "summary": "All subtasks completed"
    }
  },
  "subtask_results": [...]
}
```

---

## Step 5: Try a Complex Multi-Step Task (1 minute)

```bash
# Submit a task that requires multiple subtasks
curl -X POST "http://localhost:8000/tasks?description=Fetch%20weather%20data%20from%20API,%20analyze%20temperature%20trends,%20and%20create%20summary%20report&user_id=quickstart_user"
```

This task will be decomposed into:
1. **Web Scraping**: Fetch weather data (Agent 2)
2. **Data Analysis**: Analyze temperature trends (Agent 1 or 5)
3. **Code Generation**: Create summary report (Agent 1 or 4)

**Monitor in Streamlit UI**:
- You'll see 3 subtasks created
- Agents will execute them in parallel (if no dependencies)
- Final result will aggregate all outputs

---

## Validation Checklist

After completing these steps, verify:

- [ ] All 5 agents show `is_available: true` in `/agents` endpoint
- [ ] Simple task completes within 30 seconds
- [ ] Task status transitions: pending → in_progress → completed
- [ ] Streamlit UI shows real-time updates
- [ ] Agent logs are visible in Streamlit dashboard
- [ ] Complex task correctly decomposes into multiple subtasks
- [ ] Results are aggregated in final task result

---

## Troubleshooting

**Problem**: Agents not showing in `/agents` endpoint
- **Solution**: Wait 10-15 seconds for agents to complete startup and send first heartbeat
- **Check**: `docker-compose logs agent1` for errors

**Problem**: Task stuck in "pending" status
- **Solution**: Check if any agents have required capabilities
- **Check**: `curl http://localhost:8000/agents/available` to see available agents

**Problem**: Task fails with "Agent busy"
- **Solution**: Wait for current task to complete, or restart agents
- **Check**: `curl http://localhost:8001/status` to see agent current_task

**Problem**: Streamlit UI not loading
- **Solution**: Check if port 8501 is available and service is running
- **Check**: `docker-compose logs streamlit`

**Problem**: Task decomposition produces no subtasks
- **Solution**: Try more specific task description with clear action verbs
- **Check**: Orchestrator logs for task_analyzer errors

---

## Next Steps

**Try These Example Tasks**:

1. **Data Processing**:
   ```
   "Read CSV file from ./data/sales.csv, filter rows where revenue > 1000, calculate average, and save to new file"
   ```

2. **API Integration**:
   ```
   "Fetch user data from JSONPlaceholder API, extract emails, and store in database table users"
   ```

3. **Multi-Step Workflow**:
   ```
   "Scrape top 10 Python packages from PyPI, analyze their download stats, generate comparison chart, and create markdown report"
   ```

**Explore the System**:
- View agent logs in Streamlit dashboard
- Check PostgreSQL database for task history: `docker exec -it multi_agent_postgres psql -U postgres -d multi_agent_db -c "SELECT * FROM tasks;"`
- Monitor Redis queues: `docker exec -it multi_agent_redis redis-cli LLEN agent_tasks`
- Test agent endpoints directly: `curl http://localhost:8001/health`

**Shutdown**:
```bash
# Stop all services
docker-compose down

# Remove volumes (clears database and Redis)
docker-compose down -v
```

---

## Success Criteria

✅ You successfully submitted a task via UI or API
✅ You monitored task execution in real-time
✅ You retrieved final results from completed task
✅ You understand how tasks decompose into subtasks
✅ You know how to troubleshoot common issues

**Time to first success**: < 5 minutes ✓

