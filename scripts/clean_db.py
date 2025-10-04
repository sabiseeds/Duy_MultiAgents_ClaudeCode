"""
Clean database for fresh testing - truncate all tables
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


async def clean_database():
    """Truncate all tables to clean data"""
    print("=" * 60)
    print("Multi-Agent System - Database Cleanup")
    print("=" * 60)
    print(f"\nTarget: {DB_USER}@{DB_HOST}:{DB_PORT}/{DB_NAME}\n")

    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

        try:
            print("Cleaning database tables...")

            # Truncate all tables (CASCADE to handle foreign keys)
            await conn.execute("TRUNCATE TABLE tasks CASCADE;")
            print("[OK] Truncated 'tasks' table")

            await conn.execute("TRUNCATE TABLE subtask_results CASCADE;")
            print("[OK] Truncated 'subtask_results' table")

            await conn.execute("TRUNCATE TABLE agent_logs CASCADE;")
            print("[OK] Truncated 'agent_logs' table")

            # Verify clean
            tasks_count = await conn.fetchval("SELECT COUNT(*) FROM tasks")
            results_count = await conn.fetchval("SELECT COUNT(*) FROM subtask_results")
            logs_count = await conn.fetchval("SELECT COUNT(*) FROM agent_logs")

            print("\n" + "=" * 60)
            print("[SUCCESS] Database cleaned successfully!")
            print("=" * 60)
            print(f"\nVerification:")
            print(f"  Tasks: {tasks_count}")
            print(f"  Subtask Results: {results_count}")
            print(f"  Agent Logs: {logs_count}")
            print("\nDatabase is ready for fresh testing!")

        finally:
            await conn.close()

    except Exception as e:
        print(f"[ERROR] Failed to clean database: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(clean_database())
