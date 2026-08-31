from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ip_history', '0002_source_profiles'),
    ]

    operations = [
        migrations.AlterField(
            model_name='historicalipevent',
            name='custom_fields_snapshot',
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddIndex(
            model_name='historicalipevent',
            index=models.Index(fields=['source', 'ip_address'], name='netbox_ip_h_source__55f448_idx'),
        ),
        migrations.AddIndex(
            model_name='historicalipevent',
            index=models.Index(fields=['event_type', '-timestamp'], name='netbox_ip_h_event_t_2b31f7_idx'),
        ),
        migrations.AddIndex(
            model_name='historicalipevent',
            index=models.Index(fields=['vrf_name', 'vrf_rd', 'ip_address'], name='netbox_ip_h_vrf_nam_bdf416_idx'),
        ),
        migrations.AddIndex(
            model_name='historicalipevent',
            index=models.Index(fields=['import_job', 'ip_address'], name='netbox_ip_h_import__864436_idx'),
        ),
    ]
