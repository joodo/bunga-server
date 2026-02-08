# PEP-8
import asyncio
from collections.abc import Awaitable
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from enum import Enum
import json

from django.core.cache import cache as Cache, caches as Caches


@dataclass(frozen=True)
class UserInfo:
    id: str
    name: str
    color_hue: int = 0


UserInfo.server = UserInfo(id="server", name="server")


@dataclass
class VideoRecord:
    record_id: str
    title: str
    source: str
    path: str
    thumb_url: str | None = None


@dataclass
class Projection:
    record: VideoRecord
    sharer: UserInfo


class PlayStatus:
    def __init__(self, playing: bool = False, position: timedelta = timedelta(0)):
        self._position = position
        self._play_at = None

        self.playing = playing

    @property
    def playing(self) -> bool:
        return self._play_at is not None

    @playing.setter
    def playing(self, value: bool) -> None:
        if value and not self.playing:
            self._play_at = datetime.now()
            return

        if not value and self.playing:
            delta = datetime.now() - self._play_at
            self._position += delta
            self._play_at = None
            return

    @property
    def position(self) -> timedelta:
        if not self.playing:
            return self._position
        return self._position + (datetime.now() - self._play_at)

    @position.setter
    def position(self, value) -> None:
        self._position = value
        if self.playing:
            self._play_at = datetime.now()


class ChannelStatus(Enum):
    PAUSED = b"paused"
    WAITING = b"waiting"
    PLAYING = b"playing"
    SEEKING = b"seeking"


