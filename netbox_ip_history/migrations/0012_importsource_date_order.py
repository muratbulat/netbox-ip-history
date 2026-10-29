from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('netbox_ip_history', '0011_legacy_source_types'),
    ]

    operations = [
        migrations.AddField(
            model_name='importsource',
            name='date_order',
            field=models.CharField(default='dmy', max_length=3),
        ),
    ]
