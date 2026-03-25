# PEP-8

from typing import Any

import asyncio
from channels.consumer import AsyncConsumer

from server.chat.services.presence_service import ChannelPresenceService
from server.chat.channel_manager import channel_manager
from server.chat.schemas import ChannelStatusSchema
from server.chat.utils import broadcast_message
from server.chat.channel_cache import ChannelCache


class PresenceWorker(AsyncConsumer):

    async def start_heartbeat(self, event: dict[str, Any]) -> None:
        if hasattr(self, "is_running"):
            return
        self.is_running = True

        while True:
            for channel_id in channel_manager.channels:
                if channel_manager.clean_if_stale(channel_id):
                    continue

                await ChannelPresenceService(channel_id).remove_stale_user()

                channel_cache = ChannelCache(channel_id)
                data = ChannelStatusSchema.from_channel_cache(channel_cache)
                await broadcast_message(
                    channel_id,
                    "channel-status",
                    data=data,
                )

            await asyncio.sleep(1)
