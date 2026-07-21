from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0044_hostedpost_external_url_delivered_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='site',
            name='delivery_mode',
            field=models.CharField(
                choices=[
                    ('auto', 'Automatique (Gridar héberge, ou pousse au CMS / à la DB externe)'),
                    ('agent', 'Via un agent (le contenu est construit dans le repo du client)'),
                ],
                default='auto',
                help_text=(
                    "'agent' = site dev/custom que Gridar ne publie pas "
                    "directement (Next.js maison, etc.). Les articles sont mis en "
                    "staging (brouillon HostedPost) et servis dans la build-queue "
                    "pour qu'un agent les pose dans le repo du client, plutôt que "
                    "poussés vers un CMS ou une DB externe."
                ),
                max_length=10,
                verbose_name='Mode de livraison',
            ),
        ),
    ]
