from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView

from .forms import BarcodeForm
from .models import ActiveUserSession, user_allows_multiple_sessions
from .services.oracle_client import find_price_by_barcode, get_active_settings
from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from .licensing import get_license_limit, LicenseError

from django.contrib.sessions.models import Session
from django.utils import timezone
from django.contrib.auth import SESSION_KEY


def display_value(value):
    if value in (None, ""):
        return None

    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}"
    except (TypeError, ValueError):
        return str(value)


def display_date(value):
    if not value:
        return ""

    if hasattr(value, "strftime"):
        return value.strftime("%Y-%m-%d")

    return str(value)


def enrich_promotion(product):
    if not product or not product.get("has_promotion"):
        return product

    promotion = product.get("promotion") or {}
    promotion_type = product.get("promotion_type")
    promotion_label = product.get("promotion_label") or "عرض ترويجي"

    product["promotion_title"] = promotion_label
    product["promotion_name"] = "عرض ترويجي فعال"
    product["promotion_from"] = display_date(promotion.get("f_date"))
    product["promotion_to"] = display_date(promotion.get("t_date"))

    if promotion_type == "free_quantity":
        buy_qty = display_value(promotion.get("qt_qty") or promotion.get("f_qty"))
        free_qty = display_value(promotion.get("free_qty"))
        free_item = promotion.get("qt_i_code")

        parts = []

        if buy_qty:
            parts.append(f"عند شراء {buy_qty}")

        if free_qty:
            parts.append(f"تحصل على {free_qty} مجانًا")

        if free_item:
            parts.append(f"الصنف المجاني: {free_item}")

        product["promotion_details"] = " - ".join(parts) or "العرض يحتوي على كمية مجانية"

    elif promotion_type == "discount":
        discount_value = display_value(promotion.get("disc_amt_per"))

        parts = []

        if discount_value:
            parts.append(f"قيمة الخصم: {discount_value}%")

        product["promotion_details"] = " - ".join(parts) or "العرض يحتوي على خصم"

    else:
        product["promotion_details"] = "يوجد عرض ترويجي فعال على هذا الصنف"

    return product


class BarcodeLookupView(LoginRequiredMixin, TemplateView):
    template_name = "pricing/barcode_lookup.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        config = get_active_settings()
        form = BarcodeForm(self.request.GET or None)

        product = None
        error = None
        searched = False

        if self.request.GET:
            searched = True

            if form.is_valid():
                barcode = form.cleaned_data["barcode"]

                try:
                    results = find_price_by_barcode(barcode)

                    if results:
                        product = enrich_promotion(results[0])

                    if not product:
                        error = "لم يتم العثور على صنف بهذا الباركود"

                except Exception:
                    error = "تعذر جلب بيانات الصنف. راجع إعدادات الاتصال أو تواصل مع المسؤول."

        context["company_name"] = config.company_name if config else "قارى الأسعار"
        context["form"] = form
        context["product"] = product
        context["error"] = error
        context["searched"] = searched

        return context


def cleanup_expired_active_sessions():
    valid_session_keys = set(
        Session.objects.filter(expire_date__gt=timezone.now())
        .values_list("session_key", flat=True)
    )

    ActiveUserSession.objects.exclude(
        session_key__in=valid_session_keys
    ).delete()


class SingleSessionLoginView(LoginView):
    template_name = "registration/login.html"

    def _get_user_active_session_keys(self, user):
        user_id = str(user.pk)
        session_keys = []

        sessions = Session.objects.filter(expire_date__gt=timezone.now())

        for session in sessions:
            data = session.get_decoded()
            if data.get(SESSION_KEY) == user_id:
                session_keys.append(session.session_key)

        return session_keys

    def _kick_old_user_sessions(self, user):
        old_session_keys = self._get_user_active_session_keys(user)

        if old_session_keys:
            Session.objects.filter(session_key__in=old_session_keys).delete()

        ActiveUserSession.objects.filter(user=user).delete()

        return len(old_session_keys)

    def form_valid(self, form):
        cleanup_expired_active_sessions()

        user = form.get_user()

        try:
            max_active_sessions = int(get_license_limit("max_active_sessions", 1))
        except LicenseError:
            messages.error(self.request, "الترخيص غير صالح أو منتهي.")
            return redirect("login")

        allow_multi = user_allows_multiple_sessions(user)

        # إذا المستخدم غير مسموح له بأكثر من جلسة:
        # احذف أي جلسة قديمة له واسمح بالدخول الجديد.
        if not allow_multi:
            kicked_count = self._kick_old_user_sessions(user)

            if kicked_count:
                messages.info(
                    self.request,
                    "تم إنهاء الجلسة السابقة لهذا المستخدم .",
                )

        # بعد تنظيف جلسات نفس المستخدم، احسب حد الترخيص العام.
        active_count = (
            ActiveUserSession.objects.exclude(session_key__isnull=True)
            .exclude(session_key="")
            .count()
        )

        # لو المستخدم يسمح له بجلسات متعددة، دخوله الجديد سيضيف جلسة ضمن حد الترخيص.
        # لو لا يسمح له بجلسات متعددة، القديمة انحذفت قبل العد.
        if active_count >= max_active_sessions:
            messages.error(
                self.request,
                f"تم الوصول للحد الأعلى للجلسات النشطة حسب الترخيص: {max_active_sessions}",
            )
            return redirect("login")

        response = super().form_valid(form)

        if not self.request.session.session_key:
            self.request.session.save()

        ActiveUserSession.objects.update_or_create(
            user=user,
            defaults={"session_key": self.request.session.session_key},
        )

        return response
    

