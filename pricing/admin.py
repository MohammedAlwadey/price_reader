from django.contrib import admin
from .models import OracleSettings


@admin.register(OracleSettings)
class OracleSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "company_name",
        "host",
        "port",
        "connection_mode",
        "sid",
        "service_name",
        "schema_name",
        "pricing_level",
        "username",
        "is_active",
        "updated_at",
    )
    list_filter = ("is_active", "connection_mode")
    search_fields = ("company_name", "host", "sid", "service_name", "schema_name", "username")