# The command topic of an actionner is renamed, so that the state topic it now
# reports on can sit beside it under a name that says which way round it goes.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("plant_management", "0012_growingplant_auto_watering"),
    ]

    operations = [
        migrations.RenameField(
            model_name="actionner",
            old_name="mqtt_topic",
            new_name="mqtt_topic_out",
        ),
        migrations.AlterField(
            model_name="actionner",
            name="mqtt_topic_out",
            field=models.CharField(max_length=200, verbose_name="topic MQTT (commande)"),
        ),
        migrations.AddField(
            model_name="actionner",
            name="mqtt_topic_in",
            field=models.CharField(blank=True, max_length=200, verbose_name="topic MQTT (état)"),
        ),
        migrations.AddField(
            model_name="actionner",
            name="state_payload_label",
            field=models.CharField(blank=True, default="state", max_length=120,
                                   verbose_name="état (clé du payload)"),
        ),
    ]
