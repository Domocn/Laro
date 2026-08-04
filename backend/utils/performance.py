"""
Performance Utilities - Monitoring, caching, and optimization helpers
"""
import time
import logging
import functools
from typing import Callable, Any, Optional
from datetime import datetime, timedelta, timezone
import asyncio

logger = logging.getLogger(__name__)


def measure_time(func_name: Optional[str] = None):
    """
    Decorator to measure function execution time.

    Usage:
        @measure_time()
        async def my_slow_function():
            ...

    Args:
        func_name: Optional custom name for logging
    """
    def decorator(func: Callable) -> Callable:
        name = func_name or func.__name__

        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    elapsed = (time.time() - start_time) * 1000
                    if elapsed > 1000:  # Log slow functions (>1s)
                        logger.warning(f"{name} took {elapsed:.2f}ms (SLOW)")
                    else:
                        logger.debug(f"{name} took {elapsed:.2f}ms")
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                try:
                    result = func(*args, **kwargs)
                    return result
                finally:
                    elapsed = (time.time() - start_time) * 1000
                    if elapsed > 1000:
                        logger.warning(f"{name} took {elapsed:.2f}ms (SLOW)")
                    else:
                        logger.debug(f"{name} took {elapsed:.2f}ms")
            return sync_wrapper

    return decorator


class SimpleCache:
    """
    Simple in-memory cache with TTL support.

    For production, consider using Redis for distributed caching.

    Usage:
        cache = SimpleCache(ttl_seconds=300)  # 5 minute TTL

        @cache.cached(key_prefix="user")
        async def get_user(user_id: str):
            return await user_repository.find_by_id(user_id)
    """

    def __init__(self, ttl_seconds: int = 300):
        """
        Initialize cache.

        Args:
            ttl_seconds: Time to live for cached items
        """
        self.ttl_seconds = ttl_seconds
        self._cache = {}  # key -> (value, expiry_time)

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        if key not in self._cache:
            return None

        value, expiry = self._cache[key]

        # Check expiry
        if datetime.now(timezone.utc) > expiry:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any):
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        expiry = datetime.now(timezone.utc) + timedelta(seconds=self.ttl_seconds)
        self._cache[key] = (value, expiry)

    def delete(self, key: str):
        """
        Delete value from cache.

        Args:
            key: Cache key
        """
        self._cache.pop(key, None)

    def clear(self):
        """Clear all cached values"""
        self._cache.clear()

    def cleanup_expired(self):
        """Remove expired entries from cache"""
        now = datetime.now(timezone.utc)
        expired_keys = [
            key for key, (_, expiry) in self._cache.items()
            if now > expiry
        ]
        for key in expired_keys:
            del self._cache[key]

        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired cache entries")

    def cached(self, key_prefix: str = ""):
        """
        Decorator for caching function results.

        Args:
            key_prefix: Prefix for cache key

        Usage:
            @cache.cached(key_prefix="user")
            async def get_user(user_id: str):
                return await db.get(user_id)
        """
        def decorator(func: Callable) -> Callable:
            if asyncio.iscoroutinefunction(func):
                @functools.wraps(func)
                async def async_wrapper(*args, **kwargs):
                    # Generate cache key from function args
                    cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

                    # Check cache
                    cached_value = self.get(cache_key)
                    if cached_value is not None:
                        logger.debug(f"Cache HIT: {cache_key}")
                        return cached_value

                    # Call function
                    logger.debug(f"Cache MISS: {cache_key}")
                    result = await func(*args, **kwargs)

                    # Cache result
                    self.set(cache_key, result)

                    return result
                return async_wrapper
            else:
                @functools.wraps(func)
                def sync_wrapper(*args, **kwargs):
                    cache_key = f"{key_prefix}:{func.__name__}:{str(args)}:{str(kwargs)}"

                    cached_value = self.get(cache_key)
                    if cached_value is not None:
                        logger.debug(f"Cache HIT: {cache_key}")
                        return cached_value

                    logger.debug(f"Cache MISS: {cache_key}")
                    result = func(*args, **kwargs)
                    self.set(cache_key, result)

                    return result
                return sync_wrapper

        return decorator


