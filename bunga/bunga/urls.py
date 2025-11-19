from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from debug_toolbar.toolbar import debug_toolbar_urls

urlpatterns = [
    path('', include('server.urls')),
    path('admin/', admin.site.urls),
] + debug_toolbar_urls()

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL,
                          document_root=settings.MEDIA_ROOT)
