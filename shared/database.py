"""
Database manager for PostgreSQL operations.
Handles connection pooling and all database interactions.
"""
import asyncpg
import json
from typing import Optional, List
from datetime import datetime

from shared.models import Task, SubTaskResult, TaskStatus, AdministrativeDivision, DivisionQueryRequest, DivisionQueryResult
from shared.config import settings


class DatabaseManager:
    """Manages PostgreSQL connection pool and database operations"""

    def __init__(self):
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self):
        """Create connection pool"""
        self.pool = await asyncpg.create_pool(
            settings.POSTGRES_URL,
            min_size=2,
            max_size=20,
            command_timeout=60
        )
        print(f"[DatabaseManager] Connected to PostgreSQL")

    async def disconnect(self):
        """Close connection pool"""
        if self.pool:
            await self.pool.close()
            print(f"[DatabaseManager] Disconnected from PostgreSQL")

    async def create_task(self, task: Task) -> Task:
        """Insert new task into database"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO tasks (id, user_id, description, created_at, updated_at, status, subtasks, result, error, attachments, uploads_folder)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                """,
                task.id,
                task.user_id,
                task.description,
                task.created_at,
                task.updated_at,
                task.status.value,
                json.dumps([st.model_dump() for st in task.subtasks]) if task.subtasks else None,
                json.dumps(task.result) if task.result else None,
                task.error,
                json.dumps([att.model_dump(mode='python') for att in task.attachments]) if task.attachments else None,
                task.uploads_folder
            )
        return task

    async def get_task(self, task_id: str) -> Optional[Task]:
        """Retrieve task by ID"""
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM tasks WHERE id = $1",
                task_id
            )

            if not row:
                return None

            # Parse JSONB fields
            subtasks = None
            if row['subtasks']:
                from shared.models import SubTask
                # Handle both string and already-parsed JSON
                subtasks_data = row['subtasks']
                if isinstance(subtasks_data, str):
                    subtasks_data = json.loads(subtasks_data)
                subtasks = [SubTask(**st) for st in subtasks_data]

            # Parse result field
            result = row['result']
            if isinstance(result, str):
                result = json.loads(result) if result else None

            # Parse attachments field
            attachments = []
            if row.get('attachments'):
                from shared.models import FileAttachment
                attachments_data = row['attachments']
                if isinstance(attachments_data, str):
                    attachments_data = json.loads(attachments_data)
                attachments = [FileAttachment(**att) for att in attachments_data]

            return Task(
                id=row['id'],
                user_id=row['user_id'],
                description=row['description'],
                created_at=row['created_at'],
                updated_at=row['updated_at'],
                status=TaskStatus(row['status']),
                subtasks=subtasks,
                result=result,
                error=row['error'],
                attachments=attachments,
                uploads_folder=row.get('uploads_folder')
            )

    async def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[dict] = None,
        error: Optional[str] = None
    ):
        """Update task status and optionally set result or error"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE tasks
                SET status = $1, result = $2, error = $3, updated_at = $4
                WHERE id = $5
                """,
                status.value,
                json.dumps(result) if result else None,
                error,
                datetime.utcnow(),
                task_id
            )

    async def save_subtask_result(self, result: SubTaskResult):
        """Insert subtask result into database"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO subtask_results
                (task_id, subtask_id, agent_id, status, output, error, execution_time, created_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                result.task_id,
                result.subtask_id,
                result.agent_id,
                result.status.value,
                json.dumps(result.output) if result.output else None,
                result.error,
                result.execution_time,
                result.created_at
            )

    async def get_subtask_results(self, task_id: str) -> List[SubTaskResult]:
        """Get all subtask results for a task"""
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM subtask_results
                WHERE task_id = $1
                ORDER BY created_at ASC
                """,
                task_id
            )

            results = []
            for row in rows:
                # Parse output if it's a string
                output = row['output']
                if isinstance(output, str):
                    try:
                        output = json.loads(output)
                    except (json.JSONDecodeError, TypeError):
                        pass  # Keep as string if not valid JSON

                results.append(SubTaskResult(
                    task_id=row['task_id'],
                    subtask_id=row['subtask_id'],
                    agent_id=row['agent_id'],
                    status=TaskStatus(row['status']),
                    output=output,
                    error=row['error'],
                    execution_time=row['execution_time'],
                    created_at=row['created_at']
                ))

            return results

    async def log_agent_activity(
        self,
        agent_id: str,
        task_id: Optional[str],
        level: str,
        message: str,
        metadata: Optional[dict] = None
    ):
        """Log agent activity to database"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO agent_logs (agent_id, task_id, log_level, message, metadata, created_at)
                VALUES ($1, $2, $3, $4, $5, $6)
                """,
                agent_id,
                task_id,
                level,
                message,
                json.dumps(metadata) if metadata else None,
                datetime.utcnow()
            )

    async def get_recent_logs(
        self,
        agent_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> List[dict]:
        """Get recent agent logs with optional filtering"""
        async with self.pool.acquire() as conn:
            query = "SELECT * FROM agent_logs WHERE 1=1"
            params = []
            param_num = 1

            if agent_id:
                query += f" AND agent_id = ${param_num}"
                params.append(agent_id)
                param_num += 1

            if task_id:
                query += f" AND task_id = ${param_num}"
                params.append(task_id)
                param_num += 1

            query += f" ORDER BY created_at DESC LIMIT ${param_num}"
            params.append(limit)

            rows = await conn.fetch(query, *params)

            return [
                {
                    "id": row['id'],
                    "agent_id": row['agent_id'],
                    "task_id": row['task_id'],
                    "log_level": row['log_level'],
                    "message": row['message'],
                    "metadata": row['metadata'],
                    "created_at": row['created_at']
                }
                for row in rows
            ]

    async def create_administrative_division(self, division: AdministrativeDivision) -> AdministrativeDivision:
        """Insert new administrative division into database"""
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO administrative_divisions
                (id, name, name_local, type, iso_code, parent_id, level, population, area_km2,
                 capital, timezone, latitude, longitude, bbox_north, bbox_south, bbox_east, bbox_west,
                 metadata, created_at, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
                """,
                division.id, division.name, division.name_local, division.type, division.iso_code,
                division.parent_id, division.level, division.population, division.area_km2,
                division.capital, division.timezone, division.latitude, division.longitude,
                division.bbox_north, division.bbox_south, division.bbox_east, division.bbox_west,
                json.dumps(division.metadata), division.created_at, division.updated_at
            )
        return division

    async def query_administrative_divisions(self, request: DivisionQueryRequest) -> DivisionQueryResult:
        """Query administrative divisions based on request parameters"""
        start_time = datetime.utcnow()

        async with self.pool.acquire() as conn:
            # Build query based on request type
            base_query = "SELECT * FROM administrative_divisions WHERE 1=1"
            params = []
            param_num = 1

            if request.query_type == "by_name" and request.search_term:
                base_query += f" AND (name ILIKE ${param_num} OR name_local ILIKE ${param_num})"
                params.append(f"%{request.search_term}%")
                param_num += 1

            elif request.query_type == "by_code" and request.iso_code:
                base_query += f" AND iso_code = ${param_num}"
                params.append(request.iso_code)
                param_num += 1

            elif request.query_type == "by_parent" and request.parent_id:
                base_query += f" AND parent_id = ${param_num}"
                params.append(request.parent_id)
                param_num += 1

            elif request.query_type == "by_level" and request.level is not None:
                base_query += f" AND level = ${param_num}"
                params.append(request.level)
                param_num += 1

            elif request.query_type == "nearby" and request.latitude and request.longitude:
                # Calculate distance using Haversine formula approximation
                radius_km = request.radius_km or 100
                lat_range = radius_km / 111.0  # Approximate km per degree of latitude
                lon_range = radius_km / (111.0 * abs(request.latitude) * 0.017453)  # Adjust for latitude

                base_query += f"""
                    AND latitude IS NOT NULL AND longitude IS NOT NULL
                    AND latitude BETWEEN ${param_num} AND ${param_num + 1}
                    AND longitude BETWEEN ${param_num + 2} AND ${param_num + 3}
                """
                params.extend([
                    request.latitude - lat_range, request.latitude + lat_range,
                    request.longitude - lon_range, request.longitude + lon_range
                ])
                param_num += 4

            # Add level filter if specified
            if request.level is not None and request.query_type != "by_level":
                base_query += f" AND level = ${param_num}"
                params.append(request.level)
                param_num += 1

            # Add ordering and limit
            base_query += f" ORDER BY name LIMIT ${param_num}"
            params.append(request.limit)

            # Execute query
            rows = await conn.fetch(base_query, *params)

            # Get total count (without limit)
            count_query = base_query.replace(f"ORDER BY name LIMIT ${param_num}", "")
            count_params = params[:-1]  # Remove limit parameter
            total_count = await conn.fetchval(f"SELECT COUNT(*) FROM ({count_query}) AS count_query", *count_params)

            # Convert rows to AdministrativeDivision objects
            divisions = []
            for row in rows:
                metadata = row['metadata']
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)

                division = AdministrativeDivision(
                    id=row['id'],
                    name=row['name'],
                    name_local=row['name_local'],
                    type=row['type'],
                    iso_code=row['iso_code'],
                    parent_id=row['parent_id'],
                    level=row['level'],
                    population=row['population'],
                    area_km2=float(row['area_km2']) if row['area_km2'] else None,
                    capital=row['capital'],
                    timezone=row['timezone'],
                    latitude=float(row['latitude']) if row['latitude'] else None,
                    longitude=float(row['longitude']) if row['longitude'] else None,
                    bbox_north=float(row['bbox_north']) if row['bbox_north'] else None,
                    bbox_south=float(row['bbox_south']) if row['bbox_south'] else None,
                    bbox_east=float(row['bbox_east']) if row['bbox_east'] else None,
                    bbox_west=float(row['bbox_west']) if row['bbox_west'] else None,
                    metadata=metadata,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                divisions.append(division)

        end_time = datetime.utcnow()
        query_time_ms = (end_time - start_time).total_seconds() * 1000

        return DivisionQueryResult(
            divisions=divisions,
            total_count=total_count,
            query_time_ms=query_time_ms,
            source="database",
            metadata={"query_type": request.query_type, "params_used": len(params)}
        )

    async def get_division_hierarchy(self, division_id: str) -> List[AdministrativeDivision]:
        """Get complete hierarchy for a division (from root to division)"""
        async with self.pool.acquire() as conn:
            # Use recursive CTE to get hierarchy
            hierarchy_query = """
            WITH RECURSIVE division_hierarchy AS (
                -- Base case: find the root (no parent)
                SELECT *, 0 as depth
                FROM administrative_divisions
                WHERE id = $1

                UNION ALL

                -- Recursive case: find parent
                SELECT ad.*, dh.depth + 1
                FROM administrative_divisions ad
                INNER JOIN division_hierarchy dh ON ad.id = dh.parent_id
            )
            SELECT * FROM division_hierarchy ORDER BY depth DESC
            """

            rows = await conn.fetch(hierarchy_query, division_id)

            divisions = []
            for row in rows:
                metadata = row['metadata']
                if isinstance(metadata, str):
                    metadata = json.loads(metadata)

                division = AdministrativeDivision(
                    id=row['id'],
                    name=row['name'],
                    name_local=row['name_local'],
                    type=row['type'],
                    iso_code=row['iso_code'],
                    parent_id=row['parent_id'],
                    level=row['level'],
                    population=row['population'],
                    area_km2=float(row['area_km2']) if row['area_km2'] else None,
                    capital=row['capital'],
                    timezone=row['timezone'],
                    latitude=float(row['latitude']) if row['latitude'] else None,
                    longitude=float(row['longitude']) if row['longitude'] else None,
                    bbox_north=float(row['bbox_north']) if row['bbox_north'] else None,
                    bbox_south=float(row['bbox_south']) if row['bbox_south'] else None,
                    bbox_east=float(row['bbox_east']) if row['bbox_east'] else None,
                    bbox_west=float(row['bbox_west']) if row['bbox_west'] else None,
                    metadata=metadata,
                    created_at=row['created_at'],
                    updated_at=row['updated_at']
                )
                divisions.append(division)

            return divisions


# Singleton instance
db_manager = DatabaseManager()
