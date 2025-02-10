import json
from urllib.parse import urlparse

import requests

from django.http import HttpRequest, JsonResponse
from django.core.cache import cache
from rest_framework import generics, viewsets, status
from rest_framework.response import Response

from server.utils import tencent
from server.models import AListAccount, BilibiliAccount, ChatConfiguration
from server.utils import user_agent, parse_set_cookie, bilibili
from server import serializers, models


class ChatConfig(generics.RetrieveUpdateAPIView):
    serializer_class = serializers.ChatConfigurationSerializer

    def get_object(self):
        return models.ChatConfiguration.get_solo()


class ChannelViewSet(viewsets.ViewSet):
    def list(self, request: HttpRequest) -> Response:
        config = ChatConfiguration.get_solo()
        response = tencent.request(
            config,
            'group_open_http_svc/get_appid_group_list',
        )

        group_ids = [item['GroupId'] for item in response['GroupIdList']]
        response = tencent.request(
            config,
            'group_open_http_svc/get_group_info',
            {
                'GroupIdList': group_ids,
                'ResponseFilter': {
                    'GroupBaseInfoFilter': [
                        'GroupId',
                        'Name',
                        'FaceUrl',
                        'MemberNum',
                    ],
                },
            },
        )

        data = [{
            'group_id': item.get('GroupId'),
            'name': item.get('Name'),
            'avatar': item.get('FaceUrl'),
            'member_count': item.get('MemberNum'),
        } for item in response['GroupInfo']]
        return Response(data)

    def create(self, request: HttpRequest) -> Response:
        config = ChatConfiguration.get_solo()

        data = json.loads(request.body)
        response = tencent.request(
            config,
            'group_open_http_svc/create_group',
            {
                'Type': 'Private',
                'GroupId': data.get('group_id'),
                'Name': data.get('name'),
            },
        )

        match response.get('ErrorCode'):
            case 0:
                return Response({
                    'group_id': response.get('GroupId'),
                    'name': data.get('name'),
                }, status=status.HTTP_201_CREATED)
            case 10021 | 10025:
                return Response({
                    'group_id': response.get('ErrorInfo'),
                }, status=status.HTTP_400_BAD_REQUEST)
            case _:
                return Response({
                    'name': response.get('ErrorInfo'),
                }, status=status.HTTP_400_BAD_REQUEST)

    def retrieve(self, request: HttpRequest, pk=None) -> Response:
        config = ChatConfiguration.get_solo()
        group_ids = [pk]
        response = tencent.request(
            config,
            'group_open_http_svc/get_group_info',
            {
                'GroupIdList': group_ids,
                'ResponseFilter': {
                    'GroupBaseInfoFilter': [
                        'GroupId',
                        'Name',
                        'FaceUrl',
                        'MemberNum',
                    ],
                },
            },
        )

        data = [{
            'id': item.get('GroupId'),
            'name': item.get('Name'),
            'avatar': item.get('FaceUrl'),
            'member_count': item.get('MemberNum'),
        } for item in response['GroupInfo']]
        return Response(data[0])

    def partial_update(self, request: HttpRequest, pk=None):
        config = ChatConfiguration.get_solo()
        data = json.loads(request.body)
        response = tencent.request(
            config,
            'group_open_http_svc/modify_group_base_info',
            {
                'GroupId': pk,
                'Name': data.get('name'),
            },
        )

        if (response.get('ErrorCode') != 0):
            return Response({
                'detail': response.get('ErrorInfo'),
            }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'detail': 'success',
            }, status=status.HTTP_206_PARTIAL_CONTENT)

    def destroy(self, request: HttpRequest, pk=None) -> Response:
        if not pk:
            return Response({
                'detail': 'group_id is required.',
            }, status=status.HTTP_400_BAD_REQUEST)

        config = ChatConfiguration.get_solo()
        response = tencent.request(
            config,
            'group_open_http_svc/destroy_group',
            {
                'GroupId': pk,
            },
        )

        if (response.get('ErrorCode') != 0):
            return Response({
                'detail': response.get('ErrorInfo'),
            }, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response({
                'detail': 'success',
            }, status=status.HTTP_204_NO_CONTENT)


class BiliAccountViewSet(viewsets.ModelViewSet):
    queryset = BilibiliAccount.objects.all()
    lookup_field = 'channel_id'
    serializer_class = serializers.BilibiliAccountSerializer

    def get_object(self):
        instance = super().get_object()
        cache_key = 'sess_checked:' + instance.channel_id
        if not instance.sess:
            return instance
        if cache.get(cache_key):
            return instance

        if bilibili.keep_sess_fresh(instance):
            cache.set(cache_key, True, 7*24*3600)
        return instance


class AListAccountViewSet(viewsets.ModelViewSet):
    queryset = AListAccount.objects.all()
    lookup_field = 'channel_id'
    serializer_class = serializers.AListAccountSerializer


def bilibili_qr(request: HttpRequest) -> JsonResponse:
    response = requests.get(
        'https://passport.bilibili.com/x/passport-login/web/qrcode/generate',
        headers={'User-Agent': user_agent},
    )
    if (not response.ok):
        return JsonResponse({
            'message': 'generate qr code from bilibili failed',
        }, status=500)

    data = response.json()
    if (data['code'] != 0):
        return JsonResponse(data, status=500)

    return JsonResponse(data['data'])


def bilibili_pull(request: HttpRequest) -> JsonResponse:
    qrcode_key = request.GET.get('key')
    response = requests.get(
        f'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}',
        headers={'User-Agent': user_agent},
    )
    if (not response.ok):
        return JsonResponse({
            'message': 'pull qr status from bilibili failed',
        }, status=500)

    data = response.json()
    if (data['code'] != 0):
        return JsonResponse(data, status=500)

    data = data['data']
    if (data['code'] != 0):
        return JsonResponse(data)

    cookies = parse_set_cookie(response.headers['set-cookie'])
    data['sess'] = cookies['SESSDATA']
    data['bili_jct'] = cookies['bili_jct']
    return JsonResponse(data)


def bilibili_info(request: HttpRequest) -> JsonResponse:
    sess = request.GET.get('sess')
    if not sess:
        return JsonResponse({
            'err_code': -1,
            'message': '"sess" is required.',
        }, status=400)

    cache_key = 'bili_info:' + sess
    if 'force' not in request.GET:
        cached_info = cache.get(cache_key, default=None)
        if cached_info:
            return JsonResponse(cached_info)

    response = requests.get(
        'https://api.bilibili.com/x/web-interface/nav',
        headers={'User-Agent': user_agent},
        cookies={'SESSDATA': request.GET['sess']},
    )
    if (not response.ok):
        return JsonResponse({
            'err_code': 1,
            'message': response.text,
        }, status=500)

    data = response.json()
    if (data['code'] != 0):
        return JsonResponse({
            'err_code': 2,
            'message': data,
        }, status=500)

    info = {
        'avatar': data['data']['face'],
        'username': data['data']['uname'],
        'vip': data['data']['vipStatus'] == 1,
        'wbi': {
            'img_key': data['data']['wbi_img']['img_url'],
            'sub_key': data['data']['wbi_img']['sub_url'],
        },
    }
    cache.set(cache_key, info)
    return JsonResponse(info)


def alist_info(request: HttpRequest) -> JsonResponse:
    host = request.GET.get('host')
    if not host:
        return JsonResponse({
            'err_code': -1,
            'message': '"host" is required.',
        }, status=400)

    host = __parse_host(host)
    response = requests.get(host + '/api/public/settings')
    if not response.ok:
        return JsonResponse({
            'err_code': 1,
            'message': response.text,
        }, status=400)

    data = response.json()
    if data['code'] != 200:
        return JsonResponse({
            'err_code': 2,
            'message': data,
        }, status=400)

    result = {
        'avatar': data['data']['logo'],
        'site_name': data['data']['site_title'],
    }
    return JsonResponse(result)


def alist_user_info(request: HttpRequest) -> JsonResponse:
    host = models.SiteConfiguration.get_solo().alist_host
    username = request.GET.get('username')
    password = request.GET.get('password')
    if not (host and username and password):
        return JsonResponse({
            'err_code': -1,
            'message': '"username" and "password" are required.',
        }, status=400)

    host = __parse_host(host)
    response = requests.post(
        host + '/api/auth/login',
        {'Username': username, 'Password': password},
    )
    if not response.ok:
        return JsonResponse({
            'err_code': 1,
            'message': response.text,
        }, status=400)

    data = response.json()
    if data['code'] != 200:
        return JsonResponse({
            'err_code': 2,
            'message': data,
        }, status=400)

    token = data['data']['token']
    response = requests.get(
        host + '/api/me',
        headers={'Authorization': token},
    )

    data = response.json()

    return JsonResponse({
        'base_path': data['data']['base_path'],
        'permission': 'admin' if data['data']['role'] == 2 else data['data']['permission'],
    })


def __parse_host(host):
    parsed = urlparse(host)
    return f'{parsed.scheme}://{parsed.netloc}'
