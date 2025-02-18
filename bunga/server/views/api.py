from urllib.parse import urlparse

import requests

from django.core.cache import cache
from django.contrib.auth import authenticate
from django.contrib.auth.models import User, Permission
from django.core.exceptions import ObjectDoesNotExist
from rest_framework import generics, viewsets, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework.authtoken.models import Token

from server.utils import network, bilibili, tencent, cached_function
from server import serializers, models


class Site(generics.RetrieveUpdateAPIView):
    serializer_class = serializers.SiteSerializer
    permission_classes = [IsAdminUser]

    def get_object(self):
        return models.Site.get_solo()


class AListHost(generics.RetrieveUpdateAPIView):
    serializer_class = serializers.AlistHostSerializer
    permission_classes = [IsAdminUser]

    def get_object(self):
        return models.AListHost.get_solo()


class IMKey(generics.RetrieveUpdateAPIView):
    serializer_class = serializers.IMKeySerializer
    permission_classes = [IsAdminUser]

    def get_object(self):
        return models.IMKey.get_solo()


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = models.Channel.objects.all()
    serializer_class = serializers.ChannelSerializer
    permission_classes = [IsAdminUser]

    def list(self, request: Request) -> Response:
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        local_data = serializer.data

        config = models.IMKey.get_solo()

        group_ids = [item['channel_id'] for item in local_data]
        if not group_ids:
            return Response([])

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
            'channel_id': item.get('GroupId'),
            'name': item.get('Name'),
            'avatar': item.get('FaceUrl'),
            'member_count': item.get('MemberNum'),
        } for item in response['GroupInfo']]
        return Response(data)

    def create(self, request: Request) -> Response:
        config = models.IMKey.get_solo()

        data = request.data
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
                data = {
                    'group_id': response.get('GroupId'),
                    'name': data.get('name'),
                }
            case 10021 | 10025:
                return Response({
                    'group_id': response.get('ErrorInfo'),
                }, status=status.HTTP_400_BAD_REQUEST)
            case _:
                return Response({
                    'name': response.get('ErrorInfo'),
                }, status=status.HTTP_400_BAD_REQUEST)

        new_channel = models.Channel.objects.create(
            channel_id=data.get('group_id'))

        return Response(data, status=status.HTTP_201_CREATED)

    def retrieve(self, request: Request, pk=None) -> Response:
        instance = self.get_object()
        data = _get_channel_info(instance.channel_id)
        serializer = self.get_serializer(instance)
        return Response(data | serializer.data)

    def partial_update(self, request: Request, pk=None):
        instance = self.get_object()

        config = models.IMKey.get_solo()
        data = request.data
        response = tencent.request(
            config,
            'group_open_http_svc/modify_group_base_info',
            {
                'GroupId': instance.channel_id,
                'Name': data.get('name'),
            },
        )

        if (response.get('ErrorCode') != 0):
            return Response({
                'detail': response.get('ErrorInfo'),
            }, status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response({
            'detail': 'success',
        }, status=status.HTTP_206_PARTIAL_CONTENT)

    def destroy(self, request: Request, pk=None) -> Response:
        if not pk:
            return Response({
                'detail': 'group_id is required.',
            }, status=status.HTTP_400_BAD_REQUEST)

        config = models.IMKey.get_solo()
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

        return super().destroy(request, pk)


class BiliAccountViewSet(viewsets.ModelViewSet):
    queryset = models.BilibiliAccount.objects.all()
    lookup_field = 'channel_id'
    serializer_class = serializers.BilibiliAccountSerializer
    permission_classes = [IsAdminUser]

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
    queryset = models.AListAccount.objects.all()
    lookup_field = 'channel_id'
    serializer_class = serializers.AListAccountSerializer
    permission_classes = [IsAdminUser]


@permission_classes([IsAdminUser])
@api_view(['GET'])
def bilibili_qr(request: Request) -> Response:
    response = requests.get(
        'https://passport.bilibili.com/x/passport-login/web/qrcode/generate',
        headers={'User-Agent': network.user_agent},
    )
    if (not response.ok):
        return Response({
            'message': 'generate qr code from bilibili failed',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = response.json()
    if (data['code'] != 0):
        return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    return Response(data['data'])


@permission_classes([IsAdminUser])
@api_view(['GET'])
def bilibili_pull(request: Request) -> Response:
    qrcode_key = request.query_params.get('key')
    response = requests.get(
        f'https://passport.bilibili.com/x/passport-login/web/qrcode/poll?qrcode_key={qrcode_key}',
        headers={'User-Agent': network.user_agent},
    )
    if (not response.ok):
        return Response({
            'message': 'pull qr status from bilibili failed',
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = response.json()
    if (data['code'] != 0):
        return Response(data, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = data['data']
    if (data['code'] != 0):
        return Response(data)

    cookies = network.parse_set_cookie(response.headers['set-cookie'])
    data['sess'] = cookies['SESSDATA']
    data['bili_jct'] = cookies['bili_jct']
    return Response(data)


@permission_classes([IsAdminUser])
@api_view(['GET'])
def bilibili_info(request: Request) -> Response:
    sess = request.query_params.get('sess')
    if not sess:
        return Response({
            'err_code': -1,
            'message': '"sess" is required.',
        }, status=status.HTTP_400_BAD_REQUEST)

    cache_key = 'bili_info:' + sess
    if 'force' not in request.GET:
        cached_info = cache.get(cache_key, default=None)
        if cached_info:
            return Response(cached_info)

    response = requests.get(
        'https://api.bilibili.com/x/web-interface/nav',
        headers={'User-Agent': network.user_agent},
        cookies={'SESSDATA': request.GET['sess']},
    )
    if (not response.ok):
        return Response({
            'err_code': 1,
            'message': response.text,
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    data = response.json()
    if (data['code'] != 0):
        return Response({
            'err_code': 2,
            'message': data,
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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
    return Response(info)


@permission_classes([IsAdminUser])
@api_view(['GET'])
def alist_info(request: Request) -> Response:
    host = request.query_params.get('host')
    if not host:
        return Response({
            'err_code': -1,
            'message': '"host" is required.',
        }, status=400)

    host = _parse_host(host)
    response = requests.get(host + '/api/public/settings')
    if not response.ok:
        return Response({
            'err_code': 1,
            'message': response.text,
        }, status=400)

    data = response.json()
    if data['code'] != 200:
        return Response({
            'err_code': 2,
            'message': data,
        }, status=status.HTTP_400_BAD_REQUEST)

    result = {
        'avatar': data['data']['logo'],
        'site_name': data['data']['site_title'],
    }
    return Response(result)


@permission_classes([IsAdminUser])
@api_view(['GET'])
def alist_user_info(request: Request) -> Response:
    host = models.AListHost.get_solo().host
    username = request.query_params.get('username')
    password = request.query_params.get('password')
    if not (host and username and password):
        return Response({
            'err_code': -1,
            'message': '"username" and "password" are required.',
        }, status=status.HTTP_400_BAD_REQUEST)

    try:
        token = _get_alist_token(host, username, password)
    except Exception as e:
        return Response({
            'detail': str(e),
        }, status=status.HTTP_400_BAD_REQUEST)

    print(token)
    response = requests.get(
        host + '/api/me',
        headers={'Authorization': token},
    )
    data = response.json()

    return Response({
        'base_path': data['data']['base_path'],
        'permission': 'admin' if data['data']['role'] == 2 else data['data']['permission'],
    })


@api_view(['POST'])
@permission_classes([AllowAny])
# username, password, channel_id
def register(request: Request) -> Response:
    serializer = serializers.RegisterPayloadSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400)
    payload = serializer.validated_data()

    try:
        channel = models.Channel.get(channel_id=payload['channel_id'])
    except ObjectDoesNotExist:
        return Response({
            'channel_id': 'Channel does not exist.',
        }, status=status.HTTP_404_NOT_FOUND)
    permission = Permission.objects.get(
        codename=f'channel_{channel.channel_id}')

    user_exists = User.objects.filter(username=payload['username']).exists()
    if not user_exists:
        if not channel.allow_new_client:
            return Response({
                'channel_id': 'Channel does not allow new client.',
            }, status=status.HTTP_403_FORBIDDEN)
        else:
            user = User.objects.create_user(
                payload['username'], None, payload['password'])
            user.user_permissions.add(permission)
            user.save()
            status_code = status.HTTP_201_CREATED
    else:
        user = authenticate(
            username=payload['username'], password=payload['password'])
        if user is None:
            return Response({
                'password': 'Password is not correct.',
            }, status=status.HTTP_401_UNAUTHORIZED)
        else:
            if not user.has_perm(f'server.{permission.codename}'):
                if not channel.allow_new_client:
                    return Response({
                        'channel_id': 'Channel does not allow new client.',
                    }, status=status.HTTP_403_FORBIDDEN)
                else:
                    user.user_permissions.add(permission)
                    user.save()
                    status_code = status.HTTP_200_OK
            else:
                status_code = status.HTTP_200_OK

    data = {
        'token': Token.objects.get_or_create(user=user),
    }

    data['channel'] = _get_channel_info(channel.channel_id)

    im_key = models.IMKey.get_solo()
    data['chat'] = {
        'service': 'tencent',
        'app_id':  im_key.tencent_app_id,
        'user_sig': tencent.generate_user_sig(im_key),
    }

    data['voice_call'] = {
        'service': 'agora',
        'key': models.VoiceKey.get_solo().agora_key,
    }

    bilibili = models.BilibiliAccount.objects.get(channel=channel)
    data['bilibili'] = {
        'sess': bilibili.sess
    }

    alist_host = models.AListHost.get_solo()
    alist_account = models.AListAccount.objects.get(channel=channel)
    data['alist'] = {
        'host': alist_host.host,
        'token': _get_alist_token(alist_host.host, alist_account.username, alist_account.password),
    }

    return Response(data, status=status_code)


@cached_function(lambda channel_id: f'channel:{channel_id}')
def _get_channel_info(channel_id: str) -> dict:
    config = models.IMKey.get_solo()
    response = tencent.request(
        config,
        'group_open_http_svc/get_group_info',
        {
            'GroupIdList': [channel_id],
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

    item = response['GroupInfo'][0]
    return {
        'id': item.get('GroupId'),
        'name': item.get('Name'),
        'avatar': item.get('FaceUrl'),
        'member_count': item.get('MemberNum'),
    }


@cached_function(lambda host, username, _: f'alist:{username}@{host}')
def _get_alist_token(host: str, username: str, password: str) -> str:
    host = _parse_host(host)
    response = requests.post(
        host + '/api/auth/login',
        {'Username': username, 'Password': password},
    )
    if not response.ok:
        raise Exception(response.text)

    data = response.json()
    if data['code'] != 200:
        raise Exception(data)

    return data['data']['token']


def _parse_host(host):
    parsed = urlparse(host)
    return f'{parsed.scheme}://{parsed.netloc}'
