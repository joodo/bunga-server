import json

import jwt

from urllib.parse import parse_qs

from django.utils import timezone
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from asgiref.sync import sync_to_async


class JWTRestAuthentication(JWTAuthentication):
    def authenticate(self, request):
        header = self.get_header(request)
        if header is None:
            return None

        raw_token = self.get_raw_token(header)
        if raw_token is None:
            return None
        try:
            validated_token = self.get_validated_token(raw_token)
        except Exception:
            try:
                payload = jwt.decode(
                    raw_token,
                    settings.SECRET_KEY,
                    algorithms=['HS256'],
                    options={'verify_signature': False}
                )
                if payload.get('exp') and payload['exp'] < int(timezone.now().timestamp()):
                    raise AuthenticationFailed({'code': 'token_expired'})
            except jwt.PyJWTError:
                pass

            raise AuthenticationFailed({'code': 'token_invalid'})

        return self.get_user(validated_token), validated_token
