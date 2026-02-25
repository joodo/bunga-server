from dataclasses import asdict

from asgiref.sync import async_to_sync
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from server.chat.utils import broadcast_message
from server.chat.channel_cache import ChannelCache
from server import models, serializers


class ClientLogViewSet(viewsets.ModelViewSet):
    queryset = models.ClientLog.objects.all()
    serializer_class = serializers.ClientLogSerializer

    def get_permissions(self):
        if self.action == "create":
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdminUser]
        return [permission() for permission in permission_classes]

    def perform_create(self, serializer):
        serializer.save(uploader=self.request.user)


@api_view(["GET"])
@permission_classes([IsAdminUser])
def monitor_logs(request):
    """Get the most recent log entries"""
    from django.conf import settings

    log_dir = settings.LOG_DIR
    log_file = log_dir / "django.log"

    logs = []
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            # Read the last 100 lines
            lines = f.readlines()
            logs = lines[-100:] if len(lines) > 100 else lines

    return Response({"logs": logs})


@api_view(["GET"])
@permission_classes([IsAdminUser])
def monitor_cache(request, channel_id: str):
    """Get cache info for a single channel"""
    try:
        channel = models.Channel.objects.get(channel_id=channel_id)
    except models.Channel.DoesNotExist:
        return Response({"error": "channel not found"}, status=404)

    try:
        channel_cache = ChannelCache(channel_id)
        cache_info = {
            "channel_id": channel_id,
            "channel_status": str(channel_cache.channel_status.name),
            "current_projection": None,
            "watcher_list": [asdict(w) for w in channel_cache.watcher_list],
            "watcher_count": len(channel_cache.watcher_list),
            "ready_watchers": list(channel_cache.ready_watchers),
            "buffering_watchers": list(channel_cache.buffering_watchers),
            "has_pending_call": channel_cache.has_pending_call,
            "play_status": (
                {
                    "playing": channel_cache.play_status.playing,
                    "position_seconds": channel_cache.play_status.position.total_seconds(),
                }
                if channel_cache.play_status
                else None
            ),
        }

        if channel_cache.current_projection:
            proj = channel_cache.current_projection
            cache_info["current_projection"] = {
                "record_id": proj.record.record_id,
                "title": proj.record.title,
                "source": proj.record.source,
                "sharer_id": proj.sharer.id,
                "sharer_name": proj.sharer.name,
            }

        return Response(cache_info)
    except Exception as e:
        return Response({"error": str(e)}, status=500)


@api_view(["POST"])
@permission_classes([IsAdminUser])
def monitor_reset_channel(request, channel_id: str):
    if not models.Channel.objects.filter(channel_id=channel_id).exists():
        return Response({"error": "channel not found"}, status=404)

    try:
        async_to_sync(broadcast_message)(channel_id, "reset")
        channel_cache = ChannelCache(channel_id)
        channel_cache.reset()
        return Response({"message": "Channel state has been reset"}, status=200)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
