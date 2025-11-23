# PEP-8

import os
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from dataclasses import asdict

from django.shortcuts import get_object_or_404
import requests

from django import http
from django.http import HttpResponse
from django.core.cache import cache
from django.contrib.auth import authenticate
from django.contrib.auth.models import User, Permission
from rest_framework import generics, viewsets, status, mixins
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import action, permission_classes, api_view
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from channels.layers import get_channel_layer
from asgiref.sync import sync_to_async

from server import serializers, models
from server.utils import (network, bilibili as bili_utils, tencent, agora,
                          cached_function, auto_validated, async_action)
from server.channel_cache import ChannelCache, ChannelStatus, UserInfo
from server.models import dataclasses
from utils.log import logger


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


class VoiceKey(generics.RetrieveUpdateAPIView):
    serializer_class = serializers.VoiceKeySerializer
    permission_classes = [IsAdminUser]

    def get_object(self):
        return models.VoiceKey.get_solo()


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = models.Channel.objects.all()
    serializer_class = serializers.ChannelSerializer

    @permission_classes([IsAdminUser])
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

    @permission_classes([IsAdminUser])
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

    @permission_classes([IsAdminUser])
    def retrieve(self, request: Request, pk=None) -> Response:
        instance = self.get_object()
        data = _get_channel_info(instance.channel_id)
        serializer = self.get_serializer(instance)
        return Response(data | serializer.data)

    @permission_classes([IsAdminUser])
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

    @permission_classes([IsAdminUser])
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

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[AllowAny],
        serializer_class=serializers.RegisterPayloadSerializer,
    )
    @auto_validated
    def register(self, validated, request: Request, pk=None) -> Response:
        config = models.IMKey.get_solo()

        def register_user() -> User:
            return User.objects.create_user(
                validated['username'],
                None,
                validated['password'],
            )

        def join_user_to_channel(user: User) -> None:
            user.user_permissions.add(permission)
            user.save()

        # Check if channel exist
        try:
            channel = self.get_object()
        except http.Http404:
            return Response({
                'channel_id': 'Channel does not exist.',
            }, status=status.HTTP_404_NOT_FOUND)
        permission = Permission.objects.get(
            codename=f'channel_{channel.channel_id}')

        user_exists = User.objects.filter(
            username=validated['username']).exists()
        if not user_exists:
            # User not exist and channel forbid join
            if not channel.allow_new_client:
                return Response({
                    'channel_id': 'Channel does not allow new client.',
                }, status=status.HTTP_403_FORBIDDEN)
            # Else create user and join it!
            else:
                try:
                    user = register_user()
                    join_user_to_channel(user)
                except Exception as e:
                    return Response({
                        'detail': str(e),
                    }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                status_code = status.HTTP_201_CREATED
        else:
            user = authenticate(
                username=validated['username'], password=validated['password'])
            if user is None:
                # Password not corrent
                return Response({
                    'password': 'Password is not correct.',
                }, status=status.HTTP_401_UNAUTHORIZED)
            else:
                if not user.has_perm(f'server.{permission.codename}'):
                    # Not in channel but channel forbid join...
                    if not channel.allow_new_client:
                        return Response({
                            'channel_id': 'Channel does not allow new client.',
                        }, status=status.HTTP_403_FORBIDDEN)
                    # Join it!
                    else:
                        try:
                            join_user_to_channel(user)
                        except Exception as e:
                            return Response({
                                'detail': str(e),
                            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                        status_code = status.HTTP_200_OK
                else:
                    # User exist and already join channel, do nothing
                    status_code = status.HTTP_200_OK

        refresh = RefreshToken.for_user(user)
        data = {
            'token': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            },
        }

        data['channel'] = _get_channel_info(channel.channel_id)

        im_key = models.IMKey.get_solo()
        data['im'] = {
            'service': 'tencent',
            'app_id':  im_key.tencent_app_id,
            'user_id': validated['username'],
            'user_sig': tencent.generate_user_sig(config, validated['username']),
        }

        try:
            agoraInfo = models.VoiceKey.get_solo()
            data['voice_call'] = {
                'service': 'agora',
                'key': agoraInfo.agora_key,
                'channel_token': agora.generateToken(
                    agoraInfo.agora_key,
                    agoraInfo.agora_certification,
                    channel.channel_id,
                    agora.uidFromName(validated['username']),
                ),
            }
        except:
            data['voice_call'] = None

        try:
            bilibili = models.BilibiliAccount.objects.get(channel=channel)
            sess = bilibili.sess

            info = _get_bili_info(sess)
            mixinKey = bili_utils.get_mixin_key(**info['wbi'])

            data['bilibili'] = {
                'sess': sess,
                'mixin_key': mixinKey,
            }
        except:
            data['bilibili'] = None

        try:
            alist_host = models.AListHost.get_solo()
            alist_account = models.AListAccount.objects.get(channel=channel)
            data['alist'] = {
                'host': alist_host.host,
                'token': _get_alist_token(alist_host.host, alist_account.username, alist_account.password),
            }
        except:
            data['alist'] = None

        return Response(data, status=status_code)

    @action(
        detail=True,
        methods=['post'],
        serializer_class=serializers.AlohaPayloadSerializer
    )
    @auto_validated
    def aloha(self, validated, request: Request, pk=None):
        validated['id'] = request.user.username

        channel = self.get_object()
        channel_id = channel.channel_id

        channel_cache = ChannelCache(channel_id)
        user_info = UserInfo(**validated)
        channel_cache.upsert_user(user_info)

        projection = channel_cache.current_projection
        if not projection:
            return Response({'current_projection': None}, status=status.HTTP_200_OK)

        record = models.VideoRecord.objects.filter(
            channel=channel, record_id=projection.record_id,
        ).first()
        record_data = serializers.VideoRecordSerializer(
            record).data
        return Response({
            'current_projection': {
                'sharer': asdict(projection.sharer),
                'video_record': record_data,
            }}, status=status.HTTP_200_OK)

    @action(
        detail=True,
        methods=['post'],
        serializer_class=serializers.VideoRecordSerializer
    )
    @auto_validated
    @async_action
    async def project(self, validated, request: Request, pk=None):
        """
        Request: VideoRecord
        Response: Nothing, but will send message through ws
        """
        channel_layer = get_channel_layer()

        channel = await sync_to_async(self.get_object)()
        channel_id = channel.channel_id
        validated['channel_id'] = channel_id

        channel_cache = ChannelCache(channel_id)

        current_user = channel_cache.get_user_info(request.user.username)
        if current_user is None:
            logger.warning(f'Unknown user: {request.user.username}')
            current_user = dataclasses.UserInfo(
                id=request.user.username, name='unknown')

        record_id = validated['record_id']

        if channel_cache.current_projection:
            current_video_record = await models.VideoRecord.objects.aget(
                channel=channel,
                record_id=channel_cache.current_projection.record_id,
            )

            if record_id == current_video_record.record_id:
                # Playing record_id already, tell sender to follow
                client_channel_name = channel_cache.get_channel_name(
                    request.user.username)
                if client_channel_name is not None:
                    await channel_layer.send(
                        channel_cache.get_channel_name(request.user.username),
                        {
                            'type': 'start.projection',
                            'sender': current_user,
                            'video_record': current_video_record,
                        }
                    )
                return Response(status=status.HTTP_200_OK)

            # Playing something but not record_id, save position from cache to db first
            current_video_record.position = channel_cache.current_status.position
            await current_video_record.asave()

        channel_cache.current_projection = dataclasses.Projection(
            record_id=record_id, sharer=current_user)

        existed = await models.VideoRecord.objects.filter(
            channel=channel,
            record_id=record_id,
        ).afirst()
        if existed:
            # Video has been played before
            channel_cache.current_status = ChannelStatus(
                position=existed.position
            )

            # Tell others in room
            await channel_layer.group_send(
                f'room_{channel_id}',
                {
                    'type': 'start.projection',
                    'sender': current_user,
                    'video_record': existed,
                }
            )

            return Response(status=status.HTTP_200_OK)
        else:
            # Brandy-new projection!
            channel_cache.current_status = ChannelStatus()

            instance = await models.VideoRecord.objects.acreate(**validated)

            # Tell others in room
            await channel_layer.group_send(
                f'room_{channel_id}',
                {
                    'type': 'start.projection',
                    'sender': current_user,
                    'video_record': instance,
                }
            )

            return Response(status=status.HTTP_201_CREATED)

    @action(
        url_path='alist-thumbnail',
        detail=True,
        methods=['get'],
        permission_classes=[AllowAny],
    )
    def alist_thumbnail(self, request: Request, pk=None) -> Response:
        try:
            requests_response = _get_alist_thumb(
                request.query_params.get('path'),
                pk,
            )
        except Exception as e:
            return Response({
                'detail': str(e),
            }, status=status.HTTP_400_BAD_REQUEST)

        return _convert_to_http_response(requests_response)


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

        if bili_utils.keep_sess_fresh(instance):
            cache.set(cache_key, True, 7*24*3600)
        return instance


class AListAccountViewSet(viewsets.ModelViewSet):
    queryset = models.AListAccount.objects.all()
    lookup_field = 'channel_id'
    serializer_class = serializers.AListAccountSerializer
    permission_classes = [IsAdminUser]


class VideoRecordViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    """
    Call GET detail when join room;
    Call POST list/project when project video to room
    """
    serializer_class = serializers.VideoRecordSerializer
    lookup_field = 'record_id'
    lookup_url_kwarg = 'record_id'

    async def get_queryset(self):
        channel_id = self.kwargs['channel_id']
        return models.VideoRecord.objects.filter(channel_id=channel_id)

    @action(detail=False, methods=['post'])
    async def project(self, request, *args, **kwargs):
        """
        Response: VideoRecord + "position_sec" field (float)
        """
        serializer = self.get_serializer(data=request.data)
        # Make sure projection is valid
        serializer.is_valid(raise_exception=True)

        channel_layer = get_channel_layer()

        channel_id = self.kwargs['channel_id']
        channel_cache = ChannelCache(channel_id)

        record_id = serializer.validated_data.get('record_id')

        if record_id == channel_cache.current_projection:
            # Playing record_id already

            # TODO: ws tell others to wait

            current_video_record = await self.get_queryset().aget(record_id=record_id)
            data = self.get_serializer(current_video_record).data
            # Read status from cache, not db
            data['position_sec'] = channel_cache.current_status.current_position.total_seconds()
            return Response(data, status=status.HTTP_200_OK)

        if channel_cache.current_projection:
            # Playing something but not record_id, save position from cache to db first
            current_video_record = await self.get_queryset().aget(
                record_id=channel_cache.current_projection
            )
            await models.PlayStatus.objects.aupdate_or_create(
                video_record=current_video_record,
                defaults={
                    'position': channel_cache.current_status.current_position,
                }
            )

        channel_cache.current_projection = record_id

        existed = await self.get_queryset().filter(record_id=record_id).afirst()
        if existed:
            # Video has been played before
            channel_cache.current_status = ChannelStatus(
                position=instance.play_status.position
            )

            # Tell others in room
            await channel_layer.group_send(
                f'channel_{channel_id}',
                {
                    'type': 'start.projection',
                    'request': request,
                    'video_record': existed,
                }
            )

            data = self.get_serializer(existed).data
            return Response(data, status=status.HTTP_200_OK)
        else:
            # Brandy-new projection!
            channel_cache.current_status = ChannelStatus()

            instance = await serializer.asave()

            # Tell others in room
            await channel_layer.group_send(
                f'channel_{channel_id}',
                {
                    'type': 'start.projection',
                    'request': request,
                    'video_record': instance,
                }
            )

            data = self.get_serializer(instance).data
            return Response(data, status=status.HTTP_201_CREATED)


class SubtitleCreateView(generics.CreateAPIView):
    serializer_class = serializers.SubtitleSerializer

    def perform_create(self, serializer):
        record_id = self.kwargs['record_id']
        channel_id = self.kwargs['channel_id']
        channel = get_object_or_404(models.Channel, channel_id=channel_id)
        record = get_object_or_404(
            models.VideoRecord,
            channel=channel,
            record_id=record_id,
        )

        models.Subtitle.objects.filter(record=record).delete()

        uploaded_file = serializer.validated_data['file']
        name_without_ext, _ = os.path.splitext(uploaded_file.name)
        serializer.save(
            record=record,
            uploader=self.request.user,
            name=name_without_ext,
        )


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

    force = 'force' in request.GET

    try:
        info = _get_bili_info(sess, force)
    except Exception as e:
        return Response(e.args[0], status=status.HTTP_500_INTERNAL_SERVER_ERROR)

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

    response = requests.get(
        host + '/api/me',
        headers={'Authorization': token},
    )
    data = response.json()

    return Response({
        'base_path': data['data']['base_path'],
        'permission': 'admin' if data['data']['role'] == 2 else data['data']['permission'],
    })


def _get_bili_info(sess: str, force: bool = False):
    cache_key = 'bili_info:' + sess
    cached_info = cache.get(cache_key, default=None)
    if not force and cached_info:
        return cached_info

    response = requests.get(
        'https://api.bilibili.com/x/web-interface/nav',
        headers={'User-Agent': network.user_agent},
        cookies={'SESSDATA': sess},
    )
    if (not response.ok):
        raise Exception({
            'err_code': 1,
            'message': response.text,
        })

    data = response.json()
    if (data['code'] != 0):
        raise Exception({
            'err_code': 2,
            'message': data,
        })

    def get_filename_from_url(url):
        path = urlparse(url).path
        filename = Path(path).stem
        return filename

    info = {
        'avatar': data['data']['face'],
        'username': data['data']['uname'],
        'vip': data['data']['vipStatus'] == 1,
        'wbi': {
            'img_key': get_filename_from_url(data['data']['wbi_img']['img_url']),
            'sub_key': get_filename_from_url(data['data']['wbi_img']['sub_url']),
        },
    }

    now = datetime.now()
    end_of_day = (now + timedelta(days=1)).replace(hour=0,
                                                   minute=0,
                                                   second=0,
                                                   microsecond=0)
    seconds_remaining = (end_of_day - now).total_seconds()
    cache.set(cache_key, info, seconds_remaining)
    return info


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
        raise Exception(response.status_code)

    data = response.json()
    if data['code'] != 200:
        raise Exception({
            'message': 'alist login failed.',
            'detail': data,
        })

    return data['data']['token']


@cached_function(lambda path, _: f'alist-thumb:{hash(path)}')
def _get_alist_thumb(path: str, channel_id: str) -> requests.models.Response:
    channel = models.Channel.objects.get(pk=channel_id)

    alist_host = models.AListHost.get_solo()

    alist_account = models.AListAccount.objects.get(channel=channel)
    alist_token = _get_alist_token(
        alist_host.host, alist_account.username, alist_account.password)

    host = _parse_host(alist_host.host)
    # walkthrough: alist bug cause user without '/' as
    # root path cannot fetch thumbnail url by 'fs/get/', so use 'fs/list/' here
    dir = str(Path(path).parent)
    name = Path(path).name
    response = requests.post(
        host + '/api/fs/list',
        json={'path': dir},
        headers={
            'Authorization': alist_token,
            'content-type': 'application/json',
        },
    )
    if not response.ok:
        raise Exception(response.status_code)

    data = response.json()
    if data['code'] != 200:
        raise Exception({
            'message': 'get file info failed.',
            'detail': data,
        })

    url = next(i['thumb']
               for i in data['data']['content'] if i['name'] == name)

    return requests.get(
        url,
        headers={'Authorization': alist_token},
    )


def _convert_to_http_response(requests_response: requests.models.Response) -> HttpResponse:
    django_response = HttpResponse(
        content=requests_response.content,
        status=requests_response.status_code,
        content_type=requests_response.headers.get('Content-Type')
    )

    return django_response


def _parse_host(host):
    parsed = urlparse(host)
    return f'{parsed.scheme}://{parsed.netloc}'
