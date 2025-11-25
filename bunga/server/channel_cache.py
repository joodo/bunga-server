# PEP-8
from dataclasses import replace

from django.core.cache import cache as Cache

from .models.dataclasses import *


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
        if value and self._play_at is None:
            self._play_at = datetime.now()
        if not value and self._play_at is not None:
            self.position += datetime.now() - self._play_at
            self._play_at = None

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


class ChannelCache:
    def __init__(self, channel_id: str):
        self.projection_cache_key = f"channel_{channel_id}_projection"
        self.clients_cache_key = f"channel_{channel_id}_clients"
        self.watchers_cache_key = f"channel_{channel_id}_watchers"
        self.watcher_status_cache_key = f"channel_{channel_id}_watcher_status"
        self.play_status_cache_key = f"channel_{channel_id}_play_status"
        self.waiting_to_start_cache_key = f"channel_{channel_id}_waiting"

    # Projection
    @property
    def current_projection(self) -> Projection | None:
        return Cache.get(self.projection_cache_key)

    @current_projection.setter
    def current_projection(self, new_value: Projection) -> None:
        Cache.set(self.projection_cache_key, new_value, None)

    # Client channel name
    def register_client(self, user_id: str, channel_name: str) -> None:
        clients = Cache.get_or_set(self.clients_cache_key, {}, None)
        clients[user_id] = channel_name
        Cache.set(self.clients_cache_key, clients)

    def get_channel_name(self, user_id: str) -> str | None:
        clients = Cache.get_or_set(self.clients_cache_key, {}, None)
        return clients.get(user_id)

    # Watcher info
    @property
    def watcher_list(self) -> list[UserInfo]:
        return Cache.get(self.watchers_cache_key, {}).values()

    def upsert_watcher(self, new_watcher: UserInfo) -> None:
        data = Cache.get(self.watchers_cache_key, {})
        data[new_watcher.id] = new_watcher
        Cache.set(self.watchers_cache_key, data, None)

    def get_watcher_info(self, user_id: str) -> UserInfo | None:
        data = Cache.get(self.watchers_cache_key, {})
        return data.get(user_id)

    def remove_watcher(self, user_id: str) -> UserInfo | None:
        data = Cache.get(self.watchers_cache_key, {})
        info = data.pop(user_id, None)
        Cache.set(self.watchers_cache_key, data, None)

        data = Cache.get(self.watcher_status_cache_key, {})
        data.pop(user_id, None)
        Cache.set(self.watcher_status_cache_key, data, None)

        return info

    def is_watcher(self, user_id: str) -> bool:
        return user_id in Cache.get(self.watchers_cache_key, {})

    # Watcher status
    @property
    def watcher_status(self) -> dict[str, WatcherStatus]:
        return Cache.get(self.watcher_status_cache_key, {})

    def reset_all_watchers_to_buffering(self) -> None:
        Cache.delete(self.watcher_status_cache_key)

    def set_watcher_status(self, watcher_id: str, status: WatcherStatus) -> None:
        d = self.watcher_status
        d[watcher_id] = status
        Cache.set(self.watcher_status_cache_key, d, None)

    @property
    def is_no_watcher_buffering(self) -> bool:
        status = self.watcher_status
        ids = Cache.get(self.watchers_cache_key, {}).keys()
        for watcher_id in ids:
            if status.get(watcher_id) in (WatcherStatus.BUFFERING, None):
                return False
        return True

    # Play status
    @property
    def play_status(self) -> PlayStatus:
        return Cache.get(self.play_status_cache_key)

    @play_status.setter
    def play_status(self, new_value: PlayStatus) -> None:
        Cache.set(self.play_status_cache_key, new_value, None)

    def set_play(self, is_play: bool) -> None:
        status = self.play_status
        status.playing = is_play
        self.play_status = status

    @property
    def is_waiting_to_start(self) -> bool:
        return Cache.get(self.waiting_to_start_cache_key, False)

    @is_waiting_to_start.setter
    def is_waiting_to_start(self, new_value: bool) -> None:
        Cache.set(self.waiting_to_start_cache_key, new_value, None)
