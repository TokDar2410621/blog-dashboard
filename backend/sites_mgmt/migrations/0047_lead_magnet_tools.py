# Generated manually
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('sites_mgmt', '0046_site_indexnow_key'),
    ]

    operations = [
        migrations.AddField(
            model_name='lead',
            name='company_name',
            field=models.CharField(blank=True, default='', help_text='Auto-detected from the site title or meta.', max_length=200),
        ),
        migrations.AddField(
            model_name='lead',
            name='estimated_monthly_traffic',
            field=models.IntegerField(blank=True, help_text='Estimated organic traffic at capture time.', null=True),
        ),
        migrations.AddField(
            model_name='lead',
            name='first_tool',
            field=models.CharField(blank=True, default='public_audit', help_text='Which lead-magnet tool first captured this lead.', max_length=30),
        ),
        migrations.AddField(
            model_name='lead',
            name='lead_score',
            field=models.IntegerField(blank=True, help_text='Automated 0-100 score based on site size, SEO potential, industry, and commercial opportunity.', null=True),
        ),
        migrations.CreateModel(
            name='ToolAnalysis',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('domain', models.CharField(db_index=True, max_length=255)),
                ('tool', models.CharField(choices=[('audit', 'Audit SEO'), ('ai_visibility', 'AI Visibility Checker'), ('competitor_gap', 'Competitor Gap Finder'), ('can_i_rank', 'Can I Rank?'), ('competitor_compare', 'Competitor Comparison'), ('ai_citation', 'AI Citation Checker'), ('seo_roi', 'SEO ROI Calculator')], db_index=True, max_length=30)),
                ('status', models.CharField(choices=[('pending', 'En attente'), ('running', 'En cours'), ('completed', 'Termine'), ('failed', 'Echoue')], default='pending', max_length=20)),
                ('score', models.IntegerField(blank=True, help_text='Primary score (0-100) produced by the tool.', null=True)),
                ('result', models.JSONField(blank=True, default=dict, help_text='Full result payload returned by the tool.')),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('user_agent', models.CharField(blank=True, default='', max_length=500)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('lead', models.ForeignKey(blank=True, help_text='Linked after the visitor provides their email.', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='tool_analyses', to='sites_mgmt.lead')),
            ],
            options={
                'verbose_name': 'Analyse outil (lead magnet)',
                'verbose_name_plural': 'Analyses outils (lead magnets)',
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ConversionEvent',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('event', models.CharField(choices=[('tool_view', 'Page vue'), ('domain_submitted', 'Domaine soumis'), ('analysis_started', 'Analyse lancee'), ('analysis_completed', 'Analyse terminee'), ('report_previewed', 'Apercu du rapport'), ('email_submitted', 'Email soumis'), ('report_opened', 'Rapport ouvert'), ('cta_clicked', 'CTA clique'), ('signup_started', 'Inscription commencee'), ('signup_completed', 'Inscription terminee')], db_index=True, max_length=30)),
                ('tool', models.CharField(blank=True, default='', max_length=30)),
                ('domain', models.CharField(blank=True, default='', max_length=255)),
                ('metadata', models.JSONField(blank=True, default=dict)),
                ('ip', models.GenericIPAddressField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(auto_now_add=True)),
                ('lead', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='conversion_events', to='sites_mgmt.lead')),
            ],
            options={
                'verbose_name': 'Evenement de conversion',
                'verbose_name_plural': 'Evenements de conversion',
                'ordering': ['-timestamp'],
            },
        ),
        migrations.AddIndex(
            model_name='toolanalysis',
            index=models.Index(fields=['domain', 'tool', '-created_at'], name='sites_mgmt__domain_c869fb_idx'),
        ),
        migrations.AddIndex(
            model_name='toolanalysis',
            index=models.Index(fields=['tool', '-created_at'], name='sites_mgmt__tool_79c884_idx'),
        ),
        migrations.AddIndex(
            model_name='conversionevent',
            index=models.Index(fields=['event', '-timestamp'], name='sites_mgmt__event_d7a5b3_idx'),
        ),
        migrations.AddIndex(
            model_name='conversionevent',
            index=models.Index(fields=['tool', '-timestamp'], name='sites_mgmt__tool_8dfb45_idx'),
        ),
    ]
