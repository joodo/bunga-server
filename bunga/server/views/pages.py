# PEP-8

from django.shortcuts import render
from django.contrib.auth.decorators import login_not_required

from server.models import Site


@login_not_required
def index(request):
    config = Site.get_solo()
    return render(request, 'index.djhtml', {
        'site_name': config.name,
    })
