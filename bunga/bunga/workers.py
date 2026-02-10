# PEP-8

import asyncio
from channels.consumer import AsyncConsumer

from server.services import ChatService
from server.channel_cache import ChannelCache
from utils.log import logger


class PresenceWorker(AsyncConsumer):

    async def delayed_offline(self, event: dict[str, any]) -> None:
        await asyncio.sleep(5)

        channel_id, user_id = event["channel_id"], event["user_id"]
        channel_cache = ChannelCache(channel_id)
        channel_name = channel_cache.get_channel_name(user_id)
        if channel_name is None:
            # No new connection with same user_id, safe to disconnect
            if channel_cache.has_client:
                service = ChatService(channel_id)
                await service.dispatch("bye", user_id, None)
            else:
                logger.info("No client left, clean projection")
                channel_cache.clean()
