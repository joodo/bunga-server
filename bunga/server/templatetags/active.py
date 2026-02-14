import re

from django import template
from django.urls import reverse

register = template.Library()


@register.simple_tag(takes_context=True)
def active(context, url_name, *args, **kwargs):
    try:
        target = reverse(url_name, args=args, kwargs=kwargs)
    except Exception:
        try:
            target = reverse(url_name)
        except Exception:
            return ""
    pattern = "^" + re.escape(target) + "$"
    path = context["request"].path
    if re.search(pattern, path):
        return "active"
    return ""
