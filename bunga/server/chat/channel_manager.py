# PEP-8

import time

from django.core.cache import cache as Cache, caches as Caches

from utils.log import logger
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
        channel_cache = ChannelCache(channel_id)
        try:
            if channel_cache.has_client:
                return False

            raw_last_active = self.redis.hget(self._channels_key, channel_id)
            last_active = float(raw_last_active)
            if (time.time() - last_active) <= self._stale_seconds:
                return False

            raise Exception("staled")
        except:
            logger.info(f"Clean staled channel {channel_id}")
            self.redis.hdel(self._channels_key, channel_id)
            channel_cache.reset()
            return True

    @property
    def channels(self) -> list[str]:
        return self.redis.hkeys(self._channels_key)


channel_manager = ChannelManager()
