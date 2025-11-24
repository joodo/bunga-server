# PEP-8


from django.core.cache import cache as Cache

from .models.dataclasses import *


class ChannelCache:
    def __init__(self, channel_id: str):
        self.projection_cache_key = f'channel_{channel_id}_projection'
        self.clients_cache_key = f'channel_{channel_id}_clients'
        self.watchers_cache_key = f'channel_{channel_id}_watchers'
        self.watcher_status_cache_key = f'channel_{channel_id}_watcher_status'
        self.play_status_cache_key = f'channel_{channel_id}_play_status'
        self.waiting_to_start_cache_key = f'channel_{channel_id}_waiting'

    # Projection
    @property
    def current_projection(self) -> Projection | None:
        return Cache.get(self.projection_cache_key)

    @current_projection.setter
    def current_projection(self, new_value: Projection) -> None:
        Cache.set(self.projection_cache_key, new_value, None)

    # Client channem name
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

    # Play status
    @property
    def play_status(self) -> PlayStatus:
        return Cache.get(self.play_status_cache_key)

    @play_status.setter
    def play_status(self, new_value: PlayStatus) -> None:
        Cache.set(self.play_status_cache_key, new_value, None)

    def set_waiting_to_start(self) -> None:
        Cache.set(self.waiting_to_start_cache_key, True, None)

    def set_status_to_play(self) -> bool:
        if not Cache.get(self.waiting_to_start_cache_key, False):
            return False

        for watcher_status in self.watcher_status.values():
            if watcher_status == WatcherStatus.BUFFERING:
                return False

        Cache.set(self.waiting_to_start_cache_key, False, None)
        status = self.play_status
        status.playing = True
        self.play_status = status

        return True
