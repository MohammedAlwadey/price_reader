from urllib.parse import urlencode

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse

from pricing.models import ActiveUserSession, user_allows_multiple_sessions


class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if user_allows_multiple_sessions(request.user):
            return self.get_response(request)

        current_session_key = request.session.session_key

        if not current_session_key:
            request.session.save()
            current_session_key = request.session.session_key

        active_session_key = (
            ActiveUserSession.objects
            .filter(user=request.user)
            .values_list("session_key", flat=True)
            .first()
        )

        if not active_session_key:
            ActiveUserSession.objects.update_or_create(
                user=request.user,
                defaults={"session_key": current_session_key},
            )
            return self.get_response(request)

        if active_session_key != current_session_key:
            logout(request)

            login_url = reverse("login")
            query_string = urlencode({"next": request.get_full_path()})

            return redirect(f"{login_url}?{query_string}")

        return self.get_response(request)