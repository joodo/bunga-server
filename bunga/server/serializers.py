from rest_framework import serializers

from . import models


class DurationSecondsField(serializers.Field):
    """
    DRF Field: store a timedelta as float seconds
    """

    def to_representation(self, value):
        return value.total_seconds() if value else 0.0

    def to_internal_value(self, data):
        try:
            seconds = float(data)
        except (ValueError, TypeError):
            raise serializers.ValidationError("Must be a number (seconds)")
        from datetime import timedelta

        return timedelta(seconds=seconds)


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Site
        fields = "__all__"


class AlistHostSerializer(serializers.ModelSerializer):
    site = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.AListHost
        fields = "__all__"


class VoiceKeySerializer(serializers.ModelSerializer):
    site = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.VoiceKey
        fields = "__all__"


class IMKeySerializer(serializers.ModelSerializer):
    site = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.IMKey
        fields = "__all__"


class ChannelSerializer(serializers.ModelSerializer):
    channel_id = serializers.CharField(
        style={
            "input_type": "hidden",
            "hide_label": True,
        }
    )

    class Meta:
        model = models.Channel
        fields = "__all__"


class BilibiliAccountSerializer(serializers.ModelSerializer):
    channel = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.BilibiliAccount
        fields = "__all__"


class AListAccountSerializer(serializers.ModelSerializer):
    channel = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.AListAccount
        fields = "__all__"


class SubtitleSerializer(serializers.ModelSerializer):
    uploader = serializers.CharField(source="uploader.username", read_only=True)

    class Meta:
        model = models.Subtitle
        read_only_fields = ["record", "uploader", "name"]
        fields = "__all__"


class VideoRecordSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.VideoRecord
        fields = ("record_id", "title", "thumb_url", "source", "path")


class VideoRecordSerializer(serializers.ModelSerializer):
    subtitle = SubtitleSerializer(read_only=True)
    position = DurationSecondsField(required=False)

    class Meta:
        model = models.VideoRecord
        fields = (
            "record_id",
            "title",
            "thumb_url",
            "source",
            "path",
            "subtitle",
            "position",
        )


class RegisterPayloadSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150, required=True)
    password = serializers.CharField(required=True)
