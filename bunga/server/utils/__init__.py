from functools import wraps
from django.core.cache import cache


def cached_function(key_func, timeout=60 * 15):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = key_func(*args, **kwargs)
            value = cache.get(key)
            if value is None:
                value = func(*args, **kwargs)
                cache.set(key, value, timeout)
            return value
        return wrapper
    return decorator
