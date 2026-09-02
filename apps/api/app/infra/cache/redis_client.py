"""
Tenant-Scoped Redis Client:
- Automatic key prefixing with tenant_id
- Connection pooling
- Health checks
- In-memory fallback for development
"""
import os
from functools import lru_cache
from typing import Optional, Any, List
from app.core.config import get_settings
from app.core.tenant import get_current_tenant

_redis_pool = None
_redis_client = None

def get_redis() -> "TenantRedis":
    """Get tenant-scoped Redis client."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    
    settings = get_settings()
    url = settings.redis_url
    
    try:
        import redis.asyncio as aioredis
        pool = aioredis.ConnectionPool.from_url(
            url,
            max_connections=20,
            decode_responses=True,
        )
        raw_client = aioredis.Redis(connection_pool=pool)
        _redis_client = TenantRedis(raw_client)
    except Exception as e:
        print(f"[redis] unavailable, using in-memory stub: {e}")
        _redis_client = TenantRedis(_InMemRedis())
    
    return _redis_client

def get_raw_redis():
    """Get raw Redis client without tenant scoping (for internal use)."""
    global _redis_pool
    if _redis_pool is not None:
        return _redis_pool
    
    settings = get_settings()
    url = settings.redis_url
    
    try:
        import redis.asyncio as aioredis
        _redis_pool = aioredis.from_url(url, decode_responses=True)
    except Exception as e:
        print(f"[redis] unavailable, using in-memory stub: {e}")
        _redis_pool = _InMemRedis()
    
    return _redis_pool


class TenantRedis:
    """
    Tenant-scoped Redis wrapper.
    All keys are automatically prefixed with 'tenant:{tenant_id}:'.
    """
    
    def __init__(self, client):
        self._client = client
        self._tenant_id = None
    
    def _get_tenant_id(self) -> str:
        """Get current tenant ID, fallback to 'global' if not available."""
        try:
            return get_current_tenant()
        except Exception:
            return "global"
    
    def _prefix(self, key: str) -> str:
        """Add tenant prefix to key."""
        tenant_id = self._get_tenant_id()
        return f"tenant:{tenant_id}:{key}"
    
    def _prefix_pattern(self, pattern: str) -> str:
        """Add tenant prefix to pattern for SCAN operations."""
        tenant_id = self._get_tenant_id()
        return f"tenant:{tenant_id}:{pattern}"
    
    # ============================================================
    # Basic Operations (auto-scoped)
    # ============================================================
    
    async def get(self, key: str) -> Optional[str]:
        return await self._client.get(self._prefix(key))
    
    async def set(self, key: str, value: str, ex: int = None, nx: bool = False) -> bool:
        return await self._client.set(self._prefix(key), value, ex=ex, nx=nx)
    
    async def delete(self, *keys: str) -> int:
        prefixed = [self._prefix(k) for k in keys]
        return await self._client.delete(*prefixed)
    
    async def exists(self, key: str) -> int:
        return await self._client.exists(self._prefix(key))
    
    async def incr(self, key: str) -> int:
        return await self._client.incr(self._prefix(key))
    
    async def decr(self, key: str) -> int:
        return await self._client.decr(self._prefix(key))
    
    async def expire(self, key: str, seconds: int) -> bool:
        return await self._client.expire(self._prefix(key), seconds)
    
    async def ttl(self, key: str) -> int:
        return await self._client.ttl(self._prefix(key))
    
    async def pttl(self, key: str) -> int:
        return await self._client.pttl(self._prefix(key))
    
    # ============================================================
    # Hash Operations
    # ============================================================
    
    async def hset(self, name: str, key: str = None, value: str = None, mapping: dict = None) -> int:
        return await self._client.hset(self._prefix(name), key, value, mapping)
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        return await self._client.hget(self._prefix(name), key)
    
    async def hgetall(self, name: str) -> dict:
        return await self._client.hgetall(self._prefix(name))
    
    async def hdel(self, name: str, *keys: str) -> int:
        return await self._client.hdel(self._prefix(name), *keys)
    
    async def hexists(self, name: str, key: str) -> int:
        return await self._client.hexists(self._prefix(name), key)
    
    async def hlen(self, name: str) -> int:
        return await self._client.hlen(self._prefix(name))
    
    async def hkeys(self, name: str) -> List[str]:
        return await self._client.hkeys(self._prefix(name))
    
    async def hvals(self, name: str) -> List[str]:
        return await self._client.hvals(self._prefix(name))
    
    # ============================================================
    # List Operations
    # ============================================================
    
    async def lpush(self, name: str, *values: str) -> int:
        return await self._client.lpush(self._prefix(name), *values)
    
    async def rpush(self, name: str, *values: str) -> int:
        return await self._client.rpush(self._prefix(name), *values)
    
    async def lpop(self, name: str) -> Optional[str]:
        return await self._client.lpop(self._prefix(name))
    
    async def rpop(self, name: str) -> Optional[str]:
        return await self._client.rpop(self._prefix(name))
    
    async def lrange(self, name: str, start: int, end: int) -> List[str]:
        return await self._client.lrange(self._prefix(name), start, end)
    
    async def llen(self, name: str) -> int:
        return await self._client.llen(self._prefix(name))
    
    # ============================================================
    # Set Operations
    # ============================================================
    
    async def sadd(self, name: str, *values: str) -> int:
        return await self._client.sadd(self._prefix(name), *values)
    
    async def srem(self, name: str, *values: str) -> int:
        return await self._client.srem(self._prefix(name), *values)
    
    async def smembers(self, name: str) -> set:
        return await self._client.smembers(self._prefix(name))
    
    async def sismember(self, name: str, value: str) -> bool:
        return await self._client.sismember(self._prefix(name), value)
    
    async def scard(self, name: str) -> int:
        return await self._client.scard(self._prefix(name))
    
    # ============================================================
    # Sorted Set Operations
    # ============================================================
    
    async def zadd(self, name: str, mapping: dict) -> int:
        return await self._client.zadd(self._prefix(name), mapping)
    
    async def zrem(self, name: str, *values: str) -> int:
        return await self._client.zrem(self._prefix(name), *values)
    
    async def zrange(self, name: str, start: int, end: int, withscores: bool = False) -> List:
        return await self._client.zrange(self._prefix(name), start, end, withscores=withscores)
    
    async def zrevrange(self, name: str, start: int, end: int, withscores: bool = False) -> List:
        return await self._client.zrevrange(self._prefix(name), start, end, withscores=withscores)
    
    async def zscore(self, name: str, value: str) -> Optional[float]:
        return await self._client.zscore(self._prefix(name), value)
    
    async def zcard(self, name: str) -> int:
        return await self._client.zcard(self._prefix(name))
    
    # ============================================================
    # Pipeline Operations
    # ============================================================
    
    def pipeline(self):
        """Create a pipeline with auto-tenant prefixing."""
        pipe = self._client.pipeline()
        return TenantPipeline(pipe, self._get_tenant_id())
    
    # ============================================================
    # Scan Operations (for bulk operations)
    # ============================================================
    
    async def scan_keys(self, pattern: str = "*", count: int = 100) -> List[str]:
        """Scan for keys matching pattern within current tenant."""
        prefixed_pattern = self._prefix_pattern(pattern)
        keys = []
        cursor = 0
        while True:
            cursor, found = await self._client.scan(cursor, match=prefixed_pattern, count=count)
            keys.extend(found)
            if cursor == 0:
                break
        # Strip tenant prefix from returned keys
        tenant_prefix = f"tenant:{self._get_tenant_id()}:"
        return [k[len(tenant_prefix):] for k in keys if k.startswith(tenant_prefix)]
    
    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching pattern within current tenant."""
        keys = await self.scan_keys(pattern)
        if keys:
            return await self.delete(*keys)
        return 0
    
    # ============================================================
    # Rate Limiting Helpers
    # ============================================================
    
    async def rate_limit_check(self, key: str, limit: int, window_seconds: int) -> tuple[bool, int, int]:
        """
        Check rate limit using sliding window.
        Returns (allowed, current_count, remaining).
        """
        pipe = self.pipeline()
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
        
        current = results[0]
        allowed = current <= limit
        remaining = max(0, limit - current)
        
        return allowed, current, remaining
    
    async def get_rate_limit_headers(self, key: str, limit: int, window_seconds: int) -> dict:
        """Get standard rate limit headers."""
        allowed, current, remaining = await self.rate_limit_check(key, limit, window_seconds)
        return {
            "X-RateLimit-Limit": str(limit),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(window_seconds),
            "Retry-After": str(window_seconds) if not allowed else "",
        }
    
    # ============================================================
    # Pub/Sub (tenant-scoped channels)
    # ============================================================
    
    async def publish(self, channel: str, message: str) -> int:
        return await self._client.publish(self._prefix(channel), message)
    
    async def subscribe(self, *channels: str):
        prefixed = [self._prefix(c) for c in channels]
        pubsub = self._client.pubsub()
        await pubsub.subscribe(*prefixed)
        return pubsub
    
    # ============================================================
    # Health Check
    # ============================================================
    
    async def ping(self) -> bool:
        try:
            return await self._client.ping()
        except Exception:
            return False
    
    async def info(self) -> dict:
        return await self._client.info()
    
    # ============================================================
    # Raw client access (for advanced use cases)
    # ============================================================
    
    @property
    def raw(self):
        return self._client


