import django.db.models.deletion
import taggit.managers
import utilities.json
from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def repair_data(apps, schema_editor):
    """
    - Dry runs no longer create ImportJobs: remove those left behind by earlier versions.
    - Native NetBox events are no longer tied to a synthetic import job.
    - Store the global table as an empty VRF name, never the literal "Global".
    """
    ImportJob = apps.get_model("netbox_ip_history", "ImportJob")
    HistoricalIPEvent = apps.get_model("netbox_ip_history", "HistoricalIPEvent")

    ImportJob.objects.filter(status="dry_run", events__isnull=True).delete()
    ImportJob.objects.filter(status="dry_run").update(status="completed")

    native = HistoricalIPEvent.objects.filter(source__slug="netbox")
    native.update(import_job=None)
    ImportJob.objects.filter(source__slug="netbox", filename="native_netbox_sync", events__isnull=True).delete()

    HistoricalIPEvent.objects.filter(Q(vrf_name__iexact="global") & Q(vrf_rd="")).update(vrf_name="")
    ImportJob.objects.filter(status="running").update(status="failed")


class Migration(migrations.Migration):

    dependencies = [
        ('extras', '0144_customfield_status'),
        ('ipam', '0097_merge_ipaddress_host_index_and_multi_protocol_services'),
        ('netbox_ip_history', '0001_squashed_0007'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='historicalipevent',
            options={'ordering': ('-timestamp', '-pk')},
        ),
        migrations.RemoveIndex(
            model_name='historicalipevent',
            name='netbox_ip_h_ip_addr_883ca1_idx',
        ),
        migrations.RemoveIndex(
            model_name='historicalipevent',
            name='netbox_ip_h_source__577fd7_idx',
        ),
        migrations.RemoveIndex(
            model_name='historicalipevent',
            name='netbox_ip_h_vrf_nam_068191_idx',
        ),
        migrations.RemoveIndex(
            model_name='historicalipevent',
            name='netbox_ip_h_import__1a5e0c_idx',
        ),
        migrations.RenameIndex(
            model_name='historicalipevent',
            new_name='nih_event_type_time',
            old_name='netbox_ip_h_event_t_7b92da_idx',
        ),
        migrations.RemoveField(
            model_name='importjob',
            name='dry_run',
        ),
        migrations.RemoveField(
            model_name='importsource',
            name='authority',
        ),
        migrations.RemoveField(
            model_name='importsource',
            name='capabilities',
        ),
        migrations.RemoveField(
            model_name='importsource',
            name='inspection',
        ),
        migrations.RemoveField(
            model_name='importsource',
            name='support_level',
        ),
        migrations.AddField(
            model_name='historicalipevent',
            name='created',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalipevent',
            name='custom_field_data',
            field=models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
        ),
        migrations.AddField(
            model_name='historicalipevent',
            name='last_updated',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name='historicalipevent',
            name='tags',
            field=taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag'),
        ),
        migrations.AddField(
            model_name='importjob',
            name='created',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AddField(
            model_name='importjob',
            name='custom_field_data',
            field=models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
        ),
        migrations.AddField(
            model_name='importjob',
            name='last_updated',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AddField(
            model_name='importjob',
            name='tags',
            field=taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag'),
        ),
        migrations.AddField(
            model_name='importsource',
            name='custom_field_data',
            field=models.JSONField(blank=True, default=dict, encoder=utilities.json.CustomFieldJSONEncoder),
        ),
        migrations.AddField(
            model_name='importsource',
            name='tags',
            field=taggit.managers.TaggableManager(through='extras.TaggedItem', to='extras.Tag'),
        ),
        migrations.AlterField(
            model_name='historicalipevent',
            name='fingerprint',
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
        migrations.AlterField(
            model_name='historicalipevent',
            name='import_job',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='events', to='netbox_ip_history.importjob'),
        ),
        migrations.AlterField(
            model_name='historicalipevent',
            name='raw_data',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AlterField(
            model_name='historicalipevent',
            name='related_netbox_ip',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to='ipam.ipaddress'),
        ),
        migrations.AlterField(
            model_name='importjob',
            name='status',
            field=models.CharField(default='pending', max_length=20),
        ),
        migrations.AlterField(
            model_name='importjob',
            name='user',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='+', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='importsource',
            name='created',
            field=models.DateTimeField(auto_now_add=True, null=True),
        ),
        migrations.AlterField(
            model_name='importsource',
            name='last_updated',
            field=models.DateTimeField(auto_now=True, null=True),
        ),
        migrations.AlterField(
            model_name='importsource',
            name='slug',
            field=models.SlugField(max_length=100, unique=True),
        ),
        migrations.AddIndex(
            model_name='historicalipevent',
            index=models.Index(fields=['ip_address', 'vrf_name', '-timestamp'], name='nih_event_ip_vrf_time'),
        ),
        migrations.AddIndex(
            model_name='historicalipevent',
            index=models.Index(fields=['source', '-timestamp'], name='nih_event_source_time'),
        ),
        migrations.AddIndex(
            model_name='historicalipevent',
            index=models.Index(fields=['import_job'], name='nih_event_job'),
        ),
        migrations.RunPython(repair_data, migrations.RunPython.noop),
    ]
