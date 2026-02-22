# PEP-8

from typing import Any, Callable, Dict, Awaitable, TypeAlias

from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError
from urllib.parse import parse_qs
from django.contrib.auth import get_user_model

from utils.log import logger
from server.models import Channel

User = get_user_model()

Scope: TypeAlias = Dict[str, Any]
Receive: TypeAlias = Callable[[], Awaitable[Dict[str, Any]]]
Send: TypeAlias = Callable[[Dict[str, Any]], Awaitable[None]]
ASGIApp: TypeAlias = Callable[[Scope, Receive, Send], Awaitable[None]]


class JWTAuthMiddleware:
    def __init__(self, inner: ASGIApp) -> None:
        self.inner = inner

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)
        token = params.get("token", [None])[0]

        # Check token
        if not token:
            return await self._close_connection(send, 4401, "Token is required")
            return

        try:
            access = AccessToken(token)
            user = await User.objects.aget(id=access["user_id"])
            if user is None:
                return await self._close_connection(send, 4001, "User not exist")

            scope["user"] = user
        except TokenError as e:
            reason = str(e).lower()
            code = 4002 if "expired" in reason else 4001
            return await self._close_connection(send, code, str(e))
        except Exception as e:
            logger.error(f"Connect failed: {e}")
            return await self._close_connection(send, 4001, str(e))

        channel_id = params.get("channel_id", [None])[0]
        channel = await Channel.objects.filter(channel_id=channel_id).afirst()
        if channel is None:
            return await self._close_connection(send, 4003, "Channel not exist")
        scope["channel"] = channel

        return await self.inner(scope, receive, send)

    async def _close_connection(self, send: Send, code: int, reason: str) -> None:
        await send({"type": "websocket.accept"})
        await send(
            {
                "type": "websocket.close",
                "code": code,
                "reason": reason,
            }
        )
