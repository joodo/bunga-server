import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "bunga.settings")
django_asgi_app = get_asgi_application()

from channels.routing import ProtocolTypeRouter, URLRouter, ChannelNameRouter
from bunga.workers import PresenceWorker
from bunga.middlewares import JWTAuthMiddleware
from server.urls import websocket_urlpatterns



application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": JWTAuthMiddleware(URLRouter(websocket_urlpatterns)),
        "channel": ChannelNameRouter(
            {
                "presence_worker": PresenceWorker.as_asgi(),
            }
        ),
    }
)
