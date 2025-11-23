# PEP-8


from django.core.cache import cache as Cache

from .models.dataclasses import ChannelStatus, UserInfo, Projection


class ChannelCache:
    def __init__(self, channel_id: str):
        self.projection_cache_key = f'channel_{channel_id}_projection'
        self.status_cache_key = f'channel_{channel_id}_status'
        self.clients_cache_key = f'channel_{channel_id}_clients'
        self.users_cache_key = f'channel_{channel_id}_users'

    @property
    def current_projection(self) -> Projection | None:
        return Cache.get(self.projection_cache_key)

    @current_projection.setter
    def current_projection(self, new_value: Projection) -> None:
        Cache.set(self.projection_cache_key, new_value, None)

    @property
    def current_status(self) -> ChannelStatus:
        return Cache.get(self.status_cache_key)

    @current_status.setter
    def current_status(self, new_value: ChannelStatus) -> None:
        Cache.set(self.status_cache_key, new_value, None)

    def register_client(self, user_id: str, channel_name: str) -> None:
        clients = Cache.get_or_set(self.clients_cache_key, {}, None)
        clients[user_id] = channel_name
        Cache.set(self.clients_cache_key, clients)

    def get_channel_name(self, user_id: str) -> str | None:
        clients = Cache.get_or_set(self.clients_cache_key, {}, None)
        print(clients)
        return clients.get(user_id)

    @property
    def user_list(self) -> list[UserInfo]:
        return Cache.get_or_set(self.users_cache_key, [], None)

    def upsert_user(self, new_user: UserInfo) -> None:
        users = self.user_list
        for i, u in enumerate(users):
            if u.id == new_user.id:
                users[i] = new_user
                return
        users.append(new_user)
        Cache.set(self.users_cache_key, users)

    def get_user_info(self, user_id: str) -> UserInfo:
        users = Cache.get(self.users_cache_key, [])
        return next((x for x in users if x.id == user_id), None)
