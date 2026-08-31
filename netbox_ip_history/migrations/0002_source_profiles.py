from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("netbox_ip_history", "0001_initial")]
    operations = [
        migrations.AddField(model_name="importsource", name="support_level", field=models.CharField(blank=True, max_length=20)),
        migrations.AddField(model_name="importsource", name="capabilities", field=models.JSONField(blank=True, default=list)),
        migrations.AddField(model_name="importsource", name="inspection", field=models.JSONField(blank=True, default=dict)),
        migrations.AddField(model_name="importsource", name="source_priority", field=models.PositiveIntegerField(default=100)),
        migrations.AddField(model_name="importsource", name="authority", field=models.JSONField(blank=True, default=dict)),
    ]