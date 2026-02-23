# PEP-8

from datetime import timedelta

from django.db import models
from django.dispatch import receiver
from django.conf import settings
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from solo.models import SingletonModel


def validate_file_size(file):
    file_size = file.size
    limit_mb = 1
    if file_size > limit_mb * 1024 * 1024:
        raise ValidationError(f"File size cannot exceed {limit_mb}MB.")


class Site(SingletonModel):
    name = models.CharField(max_length=100, default="My Bunga Server")


class AListHost(SingletonModel):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, primary_key=True)
    host = models.URLField()


class IMKey(SingletonModel):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, primary_key=True)
    tencent_app_id = models.CharField(max_length=100)
    tencent_app_key = models.CharField(max_length=100)
    tencent_admin_name = models.CharField(max_length=100)


class VoiceKey(SingletonModel):
    site = models.OneToOneField(Site, on_delete=models.CASCADE, primary_key=True)
    agora_key = models.CharField(max_length=100)
    agora_certification = models.CharField(max_length=100)


class Channel(models.Model):
    channel_id = models.CharField(max_length=100, primary_key=True)
    name = models.CharField(max_length=200)
    allow_new_client = models.BooleanField(default=True)

    def __str__(self):
        return self.channel_id


@receiver(models.signals.post_save, sender=Channel)
def create_channel_profile(sender, instance, created, **kwargs):
    if created:
        AListAccount.objects.create(channel=instance)
        BilibiliAccount.objects.create(channel=instance)

        content_type = ContentType.objects.get_for_model(Channel)
        Permission.objects.create(
            codename=f"channel_{instance.channel_id}",
            name=f"Actions in channel {instance.channel_id}",
            content_type=content_type,
        )


@receiver(models.signals.post_delete, sender=Channel)
def delete_channel_profile(sender, instance, **kwargs):
    Permission.objects.filter(codename=f"channel_{instance.channel_id}").delete()


class AListAccount(models.Model):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, primary_key=True)
    username = models.CharField(max_length=100, default="")
    password = models.CharField(max_length=100, default="")


class BilibiliAccount(models.Model):
    channel = models.OneToOneField(Channel, on_delete=models.CASCADE, primary_key=True)
    sess = models.CharField(max_length=500, default="")
    bili_jct = models.CharField(max_length=200, default="")
    refresh_token = models.CharField(max_length=200, default="")


class VideoRecord(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE)
    record_id = models.CharField(max_length=200)

    updated_at = models.DateTimeField(auto_now=True)

    title = models.CharField(max_length=200)
    thumb_url = models.URLField(max_length=400, null=True)
    source = models.CharField(max_length=200)
    path = models.CharField(max_length=200)

    position = models.DurationField(default=timedelta(0))

    def __str__(self):
        return f'[{self.channel.channel_id}] {self.title} ({self.updated_at.strftime("%Y-%m-%d %H:%M:%S")})'

    class Meta:
        unique_together = ("channel", "record_id")
        ordering = ("channel", "-updated_at")


class Subtitle(models.Model):
    record = models.OneToOneField(
        VideoRecord,
        on_delete=models.CASCADE,
        related_name="subtitle",
    )
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to="subtitles/")


class ClientLog(models.Model):
    channel_id = models.CharField(max_length=100)
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    file = models.FileField(
        upload_to="logs/",
        validators=[validate_file_size],
    )

    class Meta:
        ordering = ("-created_at",)


@receiver(models.signals.post_delete, sender=ClientLog)
def delete_client_log_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
