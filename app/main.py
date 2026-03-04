from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from app.core.redis_client import get_redis, close_redis
from app.core.config import settings
from app.routers import cache, news


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup — verify Redis connection
    try:
        r = await get_redis()
        await r.ping()
        print("Redis connected successfully")
    except Exception as e:
        print(f"Redis connection failed: {e}")
        # non-fatal — server starts but cache endpoints will fail
    yield
    # shutdown
    await close_redis()
    print("Redis connection closed")


app = FastAPI(
    title="Redis Cache Service",
    description="Cache layer demonstrating cache-aside, TTL, LRU eviction, stampede protection, and invalidation patterns.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Global exception handler ─────────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    if settings.debug:
        return JSONResponse(
            {"code": 500, "message": str(exc), "data": None},
            status_code=500,
        )
    return JSONResponse(
        {"code": 500, "message": "Internal server error.", "data": None},
        status_code=500,
    )


# ── Routers ─────────────────────────────────────────────────────────────────
app.include_router(cache.router)
app.include_router(news.router)


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"])
async def health():
    try:
        r = await get_redis()
        await r.ping()
        redis_ok = True
    except Exception:
        redis_ok = False
    return {"status": "ok", "redis": redis_ok}
