from django.db import models
from solo.models import SingletonModel


class SiteConfiguration(SingletonModel):
    site_name = models.CharField(max_length=100, default='My Bunga Server')
    allow_new_client = models.BooleanField(default=True)
    alist_host = models.URLField()

    def __str__(self):
        return 'Site Configuration'

    class Meta:
        verbose_name = 'Site Configuration'


class ChatConfiguration(SingletonModel):
    tencent_app_id = models.CharField(max_length=100)
    tencent_app_key = models.CharField(max_length=100)
    tencent_admin_name = models.CharField(max_length=100)

    def __str__(self):
        return 'Chat Configuration'

    class Meta:
        verbose_name = 'Chat Configuration'


class CallingConfiguration(SingletonModel):
    agora_key = models.CharField(max_length=100)
    agora_certification = models.CharField(max_length=100)

    def __str__(self):
        return 'Calling Configuration'

    class Meta:
        verbose_name = 'Calling Configuration'


class AListAccount(models.Model):
    channel_id = models.CharField(max_length=100, primary_key=True)
    username = models.CharField(max_length=100)
    password = models.CharField(max_length=100)

    def __str__(self):
        return 'AList Accounts'

    class Meta:
        verbose_name = 'AList Accounts'


class BilibiliAccount(models.Model):
    channel_id = models.CharField(max_length=100, primary_key=True)
    sess = models.CharField(max_length=500)
    bili_jct = models.CharField(max_length=200)
    refresh_token = models.CharField(max_length=200)
