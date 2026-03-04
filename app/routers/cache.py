from fastapi import APIRouter
from app.core.redis_client import cache_get, cache_set, cache_delete, cache_delete_pattern, get_stats, reset_stats
from app.core.response import ok, err
from app.models.schemas import CacheSetRequest
from app.core.config import settings

router = APIRouter(prefix="/cache", tags=["Cache"])


@router.get("/get/{key}")
async def get_key(key: str):
    """
    Get a cached value by key.
    Returns the value + hit/miss status.
    """
    value = await cache_get(key)
    if value is None:
        return err(f"Key '{key}' not found or expired", code=404)
    return ok({"key": key, "value": value}, cache_status="hit")


@router.post("/set")
async def set_key(body: CacheSetRequest):
    """
    Store any JSON value with a TTL.
    Key format recommended: 'namespace:id' e.g. 'news:42'
    """
    await cache_set(body.key, body.value, body.ttl)
    return ok({"key": body.key, "ttl": body.ttl}, message="Cached successfully")


@router.delete("/delete/{key}")
async def delete_key(key: str):
    """
    Invalidate a single cache key.
    Used when underlying data changes (write-through invalidation).
    """
    deleted = await cache_delete(key)
    if not deleted:
        return err(f"Key '{key}' not found", code=404)
    return ok({"key": key}, message="Cache invalidated")


@router.delete("/flush/{pattern}")
async def flush_pattern(pattern: str):
    """
    Invalidate all keys matching a glob pattern.
    Examples:
      - 'news:*'      → all news article caches
      - 'list:cat:*'  → all category list caches
    Warning: use carefully — scans all keys.
    """
    count = await cache_delete_pattern(pattern)
    return ok({"pattern": pattern, "deleted": count}, message=f"Flushed {count} keys")


@router.get("/stats")
async def get_cache_stats():
    """
    Return hit/miss counts and hit rate.
    Hit rate = hits / (hits + misses).
    A healthy cache should have >80% hit rate in production.
    """
    stats = await get_stats()
    return ok(stats)


@router.post("/stats/reset")
async def reset_cache_stats():
    """Reset hit/miss counters to zero."""
    await reset_stats()
    return ok(message="Stats reset")
