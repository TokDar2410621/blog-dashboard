from django.apps import AppConfig


class SitesMgmtConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'sites_mgmt'

    def ready(self):
        from . import signals  # noqa: F401
