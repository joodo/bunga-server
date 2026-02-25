from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import requests
from django.core.cache import cache
from rest_framework import status, viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from server import models, serializers
from server.utils import network, bilibili as bili_utils


class BiliAccountViewSet(viewsets.ModelViewSet):
    queryset = models.BilibiliAccount.objects.all()
    lookup_field = "channel_id"
    serializer_class = serializers.BilibiliAccountSerializer
    permission_classes = [IsAdminUser]

    def get_object(self):
        instance = super().get_object()
        cache_key = "sess_checked:" + instance.channel_id
        if not instance.sess:
            return instance
        if cache.get(cache_key):
            return instance

        if bili_utils.keep_sess_fresh(instance):
            cache.set(cache_key, True, 7 * 24 * 3600)
        return instance


@api_view(["GET"])
@permission_classes([IsAdminUser])
def bilibili_qr(request: Request) -> Response:
    response = requests.get(
        "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
        headers={"User-Agent": network.user_agent},
    )
    if not response.ok:
        return Response(
            {
                "message": "generate qr code from bilibili failed",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    data = response.json()
    if data["code"] != 0:
        return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(data["data"])


@api_view(["GET"])
@permission_classes([IsAdminUser])
def bilibili_pull(request: Request) -> Response:
    qrcode_key = request.query_params.get("key")
    response = requests.get(
        f"https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}",
        headers={"User-Agent": network.user_agent},
    )
    if not response.ok:
        return Response(
            {
                "message": "pull qr status from bilibili failed",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    data = response.json()
    if data["code"] != 0:
        return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = data["data"]
    if data["code"] != 0:
        return Response(data)

    cookies = network.parse_set_cookie(response.headers["set-cookie"])
    data["sess"] = cookies["SESSDATA"]
    data["bili_jct"] = cookies["bili_jct"]
    return Response(data)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def bilibili_info(request: Request) -> Response:
    sess = request.query_params.get("sess")
    if not sess:
        return Response(
            {
                "err_code": -1,
                "message": '"sess" is required.',
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    force = "force" in request.GET

    try:
        info = get_bili_info(sess, force)
    except Exception as e:
        return Response(e.args[0], status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(info)


def get_bili_info(sess: str, force: bool = False):
    cache_key = "bili_info:" + sess
    cached_info = cache.get(cache_key, default=None)
    if not force and cached_info:
        return cached_info

    response = requests.get(
        "https://api.bilibili.com/x/web-interface/nav",
        headers={"User-Agent": network.user_agent},
        cookies={"SESSDATA": sess},
    )
    if not response.ok:
        raise Exception(
            {
                "err_code": 1,
                "message": response.text,
            }
        )

    data = response.json()
    if data["code"] != 0:
        raise Exception(
            {
                "err_code": 2,
                "message": data,
            }
        )

    def get_filename_from_url(url):
        path = urlparse(url).path
        filename = Path(path).stem
        return filename

    info = {
        "avatar": data["data"]["face"],
        "username": data["data"]["uname"],
        "vip": data["data"]["vipStatus"] == 1,
        "wbi": {
            "img_key": get_filename_from_url(data["data"]["wbi_img"]["img_url"]),
            "sub_key": get_filename_from_url(data["data"]["wbi_img"]["sub_url"]),
        },
    }

    now = datetime.now()
    end_of_day = (now + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    seconds_remaining = (end_of_day - now).total_seconds()
    cache.set(cache_key, info, int(seconds_remaining))
    return info
