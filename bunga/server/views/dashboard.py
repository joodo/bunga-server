from django.shortcuts import redirect, render
from django.contrib.auth.decorators import login_required

from server import models, serializers


@login_required
def site(request):
    config = models.Site.get_solo()

    site_serializer = serializers.SiteSerializer()
    alist_serializer = serializers.AlistHostSerializer()
    voice_key_serializer = serializers.VoiceKeySerializer()
    return __render_dashboard(
        request,
        "site.djhtml",
        {
            "site_id": config.pk,
            "site_serializer": site_serializer,
            "voice_key_serializer": voice_key_serializer,
            "alist_serializer": alist_serializer,
        },
    )


@login_required
def channel_list(request):
    return __render_dashboard(
        request,
        "channels.djhtml",
        {
            "chat_serializer": serializers.IMKeySerializer,
        },
    )


@login_required
def channel_detail(request, channel_id):
    return __render_dashboard(
        request,
        "channel_detail.djhtml",
        {
            "channel_serializer": serializers.ChannelSerializer,
            "channel_id": channel_id,
            "bili_serializer": serializers.BilibiliAccountSerializer,
            "alist_serializer": serializers.AListAccountSerializer,
        },
    )


@login_required
def monitor(request, channel_id):
    return __render_dashboard(
        request,
        "monitor.djhtml",
        {
            "channel_id": channel_id,
        },
    )


@login_required
def client_logs(request):
    return __render_dashboard(
        request,
        "client_logs.djhtml",
        {},
    )


def __render_dashboard(request, template_name, data):
    template_data = {
        "site_name": models.Site.get_solo().name,
        "alert": request.session.pop("alert", default=None),
        "channels": models.Channel.objects.all(),
    }
    return render(request, template_name, template_data | data)


def __render_saved(request):
    request.session["alert"] = {
        "type": "success",
        "content": "修改已保存",
    }
    return redirect(request.META["HTTP_REFERER"])
