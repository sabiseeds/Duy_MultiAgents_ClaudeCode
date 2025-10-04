"""
Database migration: Add file upload support to tasks table
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


async def migrate_database():
    """Add file upload columns to tasks table"""
    print("=" * 60)
    print("Database Migration: Add File Upload Support")
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
            print("Checking existing columns...")

            # Check if columns already exist
            existing_columns = await conn.fetch(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'tasks'
                """
            )
            existing_col_names = [row['column_name'] for row in existing_columns]

            print(f"[INFO] Current columns: {', '.join(existing_col_names)}")

            # Add attachments column if not exists
            if 'attachments' not in existing_col_names:
                print("\n[ACTION] Adding 'attachments' column...")
                await conn.execute(
                    """
                    ALTER TABLE tasks
                    ADD COLUMN attachments JSONB
                    """
                )
                print("[OK] Added 'attachments' column")
            else:
                print("[SKIP] 'attachments' column already exists")

            # Add uploads_folder column if not exists
            if 'uploads_folder' not in existing_col_names:
                print("\n[ACTION] Adding 'uploads_folder' column...")
                await conn.execute(
                    """
                    ALTER TABLE tasks
                    ADD COLUMN uploads_folder TEXT
                    """
                )
                print("[OK] Added 'uploads_folder' column")
            else:
                print("[SKIP] 'uploads_folder' column already exists")

            # Verify migration
            print("\n[VERIFY] Checking updated schema...")
            updated_columns = await conn.fetch(
                """
                SELECT column_name, data_type FROM information_schema.columns
                WHERE table_name = 'tasks'
                ORDER BY ordinal_position
                """
            )

            print("\n[SCHEMA] Tasks table columns:")
            for col in updated_columns:
                print(f"  - {col['column_name']}: {col['data_type']}")

            print("\n" + "=" * 60)
            print("[SUCCESS] Migration completed successfully!")
            print("=" * 60)

        finally:
            await conn.close()

    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(migrate_database())
