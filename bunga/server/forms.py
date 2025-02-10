from django import forms
from django.forms import ModelForm, Form

from .models import AListAccount, BilibiliAccount, CallingConfiguration, ChatConfiguration, SiteConfiguration


class SiteBasicForm(ModelForm):
    class Meta:
        model = SiteConfiguration
        fields = ['site_name', 'allow_new_client']


class SiteAlistForm(ModelForm):
    class Meta:
        model = SiteConfiguration
        fields = ['alist_host']


class ChatConfigurationForm(ModelForm):
    class Meta:
        model = ChatConfiguration
        exclude = []


class ChannelForm(Form):
    channel_id = forms.CharField(max_length=255, disabled=True)
    name = forms.CharField(max_length=255)


class CallingConfigurationForm(ModelForm):
    class Meta:
        model = CallingConfiguration
        exclude = []


class AListAccountForm(ModelForm):
    password = forms.CharField(widget=forms.PasswordInput(render_value=True))

    class Meta:
        model = AListAccount
        fields = ['username', 'password']


class BilibiliAccountForm(ModelForm):
    class Meta:
        model = BilibiliAccount
        fields = ['sess', 'bili_jct', 'refresh_token']
