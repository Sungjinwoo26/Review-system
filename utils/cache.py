"""
Simple in-memory caching utility for MVP
"""
import time
from typing import Any, Callable, Optional


class SimpleCache:
    """MVP-level caching mechanism"""
    
    def __init__(self, ttl: int = 300):
        """
        Args:
            ttl: Time-to-live in seconds (default 5 minutes)
        """
        self.cache = {}
        self.ttl = ttl
    
    def get(self, key: str) -> Optional[Any]:
        """Retrieve cached value if not expired"""
        if key in self.cache:
            value, timestamp = self.cache[key]
            if time.time() - timestamp < self.ttl:
                return value
            else:
                del self.cache[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """Store value with timestamp"""
        self.cache[key] = (value, time.time())
    
    def clear(self) -> None:
        """Clear all cached data"""
        self.cache.clear()


# Global cache instance
_global_cache = SimpleCache(ttl=300)


def cached(ttl: int = 300):
    """Decorator for caching function results"""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs) -> Any:
            cache_key = f"{func.__name__}_{args}_{kwargs}"
            
            # Try to get from cache
            result = _global_cache.get(cache_key)
            if result is not None:
                return result
            
            # If not in cache, execute function and cache result
            result = func(*args, **kwargs)
            _global_cache.set(cache_key, result)
            return result
        
        return wrapper
    return decorator


def get_cache() -> SimpleCache:
    """Get global cache instance"""
    return _global_cache
