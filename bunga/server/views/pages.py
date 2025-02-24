# PEP-8

from django.shortcuts import render

from server.models import Site


def index(request):
    config = Site.get_solo()
    return render(request, 'index.djhtml', {
        'site_name': config.name,
    })
