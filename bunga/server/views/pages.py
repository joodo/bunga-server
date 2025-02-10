from django.shortcuts import render

from server.models import SiteConfiguration


def index(request):
    config = SiteConfiguration.get_solo()
    return render(request, 'index.djhtml', {
        'site_name': config.site_name,
    })
