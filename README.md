# Redis Cache Service

A production-pattern cache layer built with **FastAPI** and **Redis**, demonstrating the core caching concepts used in real backend systems.

```
┌──────────────┐   cache hit (< 1ms)   ┌───────────────┐
│              │ ◄──────────────────── │               │
│   Client     │                       │  Redis (LRU)  │
│              │ ──── cache miss ────► │               │
└──────────────┘         │             └───────────────┘
                         │ fetch
                         ▼
                  ┌─────────────┐
                  │  Database   │  (~50ms simulated)
                  └─────────────┘
```

## Core Concepts Demonstrated

| Concept | Implementation |
|---------|---------------|
| **Cache-aside** | Read from cache first; on miss, fetch DB, write to cache |
| **TTL management** | News: 60s · Categories: 600s · Generic: 300s |
| **LRU eviction** | Redis `maxmemory-policy allkeys-lru` (256MB cap) |
| **Cache invalidation** | DELETE on write — ensures cache never serves stale data |
| **Stampede protection** | Mutex lock on cache miss — only one request rebuilds, others wait |
| **Hit rate tracking** | `/cache/stats` — hits, misses, hit rate |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/yourname/redis-cache-service.git
cd redis-cache-service

# 2. Start Redis + API with Docker Compose
docker compose up --build

# 3. Open API docs
# http://localhost:8001/docs
```

No local Redis or Python install needed — Docker handles everything.

## API Reference

### Generic Cache

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/cache/get/{key}` | Get cached value |
| POST | `/cache/set` | Set value with TTL |
| DELETE | `/cache/delete/{key}` | Invalidate single key |
| DELETE | `/cache/flush/{pattern}` | Invalidate by glob pattern |
| GET | `/cache/stats` | Hit/miss statistics |
| POST | `/cache/stats/reset` | Reset counters |

### News Cache (Demo)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/news/{id}` | Get article (cache-aside + stampede lock) |
| GET | `/news/list/{category_id}` | Get paginated list |
| POST | `/news/{id}/invalidate` | Invalidate article + related lists |
| POST | `/news/flush-all` | Clear all news cache |

### Health

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Service + Redis status |

## Cache Patterns Explained

### Cache-Aside
```
read(key):
  value = redis.get(key)
  if value is None:           # cache miss
    value = db.fetch(key)
    redis.setex(key, ttl, value)
  return value
```
The application manages the cache. DB is the source of truth. Cache is populated lazily on first read.

### Cache Invalidation
```
write(key, new_value):
  db.update(key, new_value)
  redis.delete(key)           # invalidate — next read rebuilds
```
Delete on write ensures the cache never serves stale data after an update.

### Stampede Protection
```
on cache miss:
  acquired = redis.set(lock_key, 1, nx=True, ex=10)
  if acquired:
    value = db.fetch()        # only ONE request hits DB
    redis.setex(key, ttl, value)
    redis.delete(lock_key)
  else:
    sleep(100ms)              # others wait
    retry()                   # then read from cache
```
Without this, 1000 simultaneous requests on a cold cache all hit the DB at once.

### LRU Eviction
Redis is configured with `maxmemory 256mb` and `maxmemory-policy allkeys-lru`. When memory is full, Redis automatically evicts the **Least Recently Used** keys — the cache self-manages without manual cleanup.

## Performance Demo

```bash
# First request — cache miss (~50ms DB latency)
curl http://localhost:8001/news/1
# → { "cache": "miss", ... }

# Second request — cache hit (< 1ms Redis)
curl http://localhost:8001/news/1
# → { "cache": "hit", ... }

# Check stats after a few requests
curl http://localhost:8001/cache/stats
# → { "hits": 5, "misses": 2, "hit_rate": 0.714 }
```

## Project Structure

```
├── app/
│   ├── main.py                 # FastAPI app + lifespan
│   ├── core/
│   │   ├── config.py           # Settings (TTL, Redis URL)
│   │   ├── redis_client.py     # Cache ops + stampede lock + stats
│   │   └── response.py         # Unified { code, message, data }
│   ├── routers/
│   │   ├── cache.py            # Generic cache CRUD endpoints
│   │   └── news.py             # News cache demo endpoints
│   └── models/
│       └── schemas.py          # Pydantic schemas
├── docker-compose.yml          # Redis + API services
├── Dockerfile
├── requirements.txt
├── test_main.http
└── .env.example
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection string |
| `DEFAULT_TTL` | `300` | Default cache TTL in seconds |
| `NEWS_TTL` | `60` | TTL for news articles (changes often) |
| `CATEGORY_TTL` | `600` | TTL for categories (rarely changes) |
| `DEBUG` | `false` | Expose error details in responses |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, Python 3.11 |
| Cache | Redis 7 (alpine), redis-py async |
| Container | Docker, Docker Compose |
| Validation | Pydantic v2 |
