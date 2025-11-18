# PEP-8

from channels.middleware import BaseMiddleware
from urllib.parse import parse_qs

from utils.log import logger


class JWTAuthMiddleware(BaseMiddleware):
    async def __call__(self, scope, receive, send):
        query_string = scope.get('query_string', b'').decode()
        params = parse_qs(query_string)

        # Check token
        token_list = params.get('token')
        if not token_list:
            logger.i('Token not provided')
            await send({'type': 'websocket.close'})
            return
        token = token_list[0]

        scope['token'] = token
        return await super().__call__(scope, receive, send)
