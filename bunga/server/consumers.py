# PEP-8

from dataclasses import asdict
import json
from django.contrib.auth import get_user_model
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken, TokenError

from server.models import Channel
from server.schemas import PROTOCOL_MAP
from server.services import ChatService, OutboundCommand, OutboundCommandList
from server.channel_cache import ChannelCache
from utils.log import logger


User = get_user_model()

IgnoreLoggingCode = {"spark"}


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        await self.accept()

        token = self.scope.get("token")
        try:
            access = AccessToken(token)
            user_id = access["user_id"]
            self.scope["user"] = await User.objects.aget(id=user_id)
        except TokenError as e:
            reason = str(e)
            logger.info(reason)
            code = 4002 if "expired" in reason else 4001
            await self.close(code=code)

        channel_id = self.scope["url_route"]["kwargs"]["channel_id"]
        self.channel = await Channel.objects.filter(channel_id=channel_id).afirst()
        if self.channel is None:
            await self.close(code=4003)
            return

        self.user_id = self.scope["user"].username

        self.channel_cache = ChannelCache(channel_id)
        self.channel_cache.register_client(self.user_id, self.channel_name)

        self.service = ChatService(channel_id)

        self.room_group_name = f"room_{channel_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

    async def disconnect(self, close_code):
        room_group_name = getattr(self, "room_group_name", None)
        if room_group_name is not None:
            await self.channel_layer.group_discard(room_group_name, self.channel_name)

        user_id: str = getattr(self, "user_id", None)
        channel: Channel | None = getattr(self, "channel", None)
        if user_id and channel:
            self.channel_cache.unregister_client(user_id)
            await self.channel_layer.send(
                "presence_worker",
                {
                    "type": "delayed_offline",
                    "user_id": user_id,
                    "channel_id": channel.channel_id,
                },
            )
            await self.channel_layer.send(
                "presence_worker",
                {
                    "type": "delayed_clean_channel",
                    "channel_id": channel.channel_id,
                },
            )

    async def receive_json(self, content: dict, **kwargs):
        code = content.pop("code", None)
        if code not in IgnoreLoggingCode:
            logger.info("Received data from %s: %s", self.user_id, content)

        commands: OutboundCommandList = await self.service.dispatch(
            code, self.user_id, content
        )
        for command in commands:
            command: OutboundCommand
            await self._send_message_to_client(
                code=command.code,
                sender=asdict(command.sender),
                data=asdict(command.schema_data) if command.schema_data else None,
            )

    async def _send_message_to_client(
        self,
        code: str,
        sender: dict,
        data: dict | None = None,
        excludes: list[str] = [],
        **kwargs,
    ):
        if self.user_id in excludes:
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

    async def send_event_receiver(self, event: dict[str, any]) -> None:
        # event.pop("type", None)
        await self._send_message_to_client(**event)
