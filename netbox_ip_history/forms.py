from django import forms
from django.utils.translation import gettext_lazy as _
from netbox.forms import NetBoxModelBulkEditForm, NetBoxModelFilterSetForm, NetBoxModelForm
from netbox.plugins import get_plugin_config
from utilities.forms import BOOLEAN_WITH_BLANK_CHOICES, add_blank_choice
from utilities.forms.fields import DynamicModelMultipleChoiceField, SlugField, TagFilterField
from utilities.forms.rendering import FieldSet
from utilities.forms.widgets import BulkEditNullBooleanSelect, DateTimePicker

from .choices import EventTypeChoices, ImportStatusChoices, SourceTypeChoices
from .importers import importer_for
from .models import HistoricalIPEvent, ImportJob, ImportSource
from .services.normalize import RecordError, normalize_ip

__all__ = (
    "CompareForm",
    "HistoricalIPEventFilterForm",
    "ImportForm",
    "ImportJobFilterForm",
    "ImportJobForm",
    "ImportSourceBulkEditForm",
    "ImportSourceFilterForm",
    "ImportSourceForm",
    "TimelineSearchForm",
)


#
# Import sources
#

class ImportSourceForm(NetBoxModelForm):
    slug = SlugField()

    fieldsets = (
        FieldSet("name", "slug", "source_type", "enabled", "description", "tags", name=_("Source")),
        FieldSet("source_timezone", "source_priority", "field_mapping", name=_("Parsing")),
    )

    class Meta:
        model = ImportSource
        fields = (
            "name", "slug", "source_type", "enabled", "description", "source_timezone", "source_priority",
            "field_mapping", "tags",
        )
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}


class ImportSourceBulkEditForm(NetBoxModelBulkEditForm):
    model = ImportSource
    source_type = forms.ChoiceField(
        choices=add_blank_choice(SourceTypeChoices), required=False, label=_("Source type")
    )
    enabled = forms.NullBooleanField(required=False, widget=BulkEditNullBooleanSelect, label=_("Enabled"))
    source_timezone = forms.CharField(max_length=64, required=False, label=_("Source timezone"))
    source_priority = forms.IntegerField(min_value=0, required=False, label=_("Priority"))
    description = forms.CharField(required=False, label=_("Description"))

    fieldsets = (FieldSet("source_type", "enabled", "source_timezone", "source_priority", "description"),)
    nullable_fields = ("source_timezone", "description")


class ImportSourceFilterForm(NetBoxModelFilterSetForm):
    model = ImportSource
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("source_type", "enabled", name=_("Source")),
    )
    source_type = forms.MultipleChoiceField(choices=SourceTypeChoices, required=False, label=_("Type"))
    enabled = forms.NullBooleanField(
        required=False, widget=forms.Select(choices=BOOLEAN_WITH_BLANK_CHOICES), label=_("Enabled")
    )
    tag = TagFilterField(model)


#
# Import jobs
#

class ImportJobForm(NetBoxModelForm):
    fieldsets = (FieldSet("tags", name=_("Import job")),)

    class Meta:
        model = ImportJob
        fields = ("tags",)


class ImportJobFilterForm(NetBoxModelFilterSetForm):
    model = ImportJob
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("source_id", "status", name=_("Job")),
    )
    source_id = DynamicModelMultipleChoiceField(
        queryset=ImportSource.objects.all(), required=False, label=_("Source")
    )
    status = forms.MultipleChoiceField(choices=ImportStatusChoices, required=False, label=_("Status"))
    tag = TagFilterField(model)


#
# Events
#

class HistoricalIPEventFilterForm(NetBoxModelFilterSetForm):
    model = HistoricalIPEvent
    fieldsets = (
        FieldSet("q", "filter_id", "tag"),
        FieldSet("ip_address", "vrf", "event_type", "source_id", "import_job_id", name=_("Event")),
        FieldSet("timestamp_after", "timestamp_before", name=_("Time")),
        FieldSet("owner_name", "dns_name", "mac_address", "source_username", name=_("Attributes")),
    )
    ip_address = forms.CharField(required=False, label=_("IP address"))
    vrf = forms.CharField(required=False, label=_("VRF"), help_text=_("Name, RD, or 'Global'"))
    event_type = forms.MultipleChoiceField(choices=EventTypeChoices, required=False, label=_("Event type"))
    source_id = DynamicModelMultipleChoiceField(
        queryset=ImportSource.objects.all(), required=False, label=_("Source")
    )
    import_job_id = DynamicModelMultipleChoiceField(
        queryset=ImportJob.objects.all(), required=False, label=_("Import job")
    )
    timestamp_after = forms.DateTimeField(required=False, widget=DateTimePicker(), label=_("After"))
    timestamp_before = forms.DateTimeField(required=False, widget=DateTimePicker(), label=_("Before"))
    owner_name = forms.CharField(required=False, label=_("Owner"))
    dns_name = forms.CharField(required=False, label=_("DNS name"))
    mac_address = forms.CharField(required=False, label=_("MAC address"))
    source_username = forms.CharField(required=False, label=_("User"))
    tag = TagFilterField(model)


