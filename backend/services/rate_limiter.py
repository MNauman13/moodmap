"""
Redis sliding-window rate limiter.
Uses the existing Redis instance (same one as Celery broker).
"""
import time
import os
import redis
from fastapi import HTTPException, status

_redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
_pool = redis.ConnectionPool.from_url(_redis_url, decode_responses=True)


def _client() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


def check_rate_limit(key: str, max_requests: int, window_seconds: int) -> None:
    """
    Sliding-window rate limit using a Redis sorted set.
    Raises HTTP 429 if the limit is exceeded.

    key: unique identifier (e.g. "rl:journal_create:user_id")
    max_requests: allowed requests in the window
    window_seconds: rolling window duration in seconds
    """
    r = _client()
    now = time.time()
    window_start = now - window_seconds

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)   # drop expired entries
    pipe.zadd(key, {str(now): now})               # record this request
    pipe.zcard(key)                               # count requests in window
    pipe.expire(key, window_seconds + 1)          # auto-clean key
    results = pipe.execute()

    count = results[2]
    if count > max_requests:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Max {max_requests} requests per {window_seconds}s.",
            headers={"Retry-After": str(window_seconds)},
        )
