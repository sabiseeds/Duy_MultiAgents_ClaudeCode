"""
Python script to initialize PostgreSQL database
This script creates the database and schema without requiring psql command
Works with Docker postgres-pgvector
"""
import asyncio
import asyncpg
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    os.system("chcp 65001 > nul")


DB_HOST = "192.168.1.33"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_NAME = "multi_agent_db"


async def create_database():
    """Create the database if it doesn't exist"""
    print("Connecting to PostgreSQL server...")

    try:
        # Connect to default postgres database
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database="postgres"
        )

        try:
            # Check if database exists
            exists = await conn.fetchval(
                "SELECT 1 FROM pg_database WHERE datname = $1",
                DB_NAME
            )

            if exists:
                print(f"[WARNING] Database '{DB_NAME}' already exists. Dropping it...")
                # Terminate existing connections
                await conn.execute(
                    f"""
                    SELECT pg_terminate_backend(pg_stat_activity.pid)
                    FROM pg_stat_activity
                    WHERE pg_stat_activity.datname = '{DB_NAME}'
                    AND pid <> pg_backend_pid()
                    """
                )
                await conn.execute(f"DROP DATABASE {DB_NAME}")
                print(f"[OK] Database '{DB_NAME}' dropped")

            # Create database
            await conn.execute(f"CREATE DATABASE {DB_NAME}")
            print(f"[OK] Database '{DB_NAME}' created successfully")

        finally:
            await conn.close()

    except Exception as e:
        print(f"[ERROR] Error creating database: {e}")
        sys.exit(1)


async def create_schema():
    """Create all tables and indexes"""
    print(f"\nConnecting to database '{DB_NAME}'...")

    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

        try:
            print("Creating tables...")

            # Create tasks table
            await conn.execute("""
                CREATE TABLE tasks (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    status TEXT NOT NULL CHECK (status IN ('pending', 'in_progress', 'completed', 'failed', 'cancelled')),
                    subtasks JSONB,
                    result JSONB,
                    error TEXT,
                    CONSTRAINT description_length CHECK (LENGTH(description) BETWEEN 10 AND 5000)
                )
            """)
            print("[OK] Table 'tasks' created")

            # Create subtask_results table
            await conn.execute("""
                CREATE TABLE subtask_results (
                    id SERIAL PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    subtask_id TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('completed', 'failed')),
                    output JSONB,
                    error TEXT,
                    execution_time FLOAT NOT NULL CHECK (execution_time > 0),
                    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
                    FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
                    CHECK ((status = 'completed' AND output IS NOT NULL) OR (status = 'failed' AND error IS NOT NULL))
                )
            """)
            print("[OK] Table 'subtask_results' created")

            # Create agent_logs table
            await conn.execute("""
                CREATE TABLE agent_logs (
                    id SERIAL PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    task_id TEXT,
                    log_level TEXT NOT NULL CHECK (log_level IN ('INFO', 'DEBUG', 'ERROR', 'WARN')),
                    message TEXT NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            print("[OK] Table 'agent_logs' created")

            print("\nCreating indexes...")

            # Tasks indexes
            await conn.execute("CREATE INDEX idx_tasks_status ON tasks(status)")
            await conn.execute("CREATE INDEX idx_tasks_user ON tasks(user_id)")
            await conn.execute("CREATE INDEX idx_tasks_created ON tasks(created_at DESC)")
            print("[OK] Created 3 indexes on 'tasks' table")

            # Subtask results indexes
            await conn.execute("CREATE INDEX idx_subtask_results_task ON subtask_results(task_id)")
            await conn.execute("CREATE INDEX idx_subtask_results_agent ON subtask_results(agent_id)")
            await conn.execute("CREATE INDEX idx_subtask_results_created ON subtask_results(created_at DESC)")
            print("[OK] Created 3 indexes on 'subtask_results' table")

            # Agent logs indexes
            await conn.execute("CREATE INDEX idx_agent_logs_agent ON agent_logs(agent_id)")
            await conn.execute("CREATE INDEX idx_agent_logs_task ON agent_logs(task_id)")
            await conn.execute("CREATE INDEX idx_agent_logs_level ON agent_logs(log_level)")
            await conn.execute("CREATE INDEX idx_agent_logs_created ON agent_logs(created_at DESC)")
            print("[OK] Created 4 indexes on 'agent_logs' table")

            # Verify tables created
            print("\nVerifying schema...")
            tables = await conn.fetch("""
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
            """)

            print(f"\n[TABLES] Created ({len(tables)} total):")
            for table in tables:
                print(f"   - {table['tablename']}")

            # Count indexes
            indexes = await conn.fetch("""
                SELECT indexname FROM pg_indexes
                WHERE schemaname = 'public'
                AND indexname LIKE 'idx_%'
                ORDER BY indexname
            """)

            print(f"\n[INDEXES] Created ({len(indexes)} total):")
            for index in indexes:
                print(f"   - {index['indexname']}")

        finally:
            await conn.close()

    except Exception as e:
        print(f"[ERROR] Error creating schema: {e}")
        sys.exit(1)


async def main():
    print("=" * 60)
    print("Multi-Agent Task Execution System - Database Initialization")
    print("=" * 60)
    print(f"\nTarget: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}\n")

    await create_database()
    await create_schema()

    print("\n" + "=" * 60)
    print("[SUCCESS] Database initialization completed successfully!")
    print("=" * 60)
    print(f"\nConnection string:")
    print(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")
    print("\n[INFO] Database: Docker postgres-pgvector container")
    print("\nNext step: Run 'python scripts/test_db.py' to verify connectivity")


if __name__ == "__main__":
    asyncio.run(main())
