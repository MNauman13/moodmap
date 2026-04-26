"""
Redis cache-aside helper.

Uses the same Redis instance as the Celery broker and rate limiter.
All values are JSON-serialised strings. A TTL of None means no expiry.
"""

import json
import os
from typing import Any, Optional

import redis

_redis_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
_pool = redis.ConnectionPool.from_url(_redis_url, decode_responses=True)


def _client() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


def cache_get(key: str) -> Optional[Any]:
    """Return the deserialised cached value, or None on miss / Redis error."""
    try:
        raw = _client().get(key)
        if raw is None:
            return None
        return json.loads(raw)
    except Exception:
        return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> None:
    """Serialise value to JSON and store with the given TTL. Silently swallows errors."""
    try:
        _client().setex(key, ttl_seconds, json.dumps(value))
    except Exception:
        pass


def cache_delete(key: str) -> None:
    """Delete a cache key. Silently swallows errors."""
    try:
        _client().delete(key)
    except Exception:
        pass


def cache_delete_pattern(pattern: str) -> None:
    """Delete all keys matching a glob pattern (e.g. 'insights:*'). Use sparingly."""
    try:
        r = _client()
        keys = r.keys(pattern)
        if keys:
            r.delete(*keys)
    except Exception:
        pass
