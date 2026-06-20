from django.conf import settings
from django.db import models
from django.contrib.sessions.models import Session
from django.utils import timezone


class OracleSettings(models.Model):
    company_name = models.CharField(max_length=150, default="قارى الأسعار")

    host = models.CharField(max_length=255)
    port = models.PositiveIntegerField(default=1521)

    connection_mode = models.CharField(
        max_length=20,
        choices=[
            ("sid", "SID"),
            ("service_name", "Service Name"),
        ],
        default="sid",
    )

    sid = models.CharField(max_length=100, blank=True)
    service_name = models.CharField(max_length=100, blank=True)

    schema_name = models.CharField(max_length=30, default="YSPOS1")
    pricing_level = models.PositiveIntegerField(default=2)

    username = models.CharField(max_length=100)
    password = models.CharField(max_length=255)

    oracle_client_lib_dir = models.CharField(
        max_length=255,
        blank=True,
        help_text="مثال: C:\\Users\\user\\Pictures\\instantclient-basic-windows.x64-23.26.2.0.0\\instantclient_23_0",
    )

    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.company_name
    
    

class BarcodeSearchLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    barcode = models.CharField(max_length=100)
    success = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "سجل بحث باركود"
        verbose_name_plural = "سجل بحث الباركود"




class ActiveUserSession(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="active_session",
    )
    session_key = models.CharField(max_length=40, blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user} - {self.session_key}"
    


class UserLoginPolicy(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="login_policy",
        verbose_name="المستخدم",
    )
    allow_multiple_sessions = models.BooleanField(
        default=False,
        verbose_name="السماح بالدخول من أكثر من جهاز",
    )

    class Meta:
        verbose_name = "صلاحية دخول المستخدم"
        verbose_name_plural = "صلاحيات دخول المستخدمين"

    def __str__(self):
        return str(self.user)


def user_allows_multiple_sessions(user):
    if not user.is_authenticated:
        return True

    # اختياري: لو تبغى السوبر يوزر دائمًا مسموح له
    if user.is_superuser:
        return True

    try:
        return user.login_policy.allow_multiple_sessions
    except UserLoginPolicy.DoesNotExist:
        return False
    
def cleanup_expired_active_sessions():
    valid_session_keys = set(
        Session.objects.filter(expire_date__gte=timezone.now())
        .values_list("session_key", flat=True)
    )

    ActiveUserSession.objects.exclude(
        session_key__in=valid_session_keys
    ).delete()


def get_active_users_count():
    cleanup_expired_active_sessions()
    return ActiveUserSession.objects.exclude(session_key__isnull=True).count()