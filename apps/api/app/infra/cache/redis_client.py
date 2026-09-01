import os
from functools import lru_cache

_redis = None

def get_redis():
    global _redis
    if _redis is not None:
        return _redis
    url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis.asyncio as aioredis
        _redis = aioredis.from_url(url, decode_responses=True)
    except Exception as e:
        print(f"[redis] unavailable, using in-memory stub: {e}")
        _redis = _InMemRedis()
    return _redis

class _InMemRedis:
    def __init__(self): self.store={}
    async def get(self, k): return self.store.get(k)
    async def set(self, k, v, ex=None): self.store[k]=v
    async def delete(self, k): self.store.pop(k, None)
    async def exists(self, k): return 1 if k in self.store else 0
    async def ping(self): return True
