from django.contrib import admin
from django.contrib.auth.views import LogoutView
from django.urls import include, path

from pricing.views import SingleSessionLoginView

urlpatterns = [
    path("admin/", admin.site.urls),

    path("accounts/login/", SingleSessionLoginView.as_view(), name="login"),
    path("accounts/logout/", LogoutView.as_view(next_page="login"), name="logout"),
    path("accounts/", include("django.contrib.auth.urls")),

    path("", include("pricing.urls")),
]