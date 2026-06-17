from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import TemplateView

from .forms import BarcodeForm
from .models import ActiveUserSession, user_allows_multiple_sessions
from .services.oracle_client import find_price_by_barcode, get_active_settings


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


class SingleSessionLoginView(LoginView):
    template_name = "registration/login.html"

    def form_valid(self, form):
        response = super().form_valid(form)

        user = self.request.user

        if user_allows_multiple_sessions(user):
            ActiveUserSession.objects.filter(user=user).delete()
            return response

        if not self.request.session.session_key:
            self.request.session.save()

        ActiveUserSession.objects.update_or_create(
            user=user,
            defaults={"session_key": self.request.session.session_key},
        )

        return response