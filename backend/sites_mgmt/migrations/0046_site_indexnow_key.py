from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0045_site_delivery_mode'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='indexnow_key',
            field=models.CharField(
                blank=True,
                default='',
                help_text=(
                    "Cle IndexNow (hex) generee a la 1re utilisation. Le site "
                    "heberge un fichier <cle>.txt a sa racine pour prouver la "
                    "propriete. Sert a soumettre les URLs a Bing/Yandex/Seznam/"
                    "Naver (pas Google). Non sensible seule."
                ),
                max_length=64,
                verbose_name='IndexNow - cle',
            ),
        ),
    ]
