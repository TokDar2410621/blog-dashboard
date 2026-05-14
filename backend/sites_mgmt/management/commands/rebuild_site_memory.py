"""Bulk-rebuild SiteMemory rows for one site (or all sites).

Use cases:
  - Initial backfill after deploying RAG (run once per existing site)
  - Re-index after changing embedding model or chunk size
  - Recover from a long VOYAGE_API_KEY outage where signals failed silently

Run locally:
    python manage.py rebuild_site_memory --site=6
    python manage.py rebuild_site_memory --all
    python manage.py rebuild_site_memory --site=6 --dry-run

On Railway:
    railway ssh
    python manage.py rebuild_site_memory --site=6
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from sites_mgmt.memory_index import index_source
from sites_mgmt.models import HostedPost, Site, SiteMemory


class Command(BaseCommand):
    help = (
        "Rebuild SiteMemory for one or all sites: re-chunks and re-embeds "
        "all HostedPost(status=published) + Site.knowledge_base into "
        "SiteMemory rows. Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument('--site', type=int, default=None,
                            help='Site ID to rebuild. Mutually exclusive with --all.')
        parser.add_argument('--all', action='store_true',
                            help='Rebuild every site. Use with care - hits Voyage API for each chunk.')
        parser.add_argument('--wipe', action='store_true',
                            help='Delete all existing SiteMemory rows for the site before rebuilding.')
        parser.add_argument('--dry-run', action='store_true',
                            help='Show what would be indexed without calling the embedding API.')

    def handle(self, *args, **options):
        site_id = options.get('site')
        do_all = options.get('all')
        wipe = options.get('wipe')
        dry_run = options.get('dry_run')

        if not site_id and not do_all:
            raise CommandError('Tu dois passer --site=<id> OU --all.')
        if site_id and do_all:
            raise CommandError('--site et --all sont mutuellement exclusifs.')

        if site_id:
            sites = [Site.objects.get(pk=site_id)]
        else:
            sites = list(Site.objects.filter(is_active=True))

        self.stdout.write(self.style.HTTP_INFO(
            f"Sites a traiter: {len(sites)}"
        ))

        for site in sites:
            self.stdout.write('')
            self.stdout.write(self.style.HTTP_INFO(
                f"--- Site #{site.id}: {site.name} ({site.domain}) ---"
            ))

            if wipe:
                deleted, _ = SiteMemory.objects.filter(site=site).delete()
                self.stdout.write(f"  Wipe: {deleted} memoires supprimees.")

            # 1. Knowledge base
            if site.knowledge_base:
                if dry_run:
                    self.stdout.write(
                        f"  [DRY] indexerait KB ({len(site.knowledge_base)} chars)"
                    )
                else:
                    r = index_source(
                        site=site, kind='kb', content=site.knowledge_base,
                        source_ref='site-kb', title='Knowledge base',
                    )
                    self.stdout.write(
                        f"  KB: created={r.get('created', 0)}, reused={r.get('reused', 0)}"
                        + (f", error={r['error']}" if r.get('error') else '')
                    )
            else:
                self.stdout.write("  KB: (vide, skip)")

            # 2. HostedPost articles (only hosted-mode sites have these)
            posts = HostedPost.objects.filter(site=site, status='published')
            self.stdout.write(f"  Articles publies: {posts.count()}")
            for p in posts:
                full = f"# {p.title}\n\n{p.content or ''}"
                if dry_run:
                    self.stdout.write(f"    [DRY] {p.slug}")
                    continue
                r = index_source(
                    site=site, kind='article', content=full,
                    source_ref=f'hosted:{p.slug}', title=p.title,
                )
                tag = self.style.SUCCESS if r.get('created') else 'NOTE'
                self.stdout.write(
                    f"    {p.slug}: created={r.get('created', 0)}, "
                    f"reused={r.get('reused', 0)}"
                    + (f", error={r['error']}" if r.get('error') else '')
                )

            # Stats finales
            counts = (
                SiteMemory.objects.filter(site=site)
                .values_list('kind', flat=True)
            )
            from collections import Counter
            stats = Counter(counts)
            self.stdout.write(self.style.SUCCESS(
                f"  Total memoires: {sum(stats.values())} ({dict(stats)})"
            ))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('Done.'))
