from django import shortcuts
from rest_framework import renderers, status

from . import models


class DashboardRenderMixin:
    def dispatch(self, request, *args, **kwargs):
        response = super().dispatch(request, *args, **kwargs)
        if type(response.accepted_renderer) == renderers.TemplateHTMLRenderer:
            if request.method == 'GET':
                response.data = {
                    'serializer': self.get_serializer(response.data),
                    'site_name': models.SiteConfiguration.get_solo().site_name,
                    'alert': request.session.pop('alert', default=None),
                }
                return response
            else:
                if status.is_success(response.status_code):
                    request.session['alert'] = {
                        'type': 'success',
                        'content': '修改已保存',
                    }
                else:
                    request.session['alert'] = {
                        'type': 'danger',
                        'content': response.data,
                    }
                return shortcuts.redirect(request.META['HTTP_REFERER'])
