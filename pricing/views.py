from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from .forms import BarcodeForm
from .services.oracle_client import find_price_by_barcode, get_active_settings


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
                    product = results[0] if results else None

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