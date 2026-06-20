from urllib.parse import urlencode

from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.sessions.models import Session
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from pricing.licensing import get_license_limit, LicenseError
from pricing.models import ActiveUserSession, user_allows_multiple_sessions


def cleanup_expired_active_sessions():
    valid_session_keys = set(
        Session.objects.filter(expire_date__gt=timezone.now())
        .values_list("session_key", flat=True)
    )

    ActiveUserSession.objects.exclude(
        session_key__in=valid_session_keys
    ).delete()


class SingleSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def _redirect_to_login(self, request):
        login_url = reverse("login")
        query_string = urlencode({"next": request.get_full_path()})
        return redirect(f"{login_url}?{query_string}")

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        cleanup_expired_active_sessions()

        try:
            max_active_sessions = int(get_license_limit("max_active_sessions", 1))
        except LicenseError:
            logout(request)
            messages.error(request, "الترخيص غير صالح أو منتهي.")
            return self._redirect_to_login(request)

        current_session_key = request.session.session_key

        if not current_session_key:
            request.session.save()
            current_session_key = request.session.session_key

        existing_session = ActiveUserSession.objects.filter(
            user=request.user
        ).first()

        # 1) سياسة نفس المستخدم:
        # إذا هذا المستخدم لا يسمح له بأكثر من جلسة،
        # وكان لديه جلسة مختلفة مسجلة، امنع الجلسة الجديدة.
        if (
            existing_session
            and existing_session.session_key
            and existing_session.session_key != current_session_key
            and not user_allows_multiple_sessions(request.user)
        ):
            logout(request)
            messages.error(
                request,
                "هذا المستخدم مسجل دخول من جهاز آخر، ولا يسمح له بأكثر من جلسة.",
            )
            return self._redirect_to_login(request)

        # 2) سجل أو حدث جلسة المستخدم الحالية.
        ActiveUserSession.objects.update_or_create(
            user=request.user,
            defaults={"session_key": current_session_key},
        )

        # 3) حد الترخيص العام:
        # احسب عدد المستخدمين النشطين، وإذا تجاوز الحد امنع المستخدم الحالي.
        active_count = (
            ActiveUserSession.objects.exclude(session_key__isnull=True)
            .exclude(session_key="")
            .count()
        )
        print(active_count,"active_countactive_countactive_count")

        if active_count > max_active_sessions:
            ActiveUserSession.objects.filter(user=request.user).delete()
            logout(request)

            messages.error(
                request,
                f"تم الوصول للحد الأعلى للجلسات النشطة حسب الترخيص: {max_active_sessions}",
            )

            return self._redirect_to_login(request)

        return self.get_response(request)