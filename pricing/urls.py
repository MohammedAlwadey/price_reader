from django.urls import path

from .views import BarcodeLookupView

urlpatterns = [
    path("", BarcodeLookupView.as_view(), name="barcode_lookup"),
]