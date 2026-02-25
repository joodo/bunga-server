from rest_framework import generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.request import Request
from rest_framework.response import Response

from server import models, serializers


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
