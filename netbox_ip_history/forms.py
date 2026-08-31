try:
    from django import forms
    from django.utils.translation import gettext_lazy as _
except ImportError:
    # Lightweight fallback for standalone environments
    forms = None
    _ = lambda s: s

if forms:
    from .choices import EventType
    from .models import ImportSource

    class HistorySearchForm(forms.Form):
        ip = forms.CharField(
            required=False,
            label=_("IP Address"),
            widget=forms.TextInput(
                attrs={
                    "class": "form-control font-monospace",
                    "placeholder": _("e.g. 192.168.1.1, 10.0.0.1/24, or 2001:db8::1"),
                    "autofocus": "autofocus",
                }
            ),
        )

        def clean_ip(self):
            raw = (self.cleaned_data.get("ip") or "").strip()
            if "/" in raw:
                raw = raw.split("/", 1)[0].strip()
            return raw
        vrf = forms.CharField(
            required=False,
            label=_("VRF / Scope"),
            widget=forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("VRF name, RD, or Global"),
                }
            ),
        )
        source = forms.CharField(
            required=False,
            label=_("Data Source"),
            widget=forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("e.g. NetBox, phpIPAM, gestioip"),
                }
            ),
        )
        event_type = forms.ChoiceField(
            required=False,
            label=_("Event Type"),
            choices=[("", _("All Event Types"))] + list(EventType.choices),
            widget=forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        )
        date_from = forms.DateField(
            required=False,
            label=_("From Date"),
            widget=forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                }
            ),
        )
        date_to = forms.DateField(
            required=False,
            label=_("To Date"),
            widget=forms.DateInput(
                attrs={
                    "type": "date",
                    "class": "form-control",
                }
            ),
        )
        owner = forms.CharField(
            required=False,
            label=_("Host / Owner"),
            widget=forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("Hostname, device, or owner name"),
                }
            ),
        )
        username = forms.CharField(
            required=False,
            label=_("Username"),
            widget=forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": _("User / author"),
                }
            ),
        )
        oldest_first = forms.BooleanField(
            required=False,
            label=_("Sort oldest first"),
            widget=forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
        )

    class ImportForm(forms.Form):
        source = forms.ModelChoiceField(
            queryset=ImportSource.objects.filter(enabled=True),
            label=_("Import Source Profile"),
            empty_label=_("Select target source configuration..."),
            widget=forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        )
        file = forms.FileField(
            label=_("Export / History File"),
            widget=forms.FileInput(
                attrs={
                    "class": "form-control",
                    "accept": ".csv,.json,.jsonl,.txt",
                }
            ),
            help_text=_("Upload CSV, JSON, or JSON Lines export file."),
        )
        format = forms.ChoiceField(
            choices=(
                ("csv", _("CSV (Comma / Custom Delimited)")),
                ("json", _("JSON / JSON Lines")),
            ),
            label=_("File Format"),
            widget=forms.Select(
                attrs={
                    "class": "form-select",
                }
            ),
        )
        delimiter = forms.CharField(
            max_length=2,
            initial=",",
            required=False,
            label=_("CSV Delimiter"),
            widget=forms.TextInput(
                attrs={
                    "class": "form-control font-monospace",
                    "placeholder": ",",
                }
            ),
            help_text=_("Field separator (default is comma ',')"),
        )
        dry_run = forms.BooleanField(
            initial=True,
            required=False,
            label=_("Dry run (simulation mode)"),
            widget=forms.CheckboxInput(
                attrs={
                    "class": "form-check-input",
                }
            ),
            help_text=_("Validate and preview records without saving changes to the database."),
        )
else:
    class HistorySearchForm:
        def __init__(self, data=None, *args, **kwargs):
            self.data = data or {}
            self.cleaned_data = {}

        def is_valid(self):
            raw = (self.data.get("ip") or "").strip()
            if "/" in raw:
                raw = raw.split("/", 1)[0].strip()
            self.cleaned_data = {"ip": raw}
            return True

    class ImportForm:
        def __init__(self, *args, **kwargs):
            pass
