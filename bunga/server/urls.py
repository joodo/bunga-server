# PEP-8

from django.urls import include, path
from django.views.generic.base import RedirectView
from rest_framework import routers
from rest_framework_simplejwt.views import (
    token_obtain_pair,
    token_refresh,
    token_verify,
)

from . import consumers
from .views import pages, dashboard, api

dashboard_patterns = [
    path(
        "",
        RedirectView.as_view(pattern_name="site", permanent=True),
        name="dashboard",
    ),
    path("site/", dashboard.site, name="site"),
    path("channels/", dashboard.channel_list, name="channels"),
    path("channels/<str:channel_id>/", dashboard.channel_detail, name="channel-detail"),
    path(
        "channels/<str:channel_id>/monitor/", dashboard.monitor, name="channel-monitor"
    ),
    path("client-logs/", dashboard.client_logs, name="client-logs"),
]

api_patterns = [
    path("token/", token_obtain_pair, name="token_obtain_pair"),
    path("token/refresh/", token_refresh, name="token_refresh"),
    path("token/verify/", token_verify, name="token_verify"),
    path("site", api.Site.as_view(), name="site"),
    path("alist-host", api.AListHost.as_view(), name="alist-host"),
    path("bilibili/qr", api.bilibili_qr, name="bilibili-qr"),
    path("bilibili/pull", api.bilibili_pull, name="bilibili-pull"),
    path("bilibili/info", api.bilibili_info, name="bilibili-info"),
    path("alist/info", api.alist_info, name="alist_info"),
    path("alist/user-info", api.alist_user_info, name="alist-user-info"),
    path("chat/config", api.IMKey.as_view(), name="chat-config"),
    path("voice/config", api.VoiceKey.as_view(), name="voice-config"),
    path("monitor/logs", api.monitor_logs, name="monitor-logs"),
    path("monitor/<str:channel_id>/cache", api.monitor_cache, name="monitor-cache"),
    path(
        "monitor/<str:channel_id>/reset",
        api.monitor_reset_channel,
        name="monitor-reset",
    ),
    path(
        "channels/<str:channel_id>/records/<str:record_id>/subtitle",
        api.SubtitleCreateView.as_view(),
        name="subtitle-upload",
    ),
]

view_set_router = routers.DefaultRouter()
view_set_router.register(r"channels", api.ChannelViewSet, basename="channel")
view_set_router.register(
    r"bilibili-account", api.BiliAccountViewSet, basename="bili-account"
)
view_set_router.register(
    r"alist-account", api.AListAccountViewSet, basename="alist-account"
)
view_set_router.register(
    r"channels/<str:channel_id>/records",
    api.VideoRecordViewSet,
    basename="video-record",
)
view_set_router.register(r"client-logs", api.ClientLogViewSet, basename="client-log")
api_patterns += view_set_router.urls

urlpatterns = [
    path("", pages.index, name="index"),
    path("dashboard/", include(dashboard_patterns)),
    path("api/", include((api_patterns, "api"))),
]


websocket_urlpatterns = [path("chat/", consumers.ChatConsumer.as_asgi())]
