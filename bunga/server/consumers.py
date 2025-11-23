# PEP-8

import json
from dataclasses import asdict

from django.contrib.auth import get_user_model
from django.core.cache import cache as Cache
from channels.generic.websocket import AsyncWebsocketConsumer
from rest_framework_simplejwt.tokens import AccessToken, TokenError
from asgiref.sync import sync_to_async

from server import serializers
from server.models import Channel, VideoRecord, dataclasses
from server.channel_cache import ChannelCache
from utils.log import logger


User = get_user_model()


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

        token = self.scope.get('token')
        try:
            access = AccessToken(token)
            user_id = access['user_id']
            self.scope['user'] = await User.objects.aget(id=user_id)
        except TokenError as e:
            reason = str(e)
            logger.info(reason)
            code = 4002 if 'expired' in reason else 4001
            await self.close(code=code)

        channel_id = self.scope['url_route']['kwargs']['channel_id']
        self.channel = await Channel.objects.filter(channel_id=channel_id).afirst()
        if self.channel is None:
            await self.close(code=4003)
            return

        self.channel_cache = ChannelCache(channel_id)
        self.channel_cache.register_client(
            self.scope['user'].username, self.channel_name)

        self.room_group_name = f'room_{channel_id}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

    async def disconnect(self, close_code):
        if close_code == 1000:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def _send_to_client(self, data):
        event = {
            'type': 'chat.message',
            'data': data,
        }
        return await self.channel_layer.send(self.channel_name, event)

    async def _send_error_to_client(self, e: Exception):
        return await self._send_to_client({
            'code': 'error',
            'detail': str(e),
        })

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        print(f'receive {text_data_json.get("code")}')

        match text_data_json.get('code'):
            case 'whats-on':
                await self._deal_whats_on()
            case 'join-in':
                await self._deal_join_in(text_data_json)
            case 'start-projection':
                await self._deal_start_projection(sharer=self._get_current_user_info(),
                                                  record_data=text_data_json['video_record'])
            case _:
                pass

    async def _deal_whats_on(self):
        projection = self.channel_cache.current_projection
        print(projection)
        if projection is None:
            return
        record = await VideoRecord.objects.aget(channel=self.channel,
                                                record_id=projection.record_id)
        record_data = serializers.VideoRecordSimpleSerializer(
            record).data
        await self._send_message_to_client(code='now-playing',
                                           sender=projection.sharer,
                                           data={'video_record': record_data})

    async def _deal_join_in(self, json):
        # Join user into channel, and send current user list
        user_info = dataclasses.UserInfo(**json['user'])
        self.channel_cache.upsert_user(user_info)
        user_list = [asdict(u) for u in self.channel_cache.user_list]
        await self._send_message_to_client(code='here-are',
                                           sender=dataclasses.UserInfo.server,
                                           data={'users': user_list},
                                           )

        # Deal with sharing if has, and send
        sharing_record_data = json.get('my_share')
        if sharing_record_data is None:
            # Join others
            current_video_record = await self._get_current_video_record()
            record_data = serializers.VideoRecordSerializer(
                current_video_record).data
            current_sharer = self.channel_cache.current_projection.sharer
            await self._send_message_to_client(code='start-projection',
                                               sender=current_sharer,
                                               data={'video_record': record_data})
        else:
            # Share video with others
            await self._deal_start_projection(user_info, sharing_record_data)

    async def _deal_start_projection(self, sharer: dataclasses.UserInfo, record_data):
        record_id = record_data['record_id']
        if self.channel_cache.current_projection:
            # If playing something...
            current_video_record = await self._get_current_video_record()

            if record_id == self.channel_cache.current_projection.record_id:
                # Playing record_id already, tell sender only
                current_record_data = serializers.VideoRecordSerializer(
                    current_video_record).data
                await self._send_message_to_client(code='start-projection',
                                                   sender=sharer,
                                                   data={'video_record': current_record_data})
                return

            # Playing something but not record_id, save position from cache to db first
            current_video_record.position = self.channel_cache.current_status.position
            await current_video_record.asave()

        self.channel_cache.current_projection = dataclasses.Projection(
            record_id=record_id, sharer=sharer)

        existed = await VideoRecord.objects.select_related('subtitle').filter(
            channel=self.channel,
            record_id=record_id,
        ).afirst()
        if existed:
            # Video has been played before
            self.channel_cache.current_status = dataclasses.ChannelStatus(
                position=existed.position
            )

            # Tell everyone in room
            record_data = serializers.VideoRecordSerializer(existed).data
            await self._send_message_to_room(code='start-projection',
                                             sender=sharer,
                                             data={'video_record': record_data})
        else:
            # Brandy-new projection!
            self.channel_cache.current_status = dataclasses.ChannelStatus()
            instance = await VideoRecord.objects.acreate(channel=self.channel,
                                                         **record_data)
            instance = await VideoRecord.objects.select_related('subtitle').aget(pk=instance.pk)

            # Tell everyone in room
            record_data = serializers.VideoRecordSerializer(instance).data
            await self._send_message_to_room(code='start-projection',
                                             sender=sharer,
                                             data={'video_record': record_data})

    async def _get_current_video_record(self) -> VideoRecord:
        return await VideoRecord.objects.select_related('subtitle').aget(
            channel=self.channel,
            record_id=self.channel_cache.current_projection.record_id,
        )

    def _get_current_user_info(self) -> dataclasses.UserInfo:
        return self.channel_cache.get_user_info(self.scope['user'].username)

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event['message']))

    async def _send_message_to_client(self, code: str, sender: dataclasses.UserInfo,  data: dict):
        await self.send(text_data=json.dumps(dict(
            code=code,
            sender=asdict(sender),
            **data,
        )))

    async def _send_message_to_room(self, code: str, sender: dataclasses.UserInfo, data: dict):
        event = {
            'type': 'chat.message',
            'message': dict(
                code=code,
                sender=asdict(sender),
                **data,
            ),
        }
        return await self.channel_layer.group_send(self.room_group_name, event)

    async def aloha(self, event):
        """
        event keys:
            - sender: str
            - info: UserInfo
        """
        user_info = event['info']
        await self.send(text_data=json.dumps({
            'code': 'aloha',
            'sender': event['sender'],
            'data': asdict(user_info),
        }))

    async def start_projection(self, event):
        """
        event keys:
            - sender: str
            - video_record: VideoRecord
        """
        record = event['video_record']
        record_data = await sync_to_async(
            lambda: serializers.VideoRecordSerializer(record).data
        )()
        data = {
            'code': 'start-projection',
            'sender': asdict(event['sender']),
            'video_record': record_data,
        }
        logger.info(f'send projection: {data}')
        await self.send(text_data=json.dumps(data))

    async def seek_and_pause(self, event):
        """
        event keys:
            - position: deltatime
            - reason:
        """
        await self.send(text_data=json.dumps({
            'code': 'seek-and-pause',
            'position_sec': event['position'],
        }))

    @sync_to_async
    def _save_video_record(self, data):
        serializer = serializers.VideoRecordSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return serializer.save()
