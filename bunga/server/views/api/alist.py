from pathlib import Path
import hashlib
from urllib.parse import urlparse

import requests
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import permission_classes, api_view


from server import models, serializers
from server.utils import cached_function


ALIST_REQUEST_TIMEOUT = 8
ALIST_STATIC_HASH_SALT = "https://github.com/alist-org/alist"


class AListAccountViewSet(viewsets.ModelViewSet):
    queryset = models.AListAccount.objects.all()
    lookup_field = "channel_id"
    serializer_class = serializers.AListAccountSerializer
    permission_classes = [IsAdminUser]


@api_view(["GET"])
@permission_classes([IsAdminUser])
def alist_info(request: Request) -> Response:
    host = request.query_params.get("host")
    if not host:
        return Response(
            {
                "err_code": -1,
                "message": '"host" is required.',
            },
            status=400,
        )

    host = _parse_host(host)
    response = requests.get(host + "/api/public/settings")
    if not response.ok:
        return Response(
            {
                "err_code": 1,
                "message": response.text,
            },
            status=400,
        )

    data = response.json()
    if data["code"] != 200:
        return Response(
            {
                "err_code": 2,
                "message": data,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    result = {
        "avatar": data["data"]["logo"],
        "site_name": data["data"]["site_title"],
    }
    return Response(result)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def alist_user_info(request: Request) -> Response:
    host = _parse_host(models.AListHost.get_solo().host)
    username = request.query_params.get("username")
    password = request.query_params.get("password")
    if not (host and username and password):
        return Response(
            {
                "err_code": -1,
                "message": '"username" and "password" are required.',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token = get_alist_token(host, username, password)
    except Exception as e:
        return Response(
            {
                "detail": str(e),
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = requests.get(
        host + "/api/me",
        headers={"Authorization": token},
        timeout=ALIST_REQUEST_TIMEOUT,
    )

    if not response.ok:
        return Response(
            {
                "detail": f"alist /api/me request failed: {response.status_code}",
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        data = response.json()
    except ValueError:
        return Response(
            {
                "detail": {
                    "message": "alist /api/me returned invalid json.",
                    "raw": response.text,
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    if data.get("code") != 200 or not isinstance(data.get("data"), dict):
        return Response(
            {
                "detail": {
                    "message": "alist /api/me failed.",
                    "raw": data,
                },
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    me = data["data"]
    base_path = me.get("base_path")
    if not isinstance(base_path, str) or not base_path:
        base_path = "/"

    if _is_admin_user(me):
        permission = "admin"
    else:
        permission = _extract_effective_permission(me)
        if permission is None:
            return Response(
                {
                    "detail": {
                        "message": "Cannot parse AList permission from /api/me response.",
                        "raw": data,
                    },
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    return Response(
        {
            "base_path": base_path,
            "permission": permission,
        }
    )


def _parse_host(host):
    parsed = urlparse(host)
    return f"{parsed.scheme}://{parsed.netloc}"


def _as_int(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return None


def _normalize_role_ids(role_value):
    if isinstance(role_value, list):
        role_ids = set()
        for item in role_value:
            role_id = _as_int(item)
            if role_id is not None:
                role_ids.add(role_id)
        return role_ids

    role_id = _as_int(role_value)
    if role_id is None:
        return set()
    return {role_id}


def _is_admin_user(me):
    role_names = me.get("role_names")
    if isinstance(role_names, list):
        for role_name in role_names:
            if isinstance(role_name, str) and role_name.lower() == "admin":
                return True

    role_ids = _normalize_role_ids(me.get("role"))
    return 2 in role_ids


def _extract_effective_permission(me):
    # Newer AList versions provide path-scoped permissions in /api/me.
    # For this status page, merge all scopes into one effective bitmask.
    permissions = me.get("permissions")
    if isinstance(permissions, list):
        merged = 0
        for entry in permissions:
            if not isinstance(entry, dict):
                continue
            permission = _as_int(entry.get("permission"))
            if permission is not None:
                merged |= permission
        return merged

    # Fallback for older AList versions. Docs mark this field as deprecated.
    return _as_int(me.get("permission"))


@cached_function(lambda host, username, _: f"alist:{username}@{host}")
def get_alist_token(host: str, username: str, password: str) -> str:
    host = _parse_host(host)
    static_hash = hashlib.sha256(
        f"{password}-{ALIST_STATIC_HASH_SALT}".encode("utf-8")
    ).hexdigest()

    login_attempts = [
        {
            "url": host + "/api/auth/login",
            "kwargs": {"json": {"username": username, "password": password}},
            "name": "login-json-lowercase",
        },
        {
            "url": host + "/api/auth/login",
            "kwargs": {"data": {"username": username, "password": password}},
            "name": "login-form-lowercase",
        },
        {
            "url": host + "/api/auth/login",
            "kwargs": {"data": {"Username": username, "Password": password}},
            "name": "login-form-uppercase",
        },
        {
            "url": host + "/api/auth/login/hash",
            "kwargs": {"json": {"username": username, "password": static_hash}},
            "name": "login-hash-json",
        },
    ]

    last_error = None
    for attempt in login_attempts:
        try:
            response = requests.post(
                attempt["url"],
                timeout=ALIST_REQUEST_TIMEOUT,
                **attempt["kwargs"],
            )
        except requests.RequestException as exc:
            last_error = {
                "attempt": attempt["name"],
                "message": str(exc),
            }
            continue

        if not response.ok:
            last_error = {
                "attempt": attempt["name"],
                "status_code": response.status_code,
                "message": "http request failed",
            }
            continue

        try:
            data = response.json()
        except ValueError:
            last_error = {
                "attempt": attempt["name"],
                "message": "invalid json response",
                "raw": response.text,
            }
            continue

        if data.get("code") == 200 and isinstance(data.get("data"), dict):
            token = data["data"].get("token")
            if token:
                return token

        last_error = {
            "attempt": attempt["name"],
            "message": "alist login failed",
            "raw": data,
        }

    raise Exception(
        {
            "message": "alist login failed.",
            "detail": last_error,
        }
    )


@cached_function(lambda path, _: f"alist-thumb:{hash(path)}")
def get_alist_thumb(path: str, channel_id: str) -> requests.models.Response:
    channel = models.Channel.objects.get(pk=channel_id)

    alist_host = models.AListHost.get_solo()

    alist_account = models.AListAccount.objects.get(channel=channel)
    alist_token = get_alist_token(
        alist_host.host, alist_account.username, alist_account.password
    )

    host = _parse_host(alist_host.host)
    # walkthrough: alist bug cause user without '/' as
    # root path cannot fetch thumbnail url by 'fs/get/', so use 'fs/list/' here
    dir = str(Path(path).parent)
    name = Path(path).name
    response = requests.post(
        host + "/api/fs/list",
        json={"path": dir},
        headers={
            "Authorization": alist_token,
            "content-type": "application/json",
        },
    )
    if not response.ok:
        raise Exception(response.status_code)

    data = response.json()
    if data["code"] != 200:
        raise Exception(
            {
                "message": "get file info failed.",
                "detail": data,
            }
        )

    url = next(i["thumb"] for i in data["data"]["content"] if i["name"] == name)

    return requests.get(
        url,
        headers={"Authorization": alist_token},
    )
