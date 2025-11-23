from django.contrib import admin

from solo.admin import SingletonModelAdmin

from server.models import Site, Channel, VideoRecord


admin.site.register(Site, SingletonModelAdmin)
admin.site.register([Channel, VideoRecord])
