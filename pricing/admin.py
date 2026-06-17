from django.contrib import admin
from .models import OracleSettings


from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import UserLoginPolicy


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


class UserLoginPolicyInline(admin.StackedInline):
    model = UserLoginPolicy
    can_delete = False
    extra = 0
    verbose_name_plural = "صلاحيات الدخول"


try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (UserLoginPolicyInline,)
    inlines = (UserLoginPolicyInline,)