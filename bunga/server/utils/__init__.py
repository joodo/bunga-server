# PEP-8

from functools import wraps

from django.core.cache import cache
from asgiref.sync import async_to_sync


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


def auto_validated(func):
    """
    For DRF ViewSets.
    Wrap an action so that:
      - serializer = self.get_serializer(data=request.data)
      - serializer.is_valid(raise_exception=True)
      - validated_data injected into function as first argument.
    """

    @wraps(func)
    def wrapper(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            data=request.data,
            context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        return func(self, validated, request, *args, **kwargs)

    return wrapper


def async_action(func):
    """
    Decorator to wrap an async method in a sync function,
    so DRF ViewSet @action can call it safely.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        return async_to_sync(func)(self, *args, **kwargs)
    return wrapper