class TenantPipeline:
    """Pipeline wrapper that auto-prefixes keys with tenant ID."""
    
    def __init__(self, pipe, tenant_id: str):
        self._pipe = pipe
        self._tenant_id = tenant_id
        self._tenant_prefix = f"tenant:{tenant_id}:"
    
    def _prefix(self, key: str) -> str:
        return f"{self._tenant_prefix}{key}"
    
    # Delegate all pipeline methods with auto-prefixing
    def get(self, key: str):
        return self._pipe.get(self._prefix(key))
    
    def set(self, key: str, value: str, ex: int = None, nx: bool = False):
        return self._pipe.set(self._prefix(key), value, ex=ex, nx=nx)
    
    def delete(self, *keys: str):
        prefixed = [self._prefix(k) for k in keys]
        return self._pipe.delete(*prefixed)
    
    def incr(self, key: str):
        return self._pipe.incr(self._prefix(key))
    
    def decr(self, key: str):
        return self._pipe.decr(self._prefix(key))
    
    def expire(self, key: str, seconds: int):
        return self._pipe.expire(self._prefix(key), seconds)
    
    def hset(self, name: str, key: str = None, value: str = None, mapping: dict = None):
        return self._pipe.hset(self._prefix(name), key, value, mapping)
    
    def hget(self, name: str, key: str):
        return self._pipe.hget(self._prefix(name), key)
    
    def hgetall(self, name: str):
        return self._pipe.hgetall(self._prefix(name))
    
    def lpush(self, name: str, *values: str):
        return self._pipe.lpush(self._prefix(name), *values)
    
    def rpush(self, name: str, *values: str):
        return self._pipe.rpush(self._prefix(name), *values)
    
    def lpop(self, name: str):
        return self._pipe.lpop(self._prefix(name))
    
    def execute(self):
        return self._pipe.execute()
    
    def __getattr__(self, name):
        # Fallback for any unhandled methods
        attr = getattr(self._pipe, name)
        if callable(attr):
            def wrapper(*args, **kwargs):
                # Try to prefix first string argument if it looks like a key
                if args and isinstance(args[0], str) and not args[0].startswith("tenant:"):
                    new_args = (self._prefix(args[0]),) + args[1:]
                    return attr(*new_args, **kwargs)
                return attr(*args, **kwargs)
            return wrapper
        return attr


