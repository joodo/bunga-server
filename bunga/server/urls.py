from django.urls import include, path
from django.views.generic.base import RedirectView
from rest_framework import routers

from .views import pages, dashboard, api

dashboard_patterns = [
    path('',
         RedirectView.as_view(pattern_name='site', permanent=True),
         name='dashboard',
         ),
    path('site/', dashboard.site, name='site'),
    path('channels/', dashboard.channel_list, name='channels'),
    path('channels/<str:channel_id>/',
         dashboard.channel_detail, name='channel-detail'),
]

api_patterns = [
    path('bilibili/qr', api.bilibili_qr, name='bilibili-qr'),
    path('bilibili/pull', api.bilibili_pull, name='bilibili-pull'),
    path('bilibili/info', api.bilibili_info, name='bilibili-info'),
    path('alist/info', api.alist_info, name='alist_info'),
    path('alist/user-info', api.alist_user_info, name='alist-user-info'),
    path('chat/config', api.ChatConfig.as_view(), name='chat_config'),
]
router = routers.SimpleRouter()
router.register(r'channels', api.ChannelViewSet, basename='channel')
router.register(r'bilibili-account', api.BiliAccountViewSet,
                basename='bili-account')
router.register(r'alist-account', api.AListAccountViewSet,
                basename='alist-account')
api_patterns += router.urls

urlpatterns = [
    path('', pages.index, name='index'),
    path('dashboard/', include(dashboard_patterns,)),
    path('api/', include((api_patterns, 'api'))),
]
