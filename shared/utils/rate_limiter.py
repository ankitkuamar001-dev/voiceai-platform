import time
from fastapi import Request, HTTPException, Depends
from shared.utils.database import get_redis
from redis.asyncio import Redis


class RateLimiter:
    def __init__(self, requests: int = 100, window: int = 60):
        self.requests = requests
        self.window = window

    async def __call__(self, request: Request, redis: Redis = Depends(get_redis)):
        if not redis:
            # If redis is unavailable, we can either pass or fail. Let's pass for resilience.
            return True

        client_ip = request.client.host
        key = f"rate_limit:{client_ip}"

        now = time.time()
        pipeline = redis.pipeline()

        # Remove old requests
        pipeline.zremrangebyscore(key, 0, now - self.window)
        # Add current request
        pipeline.zadd(key, {str(now): now})
        # Count requests
        pipeline.zcard(key)
        # Set expiry for the key
        pipeline.expire(key, self.window)

        results = await pipeline.execute()
        request_count = results[2]

        if request_count > self.requests:
            raise HTTPException(status_code=429, detail="Too Many Requests")

        return True


rate_limiter = RateLimiter()
