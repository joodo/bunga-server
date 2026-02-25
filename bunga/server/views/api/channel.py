import os
from typing import Any

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
import requests
from rest_framework import generics, mixins, viewsets, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.permissions import IsAdminUser, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django import http
from django.contrib.auth import authenticate
from django.contrib.auth.models import User, Permission

from server import models, serializers
from server.utils import bilibili as bili_utils, agora, auto_validated


from .bilibili import get_bili_info
from .alist import get_alist_thumb, get_alist_token


class ChannelViewSet(viewsets.ModelViewSet):
    queryset = models.Channel.objects.all()
    serializer_class = serializers.ChannelSerializer
    permission_classes = [IsAdminUser]

    @action(
        detail=True,
        methods=["post"],
        permission_classes=[AllowAny],
        serializer_class=serializers.RegisterPayloadSerializer,
    )
    @auto_validated
    def register(self, validated, request: Request, pk=None) -> Response:
        def register_user() -> User:
            return User.objects.create_user(
                validated["username"],
                None,
                validated["password"],
            )

        def join_user_to_channel(user: User) -> None:
            user.user_permissions.add(permission)
            user.save()

        # Check if channel exist
        try:
            channel = self.get_object()
        except http.Http404:
            return Response(
                {
                    "channel_id": "Channel does not exist.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )
        permission = Permission.objects.get(codename=f"channel_{channel.channel_id}")

        user_exists = User.objects.filter(username=validated["username"]).exists()
        if not user_exists:
            # User not exist and channel forbid join
            if not channel.allow_new_client:
                return Response(
                    {
                        "channel_id": "Channel does not allow new client.",
                    },
                    status=status.HTTP_403_FORBIDDEN,
                )
            # Else create user and join it!
            else:
                try:
                    user = register_user()
                    join_user_to_channel(user)
                except Exception as e:
                    return Response(
                        {
                            "detail": str(e),
                        },
                        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    )
                status_code = status.HTTP_201_CREATED
        else:
            user = authenticate(
                username=validated["username"], password=validated["password"]
            )
            if user is None:
                # Password not corrent
                return Response(
                    {
                        "password": "Password is not correct.",
                    },
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            else:
                if not user.has_perm(f"server.{permission.codename}"):
                    # Not in channel but channel forbid join...
                    if not channel.allow_new_client:
                        return Response(
                            {
                                "channel_id": "Channel does not allow new client.",
                            },
                            status=status.HTTP_403_FORBIDDEN,
                        )
                    # Join it!
                    else:
                        try:
                            join_user_to_channel(user)
                        except Exception as e:
                            return Response(
                                {
                                    "detail": str(e),
                                },
                                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            )
                        status_code = status.HTTP_200_OK
                else:
                    # User exist and already join channel, do nothing
                    status_code = status.HTTP_200_OK

        refresh = RefreshToken.for_user(user)
        data: dict[str, Any] = {
            "token": {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
            },
        }

        data["channel"] = serializers.ChannelSerializer(channel).data

        try:
            agoraInfo = models.VoiceKey.get_solo()
            data["voice_call"] = {
                "service": "agora",
                "key": agoraInfo.agora_key,
                "channel_token": agora.generateToken(
                    agoraInfo.agora_key,
                    agoraInfo.agora_certification,
                    channel.channel_id,
                    agora.uidFromName(validated["username"]),
                ),
            }
        except:
            data["voice_call"] = None

        try:
            bilibili = models.BilibiliAccount.objects.get(channel=channel)
            sess = bilibili.sess

            info = get_bili_info(sess)
            mixinKey = bili_utils.get_mixin_key(**info["wbi"])

            data["bilibili"] = {
                "sess": sess,
                "mixin_key": mixinKey,
            }
        except:
            data["bilibili"] = None

        try:
            alist_host = models.AListHost.get_solo()
            alist_account = models.AListAccount.objects.get(channel=channel)
            data["alist"] = {
                "host": alist_host.host,
                "token": get_alist_token(
                    alist_host.host, alist_account.username, alist_account.password
                ),
            }
        except:
            data["alist"] = None

        return Response(data, status=status_code)

    @action(
        url_path="alist-thumbnail",
        detail=True,
        methods=["get"],
        permission_classes=[AllowAny],
    )
    def alist_thumbnail(self, request: Request, pk=None) -> Any:
        try:
            requests_response = get_alist_thumb(
                request.query_params.get("path"),
                pk,
            )
        except Exception as e:
            return Response(
                {
                    "detail": str(e),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        return _convert_to_drf_response(requests_response)


def _convert_to_drf_response(
    requests_response: requests.models.Response,
) -> HttpResponse:
    drf_response = HttpResponse(
        content=requests_response.content,
        status=requests_response.status_code,
        content_type=requests_response.headers.get("Content-Type"),
    )

    return drf_response


class VideoRecordViewSet(viewsets.GenericViewSet, mixins.RetrieveModelMixin):
    """
    Call GET detail when join room;
    Call POST list/project when project video to room
    """

    serializer_class = serializers.VideoRecordSerializer
    lookup_field = "record_id"
    lookup_url_kwarg = "record_id"

    async def get_queryset(self):
        channel_id = self.kwargs["channel_id"]
        return models.VideoRecord.objects.filter(channel_id=channel_id)


class SubtitleCreateView(generics.CreateAPIView):
    serializer_class = serializers.SubtitleSerializer

    def perform_create(self, serializer):
        record_id = self.kwargs["record_id"]
        channel_id = self.kwargs["channel_id"]
        channel = get_object_or_404(models.Channel, channel_id=channel_id)
        record = get_object_or_404(
            models.VideoRecord,
            channel=channel,
            record_id=record_id,
        )

        models.Subtitle.objects.filter(record=record).delete()

        uploaded_file = serializer.validated_data["file"]
        name_without_ext, _ = os.path.splitext(uploaded_file.name)
        serializer.save(
            record=record,
            uploader=self.request.user,
            name=name_without_ext,
        )
