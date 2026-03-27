"""
Infrastructure — Shared Plumbing for the Supabase Service Package
================================================================
All domain modules import from here. Nothing in this file contains
business logic — only: imports, caches, Redis, circuit breaker, helpers, and decorators.

Changes here propagate to every module automatically.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from functools import wraps

import redis
from cachetools import TTLCache
from pybreaker import CircuitBreaker, CircuitBreakerError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import supabase, logger
from metrics import DB_QUERY_COUNT, CACHE_HITS, CACHE_MISSES


# ================================
# Return Type Enforcement Decorator
# ================================
def enforce_return(return_type):
    """Decorator that asserts the return value matches the annotated return type.

    Raises TypeError if the function returns None when a dict/list is annotated,
    or returns the wrong type. This prevents silent {} returns from propagating
    to the LLM when a Supabase query returns no rows.

    Usage:
        @enforce_return(dict)
        def get_post_context(post_id: str) -> dict:
            ...
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            if result is None:
                raise TypeError(
                    f"{func.__name__} returned None — expected {return_type.__name__}. "
                    f"This usually means a Supabase query returned no rows. "
                    f"Add an explicit 'if not result.data: return {{}}' check."
                )
            if not isinstance(result, return_type):
                raise TypeError(
                    f"{func.__name__} returned {type(result).__name__} — expected {return_type.__name__}"
                )
            return result
        return wrapper
    return decorator


# ================================
# Caches — L1 in-process (fastest)
# ================================
post_context_cache: TTLCache = TTLCache(maxsize=100, ttl=30)
account_info_cache: TTLCache = TTLCache(maxsize=50, ttl=60)
attribution_model_cache: TTLCache = TTLCache(maxsize=20, ttl=300)
# Fix #1: dedicated cache for analytics reports (5 min TTL — reports change daily at most)
analytics_cache: TTLCache = TTLCache(maxsize=20, ttl=300)


# ================================
# Redis — L2 distributed cache
# ================================
# TODO #8: Replace with redis.asyncio.Redis (available in redis>=5.0).
# redis==5.0.1 is already installed. The sync client blocks the event loop on every
# cache_get/cache_set call. Migrating to async Redis requires making cache_get/cache_set
# async and updating all their callers. This is a larger refactor (estimated ~2h) and
# should be done as a separate ticket.
REDIS_HOST = os.getenv("REDIS_HOST", "redis")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))

_redis: redis.Redis | None = None
_redis_available: bool = False

try:
    _redis = redis.Redis(
        host=REDIS_HOST,
        port=REDIS_PORT,
        decode_responses=True,
        socket_timeout=2,
    )
    _redis.ping()
    _redis_available = True
    logger.info(f"Redis connected at {REDIS_HOST}:{REDIS_PORT}")
except Exception:
    _redis = None
    _redis_available = False
    logger.warning("Redis unavailable — caching disabled, queries go direct to Supabase")


# ================================
# Redis helpers (L2 cache)
# ================================
def cache_get(key: str) -> dict | None:
    """Get value from Redis cache. Returns None on miss or Redis failure."""
    if not _redis_available:
        return None
    try:
        cached = _redis.get(key)
        return json.loads(cached) if cached else None
    except Exception:
        return None


def cache_set(key: str, data, ttl: int = 60) -> None:
    """Set value in Redis cache. Silently fails if Redis unavailable."""
    if not _redis_available:
        return
    try:
        _redis.setex(key, ttl, json.dumps(data, default=str))
    except Exception:
        pass


# ================================
# Circuit Breaker + Retry
# ================================
db_breaker = CircuitBreaker(fail_max=5, reset_timeout=30)


@db_breaker
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((ConnectionError, TimeoutError, OSError)),
    reraise=True,
)
def execute(query, *, table: str, operation: str):
    """Execute a Supabase query with retry + circuit breaker.

    - tenacity: 3 attempts, exponential backoff 0.5–4s
    - pybreaker: opens after 5 consecutive failures, fails fast for 30s
    - Tracks DB_QUERY_COUNT metric
    """
    DB_QUERY_COUNT.labels(table=table, operation=operation).inc()
    return query.execute()


# ================================
# Helpers
# ================================
def is_valid_uuid(value: str) -> bool:
    """Check if a string is a valid UUID."""
    if not value:
        return False
    try:
        uuid.UUID(str(value))
        return True
    except (ValueError, AttributeError):
        return False


def is_redis_healthy() -> bool:
    """Check Redis connectivity for health endpoint."""
    if not _redis:
        return False
    try:
        return _redis.ping()
    except Exception:
        return False
