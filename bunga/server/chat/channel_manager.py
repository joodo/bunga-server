# PEP-8

import time

from django.core.cache import cache as Cache, caches as Caches
from .channel_cache import ChannelCache


class ChannelManager:
    _stale_seconds = 5 * 60
    _channels_key = Cache.make_key("bunga:channels:last_active")

    @property
    def redis(self):
        cache_backend = Caches["raw_redis"]
        client = getattr(cache_backend, "_cache")
        return client.get_client()

    def set_active(self, channel_id: str) -> None:
        self.redis.hset(self._channels_key, channel_id, str(time.time()))

    def clean_if_stale(self, channel_id: str) -> bool:
        raw_last_active = self.redis.hget(self._channels_key, channel_id)
        if raw_last_active is None:
            ChannelCache(channel_id).reset()
            return True

        try:
            last_active = float(raw_last_active)
        except (TypeError, ValueError):
            self.redis.hdel(self._channels_key, channel_id)
            ChannelCache(channel_id).reset()
            return True

        if (time.time() - last_active) <= self._stale_seconds:
            return False

        self.redis.hdel(self._channels_key, channel_id)
        ChannelCache(channel_id).reset()
        return True

    @property
    def channels(self) -> list[str]:
        return self.redis.hkeys(self._channels_key)


channel_manager = ChannelManager()
