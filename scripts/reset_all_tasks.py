"""
Reset all tasks - Clean database, Redis queues, and file uploads
"""
import asyncio
import asyncpg
import redis
import shutil
import sys
import os
from pathlib import Path

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    os.system("chcp 65001 > nul")

# Database config
DB_HOST = "192.168.1.33"
DB_PORT = 5432
DB_USER = "postgres"
DB_PASSWORD = "postgres"
DB_NAME = "multi_agent_db"

# Redis config
REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_DB = 0


async def reset_database():
    """Truncate all task-related tables"""
    print("\n[1/3] Cleaning Database...")

    try:
        conn = await asyncpg.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            database=DB_NAME
        )

        try:
            # Truncate all tables (CASCADE to handle foreign keys)
            await conn.execute("TRUNCATE TABLE tasks CASCADE;")
            print("  [OK] Truncated 'tasks' table")

            await conn.execute("TRUNCATE TABLE subtask_results CASCADE;")
            print("  [OK] Truncated 'subtask_results' table")

            await conn.execute("TRUNCATE TABLE agent_logs CASCADE;")
            print("  [OK] Truncated 'agent_logs' table")

            # Verify clean
            tasks_count = await conn.fetchval("SELECT COUNT(*) FROM tasks")
            results_count = await conn.fetchval("SELECT COUNT(*) FROM subtask_results")
            logs_count = await conn.fetchval("SELECT COUNT(*) FROM agent_logs")

            print(f"\n  [VERIFY] Tasks={tasks_count}, Results={results_count}, Logs={logs_count}")

        finally:
            await conn.close()

        return True

    except Exception as e:
        print(f"  [ERROR] Database error: {e}")
        return False


def reset_redis():
    """Flush all Redis queues"""
    print("\n[2/3] Cleaning Redis...")

    try:
        r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)

        # Flush entire database (all keys)
        r.flushdb()
        print("  [OK] Flushed Redis database")

        # Verify
        key_count = r.dbsize()
        print(f"  [VERIFY] {key_count} keys remaining")

        return True

    except Exception as e:
        print(f"  [ERROR] Redis error: {e}")
        return False


def reset_file_storage():
    """Delete all uploaded files and results"""
    print("\n[3/3] Cleaning File Storage...")

    artifacts_dir = Path("artifacts")

    # Delete entire artifacts folder
    if artifacts_dir.exists():
        try:
            shutil.rmtree(artifacts_dir)
            print(f"  [OK] Deleted artifacts/ directory")

            # Recreate structure
            artifacts_dir.mkdir(parents=True, exist_ok=True)
            (artifacts_dir / "results").mkdir(exist_ok=True)
            (artifacts_dir / "uploads").mkdir(exist_ok=True)
            (artifacts_dir / "reports").mkdir(exist_ok=True)
            (artifacts_dir / "data").mkdir(exist_ok=True)
            (artifacts_dir / "images").mkdir(exist_ok=True)
            (artifacts_dir / "temp").mkdir(exist_ok=True)
            print(f"  [OK] Recreated artifacts/ structure")

        except Exception as e:
            print(f"  [ERROR] Error cleaning artifacts/: {e}")
            return False
    else:
        print(f"  [INFO] No artifacts/ directory found")

    return True


async def main():
    print("=" * 70)
    print("RESET ALL TASKS - Complete System Cleanup")
    print("=" * 70)
    print("\nThis will permanently delete:")
    print("  - All tasks from database")
    print("  - All subtask results")
    print("  - All agent logs")
    print("  - All Redis queues and agent data")
    print("  - All uploaded files")
    print("  - All HTML results")

    print("\n" + "WARNING: This action CANNOT be undone!".center(70))

    # Confirmation
    response = input("\nType 'YES' to confirm reset: ")
    if response != "YES":
        print("\n[CANCELLED] Reset cancelled")
        return

    print("\n" + "=" * 70)
    print("Starting cleanup...")

    # Execute cleanup steps
    db_success = await reset_database()
    redis_success = reset_redis()
    files_success = reset_file_storage()

    # Summary
    print("\n" + "=" * 70)

    if db_success and redis_success and files_success:
        print("[SUCCESS] All systems cleaned!")
        print("=" * 70)
        print("\nSummary:")
        print("  - Database: CLEAN")
        print("  - Redis: CLEAN")
        print("  - File Storage: CLEAN")
        print("\nSystem is ready for fresh tasks!")
    else:
        print("[PARTIAL] Some steps failed")
        print("=" * 70)
        print("\nSummary:")
        print(f"  - Database: {'CLEAN' if db_success else 'FAILED'}")
        print(f"  - Redis: {'CLEAN' if redis_success else 'FAILED'}")
        print(f"  - File Storage: {'CLEAN' if files_success else 'FAILED'}")
        print("\nPlease check errors above")


if __name__ == "__main__":
    asyncio.run(main())
