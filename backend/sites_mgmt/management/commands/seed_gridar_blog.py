"""Migrate the static `posts/*.md` files into the Gridar marketing blog
HostedPost table so the same content is editable from the dashboard.

Run on Railway:
    railway ssh
    python manage.py seed_gridar_blog

Idempotent: re-running updates existing posts in place (matched by slug).

Steps:
  1. Find (or create) the Site row for gridar.app in hosted mode, owned by
     the first superuser.
  2. For each .md file in /app/posts (or repo root /posts/), parse the YAML
     frontmatter and upsert a HostedPost.
  3. Print the final Site ID so it can be wired into VITE_GRIDAR_BLOG_SITE_ID.
"""
from __future__ import annotations

import re
from datetime import date as date_cls, datetime
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from sites_mgmt.models import HostedPost, HostedTag, Site


def parse_frontmatter(raw: str):
    """Return ({key: value}, body). Mirrors the JS parser in src/lib/posts.ts."""
    m = re.match(r'^---\s*\n([\s\S]*?)\n---\s*\n?([\s\S]*)$', raw)
    if not m:
        return {}, raw
    meta: dict[str, object] = {}
    for line in m.group(1).split('\n'):
        colon = line.find(':')
        if colon == -1:
            continue
        key = line[:colon].strip()
        value = line[colon + 1:].strip()
        # Strip surrounding quotes
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        # YAML-flow array: [foo, bar]
        if value.startswith('[') and value.endswith(']'):
            inner = value[1:-1]
            meta[key] = [
                s.strip().strip('"').strip("'")
                for s in inner.split(',')
                if s.strip()
            ]
        else:
            meta[key] = value
    return meta, m.group(2)


def find_posts_dir() -> Path | None:
    """Locate the posts/ folder either inside the Railway container (/app/posts)
    or in the local repo (../posts relative to backend/)."""
    candidates = [
        Path(settings.BASE_DIR).parent / 'posts',  # /app/posts on Railway
        Path(settings.BASE_DIR) / '..' / 'posts',  # local dev
        Path('/app/posts'),
    ]
    for c in candidates:
        if c.exists() and c.is_dir():
            return c.resolve()
    return None


