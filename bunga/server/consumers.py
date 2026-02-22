# PEP-8

import json
from dataclasses import asdict
from typing import Any

from django.contrib.auth import get_user_model
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError

from server.models import Channel
from server.services import ChatService
from server.channel_cache import ChannelCache
from utils.log import logger


User = get_user_model()

IgnoreLoggingCode = {"spark"}


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

        self.user_id: str = self.scope["user"].username  # type: ignore
        self.channel: Channel = self.scope["channel"]  # type: ignore

        self.channel_cache = ChannelCache(self.channel.channel_id)
        self.channel_cache.register_client(self.user_id, self.channel_name)

        self.service = ChatService(self.channel.channel_id)

        self.room_group_name = f"room_{self.channel.channel_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

    async def disconnect(self, code):
        room_group_name = getattr(self, "room_group_name", None)
        if room_group_name is not None:
            await self.channel_layer.group_discard(room_group_name, self.channel_name)

        self.channel_cache.unregister_client(self.user_id)
        await self.channel_layer.send(
            "presence_worker",
            {
                "type": "delayed_offline",
                "user_id": self.user_id,
                "channel_id": self.channel.channel_id,
            },
        )
        await self.channel_layer.send(
            "presence_worker",
            {
                "type": "delayed_clean_channel",
                "channel_id": self.channel.channel_id,
            },
        )

    async def receive_json(self, content: dict, **kwargs):
        code = content.pop("code", None)
        if code not in IgnoreLoggingCode:
            logger.info("Received %s data from %s: %s", code, self.user_id, content)

        FORWARDING_CODES = {
            "talk-status",
            "popmoji",
            "danmaku",
            "spark",
            "play",
            "pause",
            "seek",
        }
        if code in FORWARDING_CODES:
            sender = self.channel_cache.get_watcher_info(self.user_id)
            if sender:
                event = {
                    "type": "message.received",
                    "code": code,
                    "sender": asdict(sender),
                    "data": content,
                }
                await self.channel_layer.group_send(self.room_group_name, event)

        await self.service.dispatch(code, self.user_id, content)

    async def _send_message_to_client(
        self,
        code: str,
        sender: dict,
        data: dict | None = None,
        excludes: list[str] | None = None,
        **kwargs,
    ):
        if excludes and self.user_id in excludes:
            return

        if code not in IgnoreLoggingCode:
            logger.info(
                "Sending message to client %s: code=%s, sender=%s, data=%s",
                self.user_id,
                code,
                sender,
                data,
            )

        await self.send(
            text_data=json.dumps(
                dict(code=code, sender=sender, **(data or {})),
                ensure_ascii=False,
            )
        )

    async def message_received(self, event: dict[str, Any]) -> None:
        await self._send_message_to_client(**event)
