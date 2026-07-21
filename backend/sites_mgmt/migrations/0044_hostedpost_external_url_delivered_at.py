from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0043_publicauditreport_lead_report_token'),
    ]

    operations = [
        migrations.AddField(
            model_name='hostedpost',
            name='external_url',
            field=models.URLField(
                blank=True,
                default='',
                help_text=(
                    "Live URL when this draft was built and published on the "
                    "client's OWN site by an agent (build-queue delivery). Empty "
                    "for Gridar-hosted posts and undelivered drafts. Its presence "
                    "means the article is live externally, so it drops out of the "
                    "build queue and can be tracked for proof attribution."
                ),
                max_length=500,
            ),
        ),
        migrations.AddField(
            model_name='hostedpost',
            name='delivered_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text=(
                    "When an agent reported this draft live on the client's "
                    "external site via gridar_mark_page_built."
                ),
            ),
        ),
    ]