class ChannelCache:
    _instances = {}

    def __new__(cls, channel_id: str, *args, **kwargs):
        if channel_id not in cls._instances:
            instance = super().__new__(cls)
            cls._instances[channel_id] = instance
            return instance
        else:
            return cls._instances[channel_id]

    def __init__(self, channel_id: str):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True

        self.channel_id = channel_id
        self.keys = self.Keys(channel_id)

    @property
    def redis(self):
        return Caches["raw_redis"]._cache.get_client()

    # Client channel name
    def register_client(self, user_id: str, channel_name: str) -> None:
        self.redis.hset(self.keys.clients.raw, user_id, channel_name)

    def unregister_client(self, user_id: str) -> None:
        self.redis.hdel(self.keys.clients.raw, user_id)

    def get_channel_name(self, user_id: str) -> str | None:
        return self.redis.hget(self.keys.clients.raw, user_id)

    @property
    def has_client(self):
        return self.redis.hlen(self.keys.clients.raw) > 0

    # Watcher info
    @property
    def watcher_list(self) -> list[UserInfo]:
        raw_values = self.redis.hvals(self.keys.watchers.raw)
        return [UserInfo(**json.loads(v)) for v in raw_values]

    @property
    def watcher_ids(self) -> list[str]:
        return self.redis.hkeys(self.keys.watchers.raw)

    def upsert_watcher(self, new_watcher: UserInfo) -> None:
        watcher_data = json.dumps(asdict(new_watcher))
        self.redis.hset(
            self.keys.watchers.raw,
            new_watcher.id,
            watcher_data,
        )

    def get_watcher_info(self, user_id: str) -> UserInfo | None:
        raw_data = self.redis.hget(self.keys.watchers.raw, user_id)
        if raw_data is None:
            return None
        return UserInfo(**json.loads(raw_data))

    def remove_watcher(self, user_id: str) -> UserInfo | None:
        watcher = self.get_watcher_info(user_id)
        if watcher is None:
            return None

        self.redis.hdel(self.keys.watchers.raw, user_id)
        return watcher

    def is_watcher(self, user_id: str) -> bool:
        return self.redis.hexists(self.keys.watchers.raw, user_id)

    # Buffering watchers
    @property
    def ready_watchers(self) -> list[str]:
        return self.redis.smembers(self.keys.ready_watchers.raw)

    @property
    def buffering_watchers(self) -> list[str]:
        watcher_ids = self.watcher_ids
        ready_ids = self.ready_watchers
        return [id for id in watcher_ids if id not in ready_ids]

    def reset_all_watchers_to_buffering(self) -> None:
        self.redis.delete(self.keys.ready_watchers.raw)

    def set_watcher_status(self, watcher_id: str, is_buffering: bool) -> bool:
        status_changed = False
        if is_buffering:
            status_changed = self.redis.srem(self.keys.ready_watchers.raw, watcher_id)
        else:
            status_changed = self.redis.sadd(self.keys.ready_watchers.raw, watcher_id)

        return status_changed

    @property
    def is_all_watchers_ready(self) -> bool:
        return len(self.buffering_watchers) == 0

    # Projection
    @property
    def current_projection(self) -> Projection | None:
        return Cache.get(self.keys.projection)

    @current_projection.setter
    def current_projection(self, new_value: Projection | None) -> None:
        Cache.set(self.keys.projection, new_value, None)

    def clean_projection(self):
        # Save watch progress if have
        if self.current_projection is not None:
            self.save_progress(
                self.current_projection.record.record_id,
                self.play_status.position,
            )

        self.current_projection = None
        self.play_status = PlayStatus()
        self.channel_status = ChannelStatus.PAUSED

    # Channel status
    @property
    def channel_status(self) -> ChannelStatus:
        status = Cache.get(self.keys.channel_status, ChannelStatus.PAUSED)
        return ChannelStatus(status)

    @channel_status.setter
    def channel_status(self, new_value: ChannelStatus) -> None:
        Cache.set(self.keys.channel_status, new_value, None)

    # Play status
    @property
    def play_status(self) -> PlayStatus:
        return Cache.get(self.keys.play_status)

    @play_status.setter
    def play_status(self, new_value: PlayStatus) -> None:
        Cache.set(self.keys.play_status, new_value, None)

    def set_play(self, is_play: bool) -> None:
        status = self.play_status
        status.playing = is_play
        self.play_status = status

    def set_position(self, position: timedelta) -> None:
        status = self.play_status
        status.position = position
        self.play_status = status

    # Watch progress
    def save_progress(self, record_id: str, position: timedelta) -> None:
        data = {"position": position.total_seconds(), "updated_at": datetime.now()}
        key = self.keys.watch_progresses.raw
        client = self.redis

        client.hset(key, record_id, json.dumps(data, default=str))

        # TODO: clean up old progresses if needed

    def get_progress(self, record_id: str) -> timedelta | None:
        key = self.keys.watch_progresses.raw
        client = self.redis

        raw_data = client.hget(key, record_id)
        if raw_data is None:
            return None

        data = json.loads(raw_data)
        position_sec = data.get("position")
        if position_sec is None:
            return None

        return timedelta(seconds=position_sec)

    # Call
    def init_call_pending_ids(self, call_id: str) -> bool:
        watcher_ids = self.watcher_ids
        watcher_ids.remove(call_id)
        if not watcher_ids:
            return False

        self.redis.sadd(self.keys.call_pending_ids.raw, *watcher_ids)
        return True

    def remove_call_pending_id(self, response_id: str) -> None:
        self.redis.srem(self.keys.call_pending_ids.raw, response_id)

    def clear_call_pending_ids(self) -> None:
        self.redis.delete(self.keys.call_pending_ids.raw)

    @property
    def has_pending_call(self) -> bool:
        return self.redis.scard(self.keys.call_pending_ids.raw) > 0

    # Utils
    def clean(self) -> None:
        self.clean_projection()
        self.redis.delete(self.keys.clients.raw)
        self.redis.delete(self.keys.watchers.raw)
        self.redis.delete(self.keys.ready_watchers.raw)
        self.redis.delete(self.keys.call_pending_ids.raw)

    class Keys:
        def __init__(self, channel_id: str):
            self.channel_id = channel_id
            self.prefix = f"bunga:channel:{channel_id}"

        class _Key:
            def __init__(self, key):
                self.key = key

            @property
            def raw(self):
                return Cache.make_key(self.key)

            def __str__(self):
                return self.key

        @property
        def projection(self):
            return self._Key(f"{self.prefix}:projection")

        @property
        def clients(self):
            return self._Key(f"{self.prefix}:clients")

        @property
        def watchers(self):
            return self._Key(f"{self.prefix}:watchers")

        @property
        def ready_watchers(self):
            return self._Key(f"{self.prefix}:ready_watchers")

        @property
        def channel_status(self):
            return self._Key(f"{self.prefix}:channel_status")

        @property
        def play_status(self):
            return self._Key(f"{self.prefix}:play_status")

        @property
        def watch_progresses(self):
            return self._Key(f"{self.prefix}:watch_progresses")

        @property
        def call_pending_ids(self):
            return self._Key(f"{self.prefix}:call_pending_ids")


class SeekCountdownManager:
    # Seek Countdown Timer, for SEEKING to PLAYING transition
    _tasks: dict[str, asyncio.Task] = {}

    _countdown_seconds = 5

    @classmethod
    async def _run_task(cls, channel_id: str, coro):
        try:
            await asyncio.sleep(cls._countdown_seconds)
            await coro
        except asyncio.CancelledError:
            pass
        finally:
            if cls._tasks.get(channel_id) == asyncio.current_task():
                cls._tasks.pop(channel_id, None)

    @classmethod
    def reset(cls, channel_id: str, coro: Awaitable[None]):
        if channel_id in cls._tasks:
            cls._tasks[channel_id].cancel()

        task = asyncio.create_task(cls._run_task(channel_id, coro))
        cls._tasks[channel_id] = task

    @classmethod
    def cancel(cls, channel_id: str):
        task = cls._tasks.pop(channel_id, None)
        if task:
            task.cancel()
