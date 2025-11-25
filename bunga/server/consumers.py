# PEP-8

import json
from datetime import timedelta
from dataclasses import asdict

import asyncio
from django.contrib.auth import get_user_model
from django.core.cache import cache as Cache
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from asgiref.sync import sync_to_async

from server import serializers
from server.models import Channel, VideoRecord, dataclasses as DC
from server.channel_cache import ChannelCache, PlayStatus
from utils.log import logger


User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
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

        self.room_group_name = f"room_{channel_id}"
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

        if self.channel_cache.get_watcher_info(self.user_id) is None:
            # Perhaps the user lost connection
            await self._send_message_to_client("who-are-you", DC.UserInfo.server)

    async def disconnect(self, close_code):
        room_group_name = getattr(self, "room_group_name", None)
        if room_group_name is not None:
            await self.channel_layer.group_discard(room_group_name, self.channel_name)

        user_id = getattr(self, "user_id", None)
        if user_id is not None and self.channel_cache.is_watcher(user_id):
            asyncio.create_task(self.delayed_offline(user_id))

    async def delayed_offline(self, user_id: str):
        await asyncio.sleep(3000)
        current_name = self.channel_cache.get_channel_name(self.user_id)
        if current_name == self.channel_name:
            watcher = self.channel_cache.remove_watcher(user_id)
            if watcher is not None:
                self._send_message_to_room("bye", watcher)

    async def receive(self, text_data: str):
        data = json.loads(text_data)

        sender = self.channel_cache.get_watcher_info(self.user_id)
        code = data.pop("code", None)

        match code:
            # cases without return will forward to room
            case "whats-on":
                await self._deal_whats_on()
                return
            case "join-in":
                await self._deal_join_in(data)
                return
            case "start-projection":
                await self._deal_start_projection(
                    sharer=sender, record_data=data["video_record"]
                )
                return
            case "sync-status":
                await self._deal_sync_status(sender, DC.WatcherStatus(data["status"]))
            case "play-at":
                await self._deal_play_at(
                    data["is_play"], timedelta(microseconds=data["position"])
                )
            case "bye":
                await self._deal_bye()
            case _:
                logger.warning("Unknown message received: %s", text_data)
                return

        await self._send_message_to_room(code, sender, data)

    async def _deal_whats_on(self):
        projection = self.channel_cache.current_projection
        if projection is None:
            return
        record = await VideoRecord.objects.aget(
            channel=self.channel, record_id=projection.record_id
        )
        record_data = serializers.VideoRecordSimpleSerializer(record).data
        await self._send_message_to_client(
            code="now-playing",
            sender=projection.sharer,
            data={"video_record": record_data},
        )

    async def _deal_join_in(self, json):
        # Send current watcher list to client
        status = self.channel_cache.watcher_status
        watcher_list = [
            {
                "user": asdict(u),
                "sync_status": status.get(u.id, DC.WatcherStatus.BUFFERING).value,
            }
            for u in self.channel_cache.watcher_list
        ]
        await self._send_message_to_client(
            code="here-are",
            sender=DC.UserInfo.server,
            data={"watchers": watcher_list},
        )

        # Join user into channel, tell others
        user_info = DC.UserInfo(**json["user"])
        self.channel_cache.upsert_watcher(user_info)
        await self._send_message_to_room(code="aloha", sender=user_info)

        # Deal with sharing if has
        sharing_record_data = json.get("my_share")
        if sharing_record_data is None:
            # Join others
            current_video_record = await self._get_current_video_record()
            record_data = serializers.VideoRecordSerializer(current_video_record).data
            record_data["position"] = (
                self.channel_cache.play_status.position.total_seconds() * 1000_000
            )
            current_sharer = self.channel_cache.current_projection.sharer
            await self._send_message_to_client(
                code="start-projection",
                sender=current_sharer,
                data={"video_record": record_data},
            )

            # Make others wait if playing
            await self._update_play_status()
        else:
            # Share video with others
            await self._deal_start_projection(user_info, sharing_record_data)

    async def _deal_start_projection(self, sharer: DC.UserInfo, record_data):
        record_id = record_data["record_id"]
        if self.channel_cache.current_projection:
            # If playing something...
            current_video_record = await self._get_current_video_record()

            if record_id == self.channel_cache.current_projection.record_id:
                # Playing record_id already, tell sender only
                current_record_data = serializers.VideoRecordSerializer(
                    current_video_record
                ).data
                current_record_data["position"] = (
                    self.channel_cache.play_status.position.total_seconds() * 1000_000
                )
                await self._send_message_to_client(
                    code="start-projection",
                    sender=sharer,
                    data={"video_record": current_record_data},
                )
                return

            # Playing something but not record_id, save position from cache to db first
            current_video_record.position = self.channel_cache.play_status.position
            await current_video_record.asave()

        self.channel_cache.current_projection = DC.Projection(
            record_id=record_id, sharer=sharer
        )
        self.channel_cache.reset_all_watchers_to_buffering()

        existed = (
            await VideoRecord.objects.select_related("subtitle")
            .filter(
                channel=self.channel,
                record_id=record_id,
            )
            .afirst()
        )
        if existed:
            # Video has been played before
            self.channel_cache.play_status = PlayStatus(position=existed.position)

            # Tell everyone in room
            record_data = serializers.VideoRecordSerializer(existed).data
            await self._send_message_to_room(
                code="start-projection",
                sender=sharer,
                data={"video_record": record_data},
            )
        else:
            # Brandy-new projection!
            self.channel_cache.play_status = PlayStatus()
            instance = await VideoRecord.objects.acreate(
                channel=self.channel, **record_data
            )
            instance = await VideoRecord.objects.select_related("subtitle").aget(
                pk=instance.pk
            )

            # Tell everyone in room
            record_data = serializers.VideoRecordSerializer(instance).data
            await self._send_message_to_room(
                code="start-projection",
                sender=sharer,
                data={"video_record": record_data},
            )

    async def _deal_sync_status(
        self, watcher: DC.UserInfo | None, status: DC.WatcherStatus
    ):
        if watcher is None:
            return
        self.channel_cache.set_watcher_status(watcher.id, status)
        await self._update_play_status()

    async def _deal_play_at(self, is_play: bool, position: timedelta):
        self.channel_cache.play_status = PlayStatus(position=position, playing=False)
        if is_play:
            self.channel_cache.is_waiting_to_start = True
            await self._update_play_status()

    async def _deal_bye(self):
        self.channel_cache.remove_watcher(self.user_id)

    async def _update_play_status(self) -> None:
        # Someone buffer when playing
        if (
            self.channel_cache.play_status.playing
            and not self.channel_cache.is_no_watcher_buffering
        ):
            self.channel_cache.set_play(False)
            self.channel_cache.is_waiting_to_start = True
            await self._send_current_play_status()

        # Every one is ready for play
        if (
            self.channel_cache.is_waiting_to_start
            and self.channel_cache.is_no_watcher_buffering
        ):
            self.channel_cache.set_play(True)
            self.channel_cache.is_waiting_to_start = False
            await self._send_current_play_status()

    async def _send_current_play_status(self) -> None:
        status = self.channel_cache.play_status
        await self._send_message_to_room(
            code="play-at",
            sender=DC.UserInfo.server,
            data={
                "is_play": status.playing,
                "position": status.position.total_seconds() * 1000_000,
            },
        )

    async def _get_current_video_record(self) -> VideoRecord:
        return await VideoRecord.objects.select_related("subtitle").aget(
            channel=self.channel,
            record_id=self.channel_cache.current_projection.record_id,
        )

    async def _send_message_to_client(
        self, code: str, sender: DC.UserInfo, data: dict | None = None
    ):
        return await self.send(
            text_data=json.dumps(
                dict(
                    code=code,
                    sender=asdict(sender),
                    **(data or {}),
                )
            )
        )

    async def _send_message_to_room(
        self, code: str, sender: DC.UserInfo | None, data: dict | None = None
    ):
        if sender is None:
            return
        event = {
            "type": "chat.message",
            "message": dict(
                code=code,
                sender=asdict(sender),
                **(data or {}),
            ),
        }
        return await self.channel_layer.group_send(self.room_group_name, event)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event["message"]))
