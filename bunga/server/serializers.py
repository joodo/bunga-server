from rest_framework import serializers

from . import models


class ChatConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = models.ChatConfiguration
        fields = '__all__'


class ChannelDetailSerializer(serializers.Serializer):
    channel_id = serializers.CharField(read_only=True)
    name = serializers.CharField()


class BilibiliAccountSerializer(serializers.ModelSerializer):
    channel_id = serializers.CharField(style={
        'input_type': 'hidden',
        'hide_label': True,
    })

    class Meta:
        model = models.BilibiliAccount
        fields = '__all__'


class AListAccountSerializer(serializers.ModelSerializer):
    channel_id = serializers.CharField(style={
        'input_type': 'hidden',
        'hide_label': True,
    })

    class Meta:
        model = models.AListAccount
        fields = '__all__'