class _InMemRedis:
    """In-memory Redis stub for development without Redis server."""
    
    def __init__(self):
        self.store = {}
        self.hashes = {}
        self.lists = {}
        self.sets = {}
        self.sorted_sets = {}
        self.expires = {}
    
    async def get(self, key: str) -> Optional[str]:
        if key in self.expires and self.expires[key] < __import__('time').time():
            self.store.pop(key, None)
            self.expires.pop(key, None)
            return None
        return self.store.get(key)
    
    async def set(self, key: str, value: str, ex: int = None, nx: bool = False) -> bool:
        if nx and key in self.store:
            return False
        self.store[key] = value
        if ex:
            self.expires[key] = __import__('time').time() + ex
        return True
    
    async def delete(self, *keys: str) -> int:
        count = 0
        for key in keys:
            if key in self.store:
                del self.store[key]
                count += 1
            self.hashes.pop(key, None)
            self.lists.pop(key, None)
            self.sets.pop(key, None)
            self.sorted_sets.pop(key, None)
            self.expires.pop(key, None)
        return count
    
    async def exists(self, key: str) -> int:
        return 1 if key in self.store else 0
    
    async def incr(self, key: str) -> int:
        val = int(self.store.get(key, 0)) + 1
        self.store[key] = str(val)
        return val
    
    async def decr(self, key: str) -> int:
        val = int(self.store.get(key, 0)) - 1
        self.store[key] = str(val)
        return val
    
    async def expire(self, key: str, seconds: int) -> bool:
        if key in self.store:
            self.expires[key] = __import__('time').time() + seconds
            return True
        return False
    
    async def ttl(self, key: str) -> int:
        if key in self.expires:
            return max(0, int(self.expires[key] - __import__('time').time()))
        return -2 if key not in self.store else -1
    
    async def hset(self, name: str, key: str = None, value: str = None, mapping: dict = None) -> int:
        if name not in self.hashes:
            self.hashes[name] = {}
        if mapping:
            self.hashes[name].update(mapping)
            return len(mapping)
        if key:
            is_new = key not in self.hashes[name]
            self.hashes[name][key] = value
            return 1 if is_new else 0
        return 0
    
    async def hget(self, name: str, key: str) -> Optional[str]:
        return self.hashes.get(name, {}).get(key)
    
    async def hgetall(self, name: str) -> dict:
        return self.hashes.get(name, {})
    
    async def hdel(self, name: str, *keys: str) -> int:
        if name in self.hashes:
            count = 0
            for key in keys:
                if key in self.hashes[name]:
                    del self.hashes[name][key]
                    count += 1
            return count
        return 0
    
    async def hexists(self, name: str, key: str) -> int:
        return 1 if name in self.hashes and key in self.hashes[name] else 0
    
    async def lpush(self, name: str, *values: str) -> int:
        if name not in self.lists:
            self.lists[name] = []
        self.lists[name] = list(values) + self.lists[name]
        return len(self.lists[name])
    
    async def rpush(self, name: str, *values: str) -> int:
        if name not in self.lists:
            self.lists[name] = []
        self.lists[name].extend(values)
        return len(self.lists[name])
    
    async def lpop(self, name: str) -> Optional[str]:
        if name in self.lists and self.lists[name]:
            return self.lists[name].pop(0)
        return None
    
    async def rpop(self, name: str) -> Optional[str]:
        if name in self.lists and self.lists[name]:
            return self.lists[name].pop()
        return None
    
    async def lrange(self, name: str, start: int, end: int) -> List[str]:
        if name not in self.lists:
            return []
        lst = self.lists[name]
        if end == -1:
            return lst[start:]
        return lst[start:end+1]
    
    async def llen(self, name: str) -> int:
        return len(self.lists.get(name, []))
    
    async def sadd(self, name: str, *values: str) -> int:
        if name not in self.sets:
            self.sets[name] = set()
        before = len(self.sets[name])
        self.sets[name].update(values)
        return len(self.sets[name]) - before
    
    async def srem(self, name: str, *values: str) -> int:
        if name not in self.sets:
            return 0
        count = 0
        for v in values:
            if v in self.sets[name]:
                self.sets[name].remove(v)
                count += 1
        return count
    
    async def smembers(self, name: str) -> set:
        return self.sets.get(name, set())
    
    async def sismember(self, name: str, value: str) -> bool:
        return value in self.sets.get(name, set())
    
    async def scard(self, name: str) -> int:
        return len(self.sets.get(name, set()))
    
    async def zadd(self, name: str, mapping: dict) -> int:
        if name not in self.sorted_sets:
            self.sorted_sets[name] = {}
        count = 0
        for k, v in mapping.items():
            if k not in self.sorted_sets[name]:
                count += 1
            self.sorted_sets[name][k] = float(v)
        return count
    
    async def zrem(self, name: str, *values: str) -> int:
        if name not in self.sorted_sets:
            return 0
        count = 0
        for v in values:
            if v in self.sorted_sets[name]:
                del self.sorted_sets[name][v]
                count += 1
        return count
    
    async def zrange(self, name: str, start: int, end: int, withscores: bool = False) -> List:
        if name not in self.sorted_sets:
            return []
        sorted_items = sorted(self.sorted_sets[name].items(), key=lambda x: x[1])
        if end == -1:
            selected = sorted_items[start:]
        else:
            selected = sorted_items[start:end+1]
        if withscores:
            return selected
        return [k for k, v in selected]
    
    async def zcard(self, name: str) -> int:
        return len(self.sorted_sets.get(name, {}))
    
    def pipeline(self):
        return _InMemPipeline(self)
    
    async def scan(self, cursor: int, match: str = None, count: int = 100):
        import fnmatch
        all_keys = list(self.store.keys()) + list(self.hashes.keys()) + list(self.lists.keys()) + list(self.sets.keys()) + list(self.sorted_sets.keys())
        if match:
            pattern = match.replace("*", "")
            all_keys = [k for k in all_keys if fnmatch.fnmatch(k, match)]
        return 0, all_keys
    
    async def publish(self, channel: str, message: str) -> int:
        return 1
    
    async def ping(self) -> bool:
        return True
    
    async def info(self) -> dict:
        return {"redis_mode": "in_memory_stub", "keys": len(self.store)}


