# PEP-8

from django.db import models
from django.dispatch import receiver
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
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


@receiver(models.signals.post_save, sender=Channel)
def create_channel_profile(sender, instance, created, **kwargs):
    if created:
        AListAccount.objects.create(channel=instance)
        BilibiliAccount.objects.create(channel=instance)

        content_type = ContentType.objects.get_for_model(Channel)
        Permission.objects.create(
            codename=f'channel_{instance.channel_id}',
            name=f'Actions in channel {instance.channel_id}',
            content_type=content_type,
        )


@receiver(models.signals.post_delete, sender=Channel)
def delete_channel_profile(sender, instance, **kwargs):
    Permission.objects.filter(
        codename=f'channel_{instance.channel_id}').delete()


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
