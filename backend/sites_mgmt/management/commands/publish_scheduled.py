import logging
from datetime import date

from django.core.management.base import BaseCommand
from django.utils import timezone

from sites_mgmt.models import Site
from sites_mgmt.db_utils import ensure_site_connection
from blog.models import BlogPost

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Publish scheduled posts whose scheduled_at has passed.'

    def handle(self, *args, **options):
        now = timezone.now()
        total_published = 0

        sites = Site.objects.all()
        self.stdout.write(f"Checking {sites.count()} site(s) for scheduled posts...")

        for site in sites:
            try:
                alias = ensure_site_connection(site)
                scheduled = BlogPost.objects.using(alias).filter(
                    status='scheduled',
                    scheduled_at__lte=now,
                )
                count = scheduled.count()
                if count == 0:
                    continue

                for post in scheduled:
                    post.status = 'published'
                    post.published_at = date.today()
                    post.save(using=alias, update_fields=['status', 'published_at'])
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Published: "{post.title}" on site "{site.name}"'
                        )
                    )

                total_published += count

            except Exception as e:
                self.stderr.write(
                    self.style.ERROR(
                        f'  Error on site "{site.name}": {e}'
                    )
                )
                logger.exception(f"Error publishing scheduled posts for site {site.id}")

        self.stdout.write(
            self.style.SUCCESS(f"\nDone. {total_published} post(s) published.")
        )
