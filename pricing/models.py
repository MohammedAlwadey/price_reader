from django.conf import settings
from django.db import models

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