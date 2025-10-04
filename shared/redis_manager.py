"""
Redis manager for message queues and agent coordination.
Handles task queues, result queues, and agent status tracking.
"""
import redis.asyncio as redis
import json
from typing import Optional, List
from datetime import datetime

from shared.models import SubTask, SubTaskResult, AgentStatus, AgentCapability
from shared.config import settings


class RedisManager:
    """Manages Redis connection and queue operations"""

    def __init__(self):
        self.client: Optional[redis.Redis] = None

    async def connect(self):
        """Create Redis connection"""
        self.client = await redis.from_url(settings.REDIS_URL)
        print(f"[RedisManager] Connected to Redis")

    async def disconnect(self):
        """Close Redis connection"""
        if self.client:
            await self.client.aclose()
            print(f"[RedisManager] Disconnected from Redis")

    async def enqueue_task(
        self,
        task_id: str,
        subtask: SubTask,
        context: dict
    ):
        """Enqueue subtask to agent_tasks queue"""
        task_data = {
            "task_id": task_id,
            "subtask": subtask.model_dump(),
            "context": context
        }
        await self.client.rpush("agent_tasks", json.dumps(task_data))

    async def dequeue_task(self, timeout: int = 5) -> Optional[dict]:
        """Dequeue subtask from agent_tasks queue (blocking)"""
        result = await self.client.blpop("agent_tasks", timeout=timeout)
        if result:
            _, data = result
            return json.loads(data)
        return None

    async def enqueue_result(self, result: SubTaskResult):
        """Enqueue result to agent_results queue"""
        # Use mode='python' to keep dicts as dicts, not JSON strings
        result_data = result.model_dump(mode='python')
        # Convert datetime to ISO string for JSON
        result_data['created_at'] = result_data['created_at'].isoformat()
        result_data['status'] = result_data['status'].value if hasattr(result_data['status'], 'value') else result_data['status']
        await self.client.rpush("agent_results", json.dumps(result_data))

    async def dequeue_result(self, timeout: int = 5) -> Optional[SubTaskResult]:
        """Dequeue result from agent_results queue (blocking)"""
        result = await self.client.blpop("agent_results", timeout=timeout)
        if result:
            _, data = result
            result_data = json.loads(data)
            # Parse datetime back from ISO string
            result_data['created_at'] = datetime.fromisoformat(result_data['created_at'])
            # Parse output if it's a JSON string
            if isinstance(result_data.get('output'), str):
                try:
                    result_data['output'] = json.loads(result_data['output'])
                except (json.JSONDecodeError, TypeError):
                    pass  # Keep as string if not valid JSON
            return SubTaskResult(**result_data)
        return None

    async def register_agent(self, agent_id: str):
        """Register agent in active_agents set"""
        await self.client.sadd("active_agents", agent_id)

    async def update_agent_status(self, agent_status: AgentStatus):
        """Update agent status in Redis with TTL"""
        key = f"agent:{agent_status.agent_id}"

        # Convert status to dict
        status_dict = {
            "agent_id": agent_status.agent_id,
            "port": str(agent_status.port),
            "is_available": "true" if agent_status.is_available else "false",
            "current_task": agent_status.current_task or "",
            "capabilities": ",".join([cap.value for cap in agent_status.capabilities]),
            "cpu_usage": str(agent_status.cpu_usage),
            "memory_usage": str(agent_status.memory_usage),
            "tasks_completed": str(agent_status.tasks_completed),
            "last_heartbeat": agent_status.last_heartbeat.isoformat()
        }

        # Set all fields and TTL
        await self.client.hset(key, mapping=status_dict)
        await self.client.expire(key, 60)  # 60 second TTL

    async def get_available_agents(
        self,
        capability: Optional[AgentCapability] = None
    ) -> List[str]:
        """Get list of available agents, optionally filtered by capability"""
        # Get all active agents
        active_agents = await self.client.smembers("active_agents")

        available = []
        for agent_id in active_agents:
            agent_id_str = agent_id.decode() if isinstance(agent_id, bytes) else agent_id
            key = f"agent:{agent_id_str}"

            # Check if agent exists (not expired)
            exists = await self.client.exists(key)
            if not exists:
                # Remove from active set if expired
                await self.client.srem("active_agents", agent_id_str)
                continue

            # Get agent status
            status = await self.client.hgetall(key)
            if not status:
                continue

            # Decode bytes to strings
            status_dict = {
                k.decode() if isinstance(k, bytes) else k:
                v.decode() if isinstance(v, bytes) else v
                for k, v in status.items()
            }

            # Check if available
            is_available = status_dict.get("is_available", "false") == "true"
            if not is_available:
                continue

            # Check capability if specified
            if capability:
                caps_str = status_dict.get("capabilities", "")
                agent_caps = caps_str.split(",")
                if capability.value not in agent_caps:
                    continue

            available.append(agent_id_str)

        return available

    async def get_agent_status(self, agent_id: str) -> Optional[AgentStatus]:
        """Get full agent status from Redis"""
        key = f"agent:{agent_id}"
        status = await self.client.hgetall(key)

        if not status:
            return None

        # Decode bytes to strings
        status_dict = {
            k.decode() if isinstance(k, bytes) else k:
            v.decode() if isinstance(v, bytes) else v
            for k, v in status.items()
        }

        # Parse capabilities
        caps_str = status_dict.get("capabilities", "")
        capabilities = [AgentCapability(cap) for cap in caps_str.split(",") if cap]

        return AgentStatus(
            agent_id=status_dict["agent_id"],
            port=int(status_dict["port"]),
            is_available=status_dict["is_available"] == "true",
            current_task=status_dict["current_task"] if status_dict["current_task"] else None,
            capabilities=capabilities,
            cpu_usage=float(status_dict.get("cpu_usage", 0)),
            memory_usage=float(status_dict.get("memory_usage", 0)),
            tasks_completed=int(status_dict.get("tasks_completed", 0)),
            last_heartbeat=datetime.fromisoformat(status_dict["last_heartbeat"])
        )

    async def get_all_agents(self) -> List[AgentStatus]:
        """Get status of all active agents"""
        active_agents = await self.client.smembers("active_agents")
        agents = []

        for agent_id in active_agents:
            agent_id_str = agent_id.decode() if isinstance(agent_id, bytes) else agent_id
            status = await self.get_agent_status(agent_id_str)
            if status:
                agents.append(status)

        return agents

    async def set(self, key: str, value: str, expire: Optional[int] = None):
        """Set a key-value pair with optional expiration"""
        await self.client.set(key, value, ex=expire)

    async def get(self, key: str) -> Optional[str]:
        """Get value by key"""
        result = await self.client.get(key)
        return result.decode() if result else None

    @property
    def redis(self):
        """Property to access the Redis client (for compatibility)"""
        return self.client


# Singleton instance
redis_manager = RedisManager()
