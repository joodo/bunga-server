from rest_framework import renderers


class JSONRendererWithCharset(renderers.JSONRenderer):
    charset = 'utf-8'