#
# Workflows
#

class BootstrapFormMixin:
    """Bootstrap classes for plain (non-NetBox-model) workflow forms rendered field by field."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                css = "form-check-input"
            elif isinstance(widget, forms.Select):
                css = "form-select"
            else:
                css = "form-control"
            widget.attrs["class"] = f"{widget.attrs.get('class', '')} {css}".strip()


def _clean_ip(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        return normalize_ip(value)[0]
    except RecordError as exc:
        raise forms.ValidationError(_("Enter a valid IPv4 or IPv6 address.")) from exc


class TimelineSearchForm(BootstrapFormMixin, forms.Form):
    ip = forms.CharField(
        required=False,
        label=_("IP address"),
        widget=forms.TextInput(attrs={"placeholder": "192.0.2.10 / 2001:db8::10", "autofocus": True}),
    )
    vrf = forms.CharField(required=False, label=_("VRF"), help_text=_("Name, RD, or 'Global'"))
    source = forms.CharField(required=False, label=_("Source"))
    event_type = forms.ChoiceField(
        choices=add_blank_choice(EventTypeChoices), required=False, label=_("Event type")
    )
    date_from = forms.DateField(required=False, label=_("From"), widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, label=_("To"), widget=forms.DateInput(attrs={"type": "date"}))
    owner = forms.CharField(required=False, label=_("Owner / host"))
    username = forms.CharField(required=False, label=_("User"))
    oldest_first = forms.BooleanField(required=False, label=_("Oldest first"))

    def clean_ip(self):
        return _clean_ip(self.cleaned_data.get("ip"))

    def timeline_kwargs(self) -> dict:
        data = dict(self.cleaned_data)
        return {
            "ip_address": data.pop("ip"),
            **{k: v for k, v in data.items() if k in (
                "vrf", "source", "event_type", "oldest_first", "date_from", "date_to", "owner", "username",
            )},
        }


class CompareForm(BootstrapFormMixin, forms.Form):
    ip = forms.CharField(
        required=False,
        label=_("IP address"),
        widget=forms.TextInput(attrs={"placeholder": "192.0.2.10 / 2001:db8::10", "autofocus": True}),
    )

    def clean_ip(self):
        return _clean_ip(self.cleaned_data.get("ip"))


class ImportForm(BootstrapFormMixin, forms.Form):
    source = forms.ModelChoiceField(queryset=ImportSource.objects.none(), label=_("Source"))
    file = forms.FileField(label=_("File"), help_text=_("CSV, JSON / JSON Lines, or XML export."))
    format = forms.ChoiceField(
        choices=(("csv", "CSV"), ("json", "JSON"), ("xml", "XML")), initial="csv", label=_("Format")
    )
    delimiter = forms.CharField(max_length=1, initial=",", required=False, label=_("CSV delimiter"))
    dry_run = forms.BooleanField(
        initial=True,
        required=False,
        label=_("Dry run"),
        help_text=_("Validate and preview without saving anything."),
    )
    background = forms.BooleanField(
        required=False,
        label=_("Run as background job"),
        help_text=_("Large files are always queued; dry runs always run immediately."),
    )

    fieldsets = (
        FieldSet("source", "file", "format", "delimiter", name=_("Input")),
        FieldSet("dry_run", "background", name=_("Options")),
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        sources = ImportSource.objects.filter(enabled=True).exclude(source_type=SourceTypeChoices.NETBOX)
        self.fields["source"].queryset = sources.restrict(user, "view") if user is not None else sources

    def clean_file(self):
        upload = self.cleaned_data["file"]
        limit = get_plugin_config("netbox_ip_history", "max_upload_size")
        if upload.size > limit:
            raise forms.ValidationError(
                _("File is larger than the {limit} MB upload limit.").format(limit=limit // (1024 * 1024))
            )
        return upload

    def clean(self):
        cleaned = super().clean()
        source, fmt = cleaned.get("source"), cleaned.get("format")
        if source and fmt and fmt not in importer_for(source.source_type).formats:
            self.add_error(
                "format",
                _("{source} imports accept: {formats}.").format(
                    source=source.get_source_type_display(),
                    formats=", ".join(importer_for(source.source_type).formats),
                ),
            )
        return cleaned