class Command(BaseCommand):
    help = (
        "Migrate posts/*.md into HostedPost rows for the canonical Gridar "
        "marketing blog site (gridar.app, hosted mode). Idempotent."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--domain', default='gridar.app',
            help="Domain to look up or create the Site for (default: gridar.app)",
        )
        parser.add_argument(
            '--owner', default=None,
            help="Username of the owner. Defaults to the first superuser.",
        )
        parser.add_argument(
            '--language', default='fr',
            help="Language code to tag the imported posts with (default: fr).",
        )
        parser.add_argument(
            '--force-hosted', action='store_true',
            help=(
                "If the matching Site is NOT in hosted mode (has database_url, "
                "wp_url, shopify_domain or webflow_token), wipe those fields "
                "so the blog routes can serve from HostedPost. Destructive: "
                "any data in the external Postgres pointed at by database_url "
                "stays where it is, but the Site row will no longer reference it."
            ),
        )

    def handle(self, *args, **options):
        User = get_user_model()

        # 1. Resolve owner
        if options['owner']:
            try:
                owner = User.objects.get(username=options['owner'])
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(
                    f"User '{options['owner']}' not found."
                ))
                return
        else:
            owner = User.objects.filter(is_superuser=True).order_by('id').first()
            if not owner:
                self.stderr.write(self.style.ERROR(
                    "No superuser found. Run `python manage.py createsuperuser` first, "
                    "or pass --owner=<username>."
                ))
                return
        self.stdout.write(f"Owner: {owner.username} ({owner.email})")

        # 2. Resolve / create Site
        domain = options['domain']
        site = Site.objects.filter(domain=domain).first()
        if site is None:
            site = Site.objects.create(
                name='Gridar (blog marketing)',
                domain=domain,
                owner=owner,
                description='Le blog Gridar - tactiques SEO concrètes pour PME québécoises',
                default_language=options['language'],
                available_languages=[options['language']],
                default_author='Darius Tokam',
                author_role='Fondateur, Arivex Studio',
                author_bio=(
                    "Fondateur de Gridar et d'Arivex Studio. Solo founder basé à "
                    "Saint-Hyacinthe, QC. Spécialiste SEO bilingue FR-CA."
                ),
                # Hosted mode: no database_url, no wp_url, no shopify, no webflow
            )
            self.stdout.write(self.style.SUCCESS(
                f"Created Site #{site.id} for {domain} (hosted mode)."
            ))
        else:
            self.stdout.write(f"Using existing Site #{site.id} for {domain}.")
            if not site.is_hosted:
                if options['force_hosted']:
                    self.stdout.write(self.style.WARNING(
                        "  --force-hosted: wiping database_url + CMS fields to convert to hosted mode..."
                    ))
                    site.database_url = ''
                    site.wp_url = ''
                    site.wp_username = ''
                    site.wp_app_password = ''
                    site.shopify_domain = ''
                    site.shopify_access_token = ''
                    site.shopify_blog_id = ''
                    site.webflow_token = ''
                    site.webflow_site_id = ''
                    site.webflow_collection_id = ''
                    site.save()
                    self.stdout.write(self.style.SUCCESS(
                        f"  Site #{site.id} is now in hosted mode."
                    ))
                else:
                    self.stderr.write(self.style.ERROR(
                        "  This site is NOT in hosted mode (has database_url, WP, Shopify or Webflow config).\n"
                        "  Posts in the hosted-mode HostedPost table would not be served by the public blog endpoint.\n"
                        "  Re-run with --force-hosted to wipe the conflicting fields, OR use a different\n"
                        "  --domain (e.g. --domain=blog.gridar.app) to create a separate Site row."
                    ))
                    return

        # 3. Find posts/ folder
        posts_dir = find_posts_dir()
        if not posts_dir:
            self.stderr.write(self.style.ERROR(
                "posts/ folder not found. Tried "
                f"{Path(settings.BASE_DIR).parent / 'posts'} and /app/posts."
            ))
            return
        self.stdout.write(f"Reading from: {posts_dir}")

        # 4. Upsert each .md
        created = 0
        updated = 0
        skipped = 0
        language = options['language']

        for md_file in sorted(posts_dir.glob('*.md')):
            slug = md_file.stem
            try:
                raw = md_file.read_text(encoding='utf-8')
            except Exception as e:
                self.stderr.write(f"  SKIP {slug}: {e}")
                skipped += 1
                continue

            meta, body = parse_frontmatter(raw)
            title = str(meta.get('title') or slug)
            excerpt = str(meta.get('excerpt') or '')
            author = str(meta.get('author') or site.default_author or 'Gridar')
            date_str = str(meta.get('date') or '')
            tags = meta.get('tags') or []
            if not isinstance(tags, list):
                tags = []

            try:
                published_at = datetime.strptime(date_str, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                published_at = timezone.now().date()

            # Reading time = body word count / 200 wpm (clamp to 1+)
            word_count = max(1, len(body.split()))
            reading_time = max(1, round(word_count / 200))

            post, was_created = HostedPost.objects.update_or_create(
                site=site,
                slug=slug,
                language=language,
                defaults={
                    'title': title[:200],
                    'excerpt': excerpt,
                    'content': body,
                    'author': author[:100],
                    'status': 'published',
                    'published_at': published_at,
                    'reading_time': reading_time,
                },
            )

            # Tags (m2m)
            for tag_name in tags:
                tag_name = str(tag_name).strip()
                if not tag_name:
                    continue
                tag, _ = HostedTag.objects.get_or_create(
                    site=site, name=tag_name,
                )
                post.tags.add(tag)

            if was_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f"  + {slug}"))
            else:
                updated += 1
                self.stdout.write(f"  ~ {slug}")

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(
            f"Done. Site #{site.id} ({domain}): "
            f"{created} created, {updated} updated, {skipped} skipped."
        ))
        self.stdout.write('')
        self.stdout.write(self.style.HTTP_INFO(
            f"Next step: set this Vercel env var so the frontend hits the right site:"
        ))
        self.stdout.write(f"    VITE_GRIDAR_BLOG_SITE_ID={site.id}")
        self.stdout.write('')
        self.stdout.write(
            f"Verify via API: curl https://api.gridar.app/api/public/sites/{site.id}/posts/"
        )
