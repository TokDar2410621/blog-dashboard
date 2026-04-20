from django.contrib import admin
from .models import Site


@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = ['name', 'domain', 'owner', 'created_at']
    list_filter = ['owner']
    search_fields = ['name', 'domain']
