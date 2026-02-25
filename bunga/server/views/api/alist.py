from pathlib import Path
from urllib.parse import urlparse

import requests
from rest_framework import status, viewsets
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.permissions import IsAdminUser
from rest_framework.decorators import permission_classes, api_view


from server import models, serializers
from server.utils import cached_function


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
    host = models.AListHost.get_solo().host
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
    )
    data = response.json()

    return Response(
        {
            "base_path": data["data"]["base_path"],
            "permission": (
                "admin" if data["data"]["role"] == 2 else data["data"]["permission"]
            ),
        }
    )


def _parse_host(host):
    parsed = urlparse(host)
    return f"{parsed.scheme}://{parsed.netloc}"


@cached_function(lambda host, username, _: f"alist:{username}@{host}")
def get_alist_token(host: str, username: str, password: str) -> str:
    host = _parse_host(host)
    response = requests.post(
        host + "/api/auth/login",
        {"Username": username, "Password": password},
    )
    if not response.ok:
        raise Exception(response.status_code)

    data = response.json()
    if data["code"] != 200:
        raise Exception(
            {
                "message": "alist login failed.",
                "detail": data,
            }
        )

    return data["data"]["token"]


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
