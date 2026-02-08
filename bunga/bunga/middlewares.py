# PEP-8

from channels.exceptions import DenyConnection
from channels.middleware import BaseMiddleware
from urllib.parse import parse_qs


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        params = parse_qs(query_string)

        # Check token
        token_list = params.get("token")
        if not token_list:
            await send(
                {
                    "type": "websocket.close",
                    "code": 4401,
                }
            )
            return

        scope["token"] = token_list[0]
        return await super().__call__(scope, receive, send)
