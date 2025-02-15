from rest_framework import serializers

from . import models


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.Site
        fields = '__all__'


class AlistHostSerializer(serializers.ModelSerializer):
    site = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.AListHost
        fields = '__all__'


class IMKeySerializer(serializers.ModelSerializer):
    site = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.IMKey
        fields = '__all__'


class ChannelSerializer(serializers.ModelSerializer):
    channel_id = serializers.CharField(style={'input_type': 'hidden',
                                              'hide_label': True,
                                              })

    class Meta:
        model = models.Channel
        fields = '__all__'


class BilibiliAccountSerializer(serializers.ModelSerializer):
    channel = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.BilibiliAccount
        fields = '__all__'


class AListAccountSerializer(serializers.ModelSerializer):
    channel = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = models.AListAccount
        fields = '__all__'
