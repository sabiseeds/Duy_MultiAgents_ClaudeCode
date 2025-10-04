import asyncio
import redis.asyncio as redis
import sys
import os

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    os.system("chcp 65001 > nul")

async def test_redis():
    # Connect to Redis
    client = await redis.from_url("redis://localhost:6379/0")

    try:
        # Test: Ping
        pong = await client.ping()
        print(f"[OK] Redis ping: {pong}")

        # Test: Set and get
        await client.set("test_key", "test_value")
        value = await client.get("test_key")
        print(f"[OK] Redis get: {value.decode()}")

        # Test: List operations (queue simulation)
        await client.rpush("test_queue", "item1", "item2")
        length = await client.llen("test_queue")
        print(f"[OK] Redis queue length: {length}")

        item = await client.lpop("test_queue")
        print(f"[OK] Redis dequeue: {item.decode()}")

        # Test: Hash operations (agent status simulation)
        await client.hset("agent:test", mapping={
            "agent_id": "agent_1",
            "is_available": "true",
            "cpu_usage": "25.5"
        })
        status = await client.hgetall("agent:test")
        print(f"[OK] Redis hash: {len(status)} fields stored")

        # Cleanup
        await client.delete("test_key", "test_queue", "agent:test")
        print("[OK] Cleanup successful")

        print("\n[SUCCESS] All Redis tests passed!")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_redis())
