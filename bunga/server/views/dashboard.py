from django.shortcuts import redirect, render
from rest_framework import generics, renderers

from server import models, forms, serializers, mixins


def site(request):
    config = models.SiteConfiguration.get_solo()
    if request.method == 'POST':
        updated_form = request.GET.get('update')
        match updated_form:
            case 'basic':
                form = forms.SiteBasicForm(request.POST, instance=config)
                form.save()
            case 'alist':
                form = forms.SiteAlistForm(request.POST, instance=config)
                form.save()
            case _:
                raise Exception('Unknown update type: ' + str(updated_form))
        return __render_saved(request)

    basic_form = forms.SiteBasicForm(instance=config)
    alist_form = forms.SiteAlistForm(instance=config)
    return __render_dashboard(request, 'site.djhtml', {
        'basic_form': basic_form,
        'alist_form': alist_form,
    })


def channel_list(request):
    return __render_dashboard(request, 'channels.djhtml', {
        'chat_serializer': serializers.ChatConfigurationSerializer,
    })


def channel_detail(request, channel_id):
    return __render_dashboard(request, 'channel_detail.djhtml', {
        'channel_serializer': serializers.ChannelDetailSerializer,
        'channel_id': channel_id,
        'bili_serializer': serializers.BilibiliAccountSerializer,
        'alist_serializer': serializers.AListAccountSerializer,
    })


def __render_dashboard(request, template_name, data):
    template_data = {
        'site_name': models.SiteConfiguration.get_solo().site_name,
        'alert': request.session.pop('alert', default=None),
    }
    return render(request, template_name, template_data | data)


def __render_saved(request):
    request.session['alert'] = {
        'type': 'success',
        'content': '修改已保存',
    }
    return redirect(request.META['HTTP_REFERER'])