# Global cache instances
user_cache = SimpleCache(ttl_seconds=300)  # 5 minutes
recipe_cache = SimpleCache(ttl_seconds=600)  # 10 minutes
settings_cache = SimpleCache(ttl_seconds=1800)  # 30 minutes


class PerformanceMonitor:
    """
    Monitor application performance metrics.

    Tracks:
    - Request counts
    - Average response times
    - Slow requests
    - Error rates
    """

    def __init__(self):
        self.total_requests = 0
        self.total_errors = 0
        self.response_times = []
        self.slow_requests = []
        self.max_slow_requests = 100  # Keep last 100 slow requests

    def record_request(self, path: str, status_code: int, response_time_ms: float):
        """
        Record a request for performance monitoring.

        Args:
            path: Request path
            status_code: HTTP status code
            response_time_ms: Response time in milliseconds
        """
        self.total_requests += 1

        if status_code >= 400:
            self.total_errors += 1

        self.response_times.append(response_time_ms)

        # Keep only last 1000 response times
        if len(self.response_times) > 1000:
            self.response_times = self.response_times[-1000:]

        # Track slow requests (>1s)
        if response_time_ms > 1000:
            self.slow_requests.append({
                "path": path,
                "status_code": status_code,
                "response_time_ms": response_time_ms,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })

            # Keep only last N slow requests
            if len(self.slow_requests) > self.max_slow_requests:
                self.slow_requests = self.slow_requests[-self.max_slow_requests:]

    def get_stats(self) -> dict:
        """
        Get performance statistics.

        Returns:
            Dictionary with performance metrics
        """
        if not self.response_times:
            return {
                "total_requests": self.total_requests,
                "total_errors": self.total_errors,
                "error_rate": 0.0,
                "avg_response_time_ms": 0.0,
                "min_response_time_ms": 0.0,
                "max_response_time_ms": 0.0,
                "slow_requests_count": len(self.slow_requests)
            }

        return {
            "total_requests": self.total_requests,
            "total_errors": self.total_errors,
            "error_rate": (self.total_errors / self.total_requests * 100) if self.total_requests > 0 else 0,
            "avg_response_time_ms": sum(self.response_times) / len(self.response_times),
            "min_response_time_ms": min(self.response_times),
            "max_response_time_ms": max(self.response_times),
            "slow_requests_count": len(self.slow_requests),
            "recent_slow_requests": self.slow_requests[-10:]  # Last 10 slow requests
        }

    def reset(self):
        """Reset all statistics"""
        self.total_requests = 0
        self.total_errors = 0
        self.response_times = []
        self.slow_requests = []


# Global performance monitor
perf_monitor = PerformanceMonitor()


def batch_database_queries(queries: list, batch_size: int = 100):
    """
    Split large database queries into batches to prevent timeout.

    Usage:
        recipe_ids = [1000 recipe IDs]
        for batch in batch_database_queries(recipe_ids, batch_size=50):
            recipes = await recipe_repository.find_many({"id": {"$in": batch}})

    Args:
        queries: List of queries/IDs to batch
        batch_size: Maximum size of each batch

    Yields:
        Batches of queries
    """
    for i in range(0, len(queries), batch_size):
        yield queries[i:i + batch_size]


async def async_batch_processor(
    items: list,
    processor: Callable,
    batch_size: int = 10,
    delay_between_batches: float = 0.1
):
    """
    Process items in batches with async concurrency control.

    Prevents overwhelming the database/API with too many concurrent requests.

    Usage:
        async def process_recipe(recipe_id):
            return await update_recipe(recipe_id)

        results = await async_batch_processor(
            recipe_ids,
            process_recipe,
            batch_size=10
        )

    Args:
        items: List of items to process
        processor: Async function to process each item
        batch_size: Number of concurrent tasks
        delay_between_batches: Delay in seconds between batches

    Returns:
        List of results
    """
    results = []

    for batch in batch_database_queries(items, batch_size):
        # Process batch concurrently
        batch_results = await asyncio.gather(*[processor(item) for item in batch])
        results.extend(batch_results)

        # Small delay to prevent overwhelming the system
        if delay_between_batches > 0:
            await asyncio.sleep(delay_between_batches)

    return results
