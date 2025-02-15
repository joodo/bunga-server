from django.db import models
from solo.models import SingletonModel


class Site(SingletonModel):
    name = models.CharField(max_length=100, default='My Bunga Server')


class AListHost(SingletonModel):
    site = models.OneToOneField(Site,
                                on_delete=models.CASCADE,
                                primary_key=True)
    host = models.URLField()


class IMKey(SingletonModel):
    site = models.OneToOneField(Site,
                                on_delete=models.CASCADE,
                                primary_key=True)
    tencent_app_id = models.CharField(max_length=100)
    tencent_app_key = models.CharField(max_length=100)
    tencent_admin_name = models.CharField(max_length=100)


class VoiceKey(SingletonModel):
    site = models.OneToOneField(Site,
                                on_delete=models.CASCADE,
                                primary_key=True)
    agora_key = models.CharField(max_length=100)
    agora_certification = models.CharField(max_length=100)


class Channel(models.Model):
    channel_id = models.CharField(max_length=100, primary_key=True)
    allow_new_client = models.BooleanField(default=True)


class AListAccount(models.Model):
    channel = models.OneToOneField(Channel,
                                   on_delete=models.CASCADE,
                                   primary_key=True)
    username = models.CharField(max_length=100, default='')
    password = models.CharField(max_length=100, default='')


class BilibiliAccount(models.Model):
    channel = models.OneToOneField(Channel,
                                   on_delete=models.CASCADE,
                                   primary_key=True)
    sess = models.CharField(max_length=500, default='')
    bili_jct = models.CharField(max_length=200, default='')
    refresh_token = models.CharField(max_length=200, default='')
