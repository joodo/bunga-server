from django.contrib import admin

from solo.admin import SingletonModelAdmin
from server.models import Site


admin.site.register(Site, SingletonModelAdmin)
