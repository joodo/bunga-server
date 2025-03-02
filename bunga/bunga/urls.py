from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from debug_toolbar.toolbar import debug_toolbar_urls

urlpatterns = [
    path('', include('server.urls')),
    path('admin/', admin.site.urls),
] + debug_toolbar_urls()
