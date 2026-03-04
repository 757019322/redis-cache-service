import json
import asyncio
import redis.asyncio as aioredis
from app.core.config import settings

# global Redis client — created once at startup
_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis


async def close_redis():
    global _redis
    if _redis:
        await _redis.aclose()
        _redis = None


# ── Cache-aside helpers ──────────────────────────────────────────────────────

async def cache_get(key: str) -> dict | list | None:
    """Return cached value or None on miss."""
    r = await get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: dict | list, ttl: int) -> None:
    """Store value as JSON with TTL (seconds)."""
    r = await get_redis()
    await r.setex(key, ttl, json.dumps(value, ensure_ascii=False))


async def cache_delete(key: str) -> bool:
    """Delete a single key. Returns True if key existed."""
    r = await get_redis()
    deleted = await r.delete(key)
    return deleted > 0


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching pattern (e.g. 'news:*'). Returns count deleted."""
    r = await get_redis()
    keys = await r.keys(pattern)
    if not keys:
        return 0
    return await r.delete(*keys)


# ── Cache stampede protection ────────────────────────────────────────────────
# When the cache is empty and many requests arrive simultaneously,
# only ONE request rebuilds the cache. Others wait briefly then retry.
# This prevents the "thundering herd" problem.

_LOCK_TTL = 10   # lock expires after 10s even if holder crashes

async def get_with_lock(key: str, ttl: int, fetch_fn):
    """
    Cache-aside with mutex lock to prevent stampede.

    1. Cache hit  → return cached value immediately
    2. Cache miss → try to acquire lock
       - Lock acquired → call fetch_fn(), cache result, release lock
       - Lock not acquired → wait 100ms, retry (another request is rebuilding)
    """
    r = await get_redis()
    lock_key = f"lock:{key}"

    for attempt in range(10):   # max 1 second wait (10 × 100ms)
        # check cache first
        cached = await cache_get(key)
        if cached is not None:
            return cached, "hit"

        # try to acquire lock — NX means "only set if not exists"
        acquired = await r.set(lock_key, "1", nx=True, ex=_LOCK_TTL)
        if acquired:
            try:
                data = await fetch_fn()
                if data is not None:
                    await cache_set(key, data, ttl)
                return data, "miss"
            finally:
                await r.delete(lock_key)
        else:
            # another coroutine holds the lock — wait and retry
            await asyncio.sleep(0.1)

    # fallback: return direct fetch without caching
    data = await fetch_fn()
    return data, "miss"


# ── Stats tracking ────────────────────────────────────────────────────────────

async def incr_stat(stat: str) -> None:
    """Increment a counter (hits or misses)."""
    r = await get_redis()
    await r.incr(f"stats:{stat}")


async def get_stats() -> dict:
    """Return hit/miss counts and computed hit rate."""
    r = await get_redis()
    hits   = int(await r.get("stats:hits")   or 0)
    misses = int(await r.get("stats:misses") or 0)
    total  = hits + misses
    return {
        "hits":     hits,
        "misses":   misses,
        "total":    total,
        "hit_rate": round(hits / total, 4) if total > 0 else 0.0,
    }


async def reset_stats() -> None:
    r = await get_redis()
    await r.delete("stats:hits", "stats:misses")
