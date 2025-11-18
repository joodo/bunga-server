# PEP-8

from django.urls import path

from . import consumers

websocket_urlpatterns = [
    path('chat/<str:channel_id>/', consumers.ChatConsumer.as_asgi()),
]
