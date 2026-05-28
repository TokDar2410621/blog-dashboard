from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0032_allow_null_published_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='autopilot_auto_publish',
            field=models.BooleanField(
                default=False,
                help_text="Si actif, les articles générés par l'autopilote sont publiés directement (sans passer par draft). Désactivé par défaut pour garder une étape de review.",
                verbose_name='Publication automatique',
            ),
        ),
    ]
