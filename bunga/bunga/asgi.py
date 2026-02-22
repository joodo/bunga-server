import os

from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
from django.core.asgi import get_asgi_application

from bunga.workers import PresenceWorker
from bunga.middlewares import JWTAuthMiddleware
from server.urls import websocket_urlpatterns

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bunga.settings")


application = ProtocolTypeRouter(
    {
        "http": get_asgi_application(),
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
        "channel": ChannelNameRouter(
            {
                "presence_worker": PresenceWorker.as_asgi(),
            }
        ),
    }
)
