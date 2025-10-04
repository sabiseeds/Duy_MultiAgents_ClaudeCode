import asyncio
import redis.asyncio as redis

async def test_redis():
    # Connect to Redis
    client = await redis.from_url("redis://localhost:6379/0")

    try:
        # Test: Ping
        pong = await client.ping()
        print(f"✓ Redis ping: {pong}")

        # Test: Set and get
        await client.set("test_key", "test_value")
        value = await client.get("test_key")
        print(f"✓ Redis get: {value.decode()}")

        # Test: List operations (queue simulation)
        await client.rpush("test_queue", "item1", "item2")
        length = await client.llen("test_queue")
        print(f"✓ Redis queue length: {length}")

        item = await client.lpop("test_queue")
        print(f"✓ Redis dequeue: {item.decode()}")

        # Test: Hash operations (agent status simulation)
        await client.hset("agent:test", mapping={
            "agent_id": "agent_1",
            "is_available": "true",
            "cpu_usage": "25.5"
        })
        status = await client.hgetall("agent:test")
        print(f"✓ Redis hash: {len(status)} fields stored")

        # Cleanup
        await client.delete("test_key", "test_queue", "agent:test")
        print("✓ Cleanup successful")

        print("\n🎉 All Redis tests passed!")

    finally:
        await client.close()

if __name__ == "__main__":
    asyncio.run(test_redis())
