import json

from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import AccessToken, TokenError

from server.models import Channel
from utils.log import logger


User = get_user_model()


@database_sync_to_async
def get_user(user_id):
    try:
        return User.objects.get(id=user_id)
    except User.DoesNotExist:
        return None


@database_sync_to_async
def get_channel(channel_id):
    try:
        return Channel.objects.get(channel_id=channel_id)
    except Channel.DoesNotExist:
        return None


class ChatConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()

        token = self.scope.get('token')
        try:
            access = AccessToken(token)
            user_id = access['user_id']
            self.scope['user'] = await get_user(user_id)
        except TokenError as e:
            reason = str(e)
            logger.info(reason)
            code = 4002 if 'expired' in reason else 4001
            await self.close(code=code)

        self.channel_id = self.scope['url_route']['kwargs']['channel_id']
        channel = await get_channel(self.channel_id)
        if not channel:
            await self.close(code=4003)
            return

        self.room_group_name = f'chat_{self.channel_id}'
        await self.channel_layer.group_add(self.room_group_name, self.channel_name)

    async def disconnect(self, close_code):
        if close_code == 1000:
            await self.channel_layer.group_discard(
                self.room_group_name, self.channel_name
            )

    async def receive(self, text_data):
        text_data_json = json.loads(text_data)
        text_data_json['type'] = 'chat.message'
        text_data_json['sender'] = self.scope['user'].username

        await self.channel_layer.group_send(
            self.room_group_name, text_data_json
        )

    async def chat_message(self, event):
        await self.send(text_data=json.dumps(event))
