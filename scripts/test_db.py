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
