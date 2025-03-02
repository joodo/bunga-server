# Generated by Django 5.1.6 on 2025-02-15 05:56

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Channel',
            fields=[
                ('channel_id', models.CharField(max_length=100, primary_key=True, serialize=False)),
                ('allow_new_client', models.BooleanField(default=True)),
            ],
        ),
        migrations.CreateModel(
            name='Site',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='My Bunga Server', max_length=100)),
                ('alist_host', models.URLField()),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='AListAccount',
            fields=[
                ('channel', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='server.channel')),
                ('username', models.CharField(max_length=100)),
                ('password', models.CharField(max_length=100)),
            ],
        ),
        migrations.CreateModel(
            name='BilibiliAccount',
            fields=[
                ('channel', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='server.channel')),
                ('sess', models.CharField(max_length=500)),
                ('bili_jct', models.CharField(max_length=200)),
                ('refresh_token', models.CharField(max_length=200)),
            ],
        ),
        migrations.CreateModel(
            name='IMKey',
            fields=[
                ('site', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='server.site')),
                ('tencent_app_id', models.CharField(max_length=100)),
                ('tencent_app_key', models.CharField(max_length=100)),
                ('tencent_admin_name', models.CharField(max_length=100)),
            ],
            options={
                'abstract': False,
            },
        ),
        migrations.CreateModel(
            name='VoiceKey',
            fields=[
                ('site', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, primary_key=True, serialize=False, to='server.site')),
                ('agora_key', models.CharField(max_length=100)),
                ('agora_certification', models.CharField(max_length=100)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