class _InMemPipeline:
    """In-memory pipeline for stub."""
    
    def __init__(self, redis: _InMemRedis):
        self._redis = redis
        self._commands = []
    
    def get(self, key: str):
        self._commands.append(("get", key))
        return self
    
    def set(self, key: str, value: str, ex: int = None, nx: bool = False):
        self._commands.append(("set", key, value, ex, nx))
        return self
    
    def delete(self, *keys: str):
        self._commands.append(("delete", keys))
        return self
    
    def incr(self, key: str):
        self._commands.append(("incr", key))
        return self
    
    def decr(self, key: str):
        self._commands.append(("decr", key))
        return self
    
    def expire(self, key: str, seconds: int):
        self._commands.append(("expire", key, seconds))
        return self
    
    def hset(self, name: str, key: str = None, value: str = None, mapping: dict = None):
        self._commands.append(("hset", name, key, value, mapping))
        return self
    
    def hget(self, name: str, key: str):
        self._commands.append(("hget", name, key))
        return self
    
    def hgetall(self, name: str):
        self._commands.append(("hgetall", name))
        return self
    
    def lpush(self, name: str, *values: str):
        self._commands.append(("lpush", name, values))
        return self
    
    def rpush(self, name: str, *values: str):
        self._commands.append(("rpush", name, values))
        return self
    
    def lpop(self, name: str):
        self._commands.append(("lpop", name))
        return self
    
    async def execute(self):
        results = []
        for cmd in self._commands:
            method = getattr(self._redis, cmd[0])
            if len(cmd) == 2:
                results.append(await method(cmd[1]))
            elif len(cmd) == 3:
                results.append(await method(cmd[1], cmd[2]))
            elif len(cmd) == 4:
                results.append(await method(cmd[1], cmd[2], cmd[3]))
            elif len(cmd) == 5:
                results.append(await method(cmd[1], cmd[2], cmd[3], cmd[4]))
            else:
                results.append(await method(*cmd[1:]))
        self._commands.clear()
        return results