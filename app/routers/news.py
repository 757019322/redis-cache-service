import random
from datetime import datetime
from fastapi import APIRouter
from app.core.redis_client import get_with_lock, cache_delete_pattern, incr_stat
from app.core.response import ok
from app.core.config import settings

router = APIRouter(prefix="/news", tags=["News Cache"])


# ── Simulated DB fetch ────────────────────────────────────────────────────────
# In production this would call the actual MySQL news platform.
# Here we simulate DB latency to demonstrate cache performance clearly.

async def _fetch_article_from_db(news_id: int) -> dict:
    """Simulate a slow DB query (50ms latency)."""
    import asyncio
    await asyncio.sleep(0.05)   # 50ms simulated DB latency
    return {
        "id": news_id,
        "title": f"Article {news_id}: The Future of AI in 2026",
        "description": "A deep dive into how artificial intelligence is reshaping industries worldwide.",
        "category_id": random.choice([1, 2, 3]),
        "views": random.randint(100, 10000),
        "publish_time": datetime.utcnow().isoformat(),
        "source": "simulated_db",
    }


async def _fetch_list_from_db(category_id: int, page: int) -> dict:
    """Simulate fetching a paginated list from DB."""
    import asyncio
    await asyncio.sleep(0.08)   # 80ms simulated DB latency
    articles = [
        {
            "id": (page - 1) * 10 + i,
            "title": f"[Cat {category_id}] Article {i}",
            "category_id": category_id,
            "publish_time": datetime.utcnow().isoformat(),
        }
        for i in range(1, 11)
    ]
    return {"list": articles, "total": 100, "page": page, "category_id": category_id}


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/{news_id}")
async def get_news(news_id: int):
    """
    Cache-aside pattern with stampede protection:
    1. Check Redis cache
    2. Cache hit  → return immediately (fast)
    3. Cache miss → acquire lock → fetch DB → store in cache → return
    """
    cache_key = f"news:{news_id}"

    data, status = await get_with_lock(
        key=cache_key,
        ttl=settings.news_ttl,
        fetch_fn=lambda: _fetch_article_from_db(news_id),
    )

    # track hit/miss stats
    await incr_stat("hits" if status == "hit" else "misses")

    return ok(data, cache_status=status)


@router.get("/list/{category_id}")
async def get_news_list(category_id: int, page: int = 1):
    """
    Cache list by category + page.
    Key: 'list:cat:{category_id}:page:{page}'
    TTL: news_ttl (shorter — lists change as new articles arrive)
    """
    cache_key = f"list:cat:{category_id}:page:{page}"

    data, status = await get_with_lock(
        key=cache_key,
        ttl=settings.news_ttl,
        fetch_fn=lambda: _fetch_list_from_db(category_id, page),
    )

    await incr_stat("hits" if status == "hit" else "misses")
    return ok(data, cache_status=status)


@router.post("/{news_id}/invalidate")
async def invalidate_news(news_id: int):
    """
    Cache invalidation — called when an article is updated or deleted.
    Deletes article cache + all list caches (since lists may include this article).

    This is the 'write-through invalidation' pattern:
    On write → delete cache → next read rebuilds from DB.
    """
    count = await cache_delete_pattern(f"news:{news_id}")
    lists = await cache_delete_pattern("list:cat:*")
    return ok(
        {"article_keys_deleted": count, "list_keys_deleted": lists},
        message=f"Cache invalidated for article {news_id}",
    )


@router.post("/flush-all")
async def flush_all_news():
    """Flush all news and list caches. Use after bulk data updates."""
    n1 = await cache_delete_pattern("news:*")
    n2 = await cache_delete_pattern("list:*")
    return ok({"deleted": n1 + n2}, message="All news cache cleared")
