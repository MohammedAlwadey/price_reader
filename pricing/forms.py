from django import forms


class BarcodeForm(forms.Form):
    barcode = forms.CharField(
        label="",
        max_length=100,
        widget=forms.TextInput(attrs={
            "class": "barcode-input",
            "autofocus": "autofocus",
            "placeholder": "امسح الباركود أو اكتب الرقم",
            "inputmode": "numeric",
            "autocomplete": "off",
        }),
    )