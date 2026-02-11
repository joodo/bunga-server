# PEP-8

import asyncio
from channels.consumer import AsyncConsumer

from server.services import ChatService
from server.channel_cache import ChannelCache
from utils.log import logger


class PresenceWorker(AsyncConsumer):
    async def delayed_offline(self, event: dict[str, any]) -> None:
        await asyncio.sleep(3)

        channel_id, user_id = event["channel_id"], event["user_id"]
        channel_cache = ChannelCache(channel_id)
        channel_name = channel_cache.get_channel_name(user_id)
        if channel_name is None:
            service = ChatService(channel_id)
            await service.dispatch("bye", user_id, None)

    async def delayed_clean_channel(self, event: dict[str, any]) -> None:
        await asyncio.sleep(5 * 60)

        channel_id = event["channel_id"]
        channel_cache = ChannelCache(channel_id)
        if not channel_cache.has_client:
            logger.info(f"No client left, clean channel {channel_id}")
            channel_cache.clean()
