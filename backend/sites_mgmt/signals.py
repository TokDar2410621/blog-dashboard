"""Auto-index hooks for SiteMemory.

When a HostedPost is created/updated, its content is chunked + embedded into
SiteMemory(kind='article'). When Site.knowledge_base changes, it's chunked +
embedded into SiteMemory(kind='kb').

Failures are swallowed (logged warning) so a missing VOYAGE_API_KEY or a
network blip never blocks a save. The data is still safe in HostedPost /
Site.knowledge_base - it just won't be retrievable via RAG until a manual
rebuild or the next save with embeddings working.
"""
from __future__ import annotations

import logging
import threading

from django.db.models.signals import post_save, post_delete, pre_save
from django.dispatch import receiver

from .models import HostedPost, Site, SiteMemory

logger = logging.getLogger(__name__)


def _safe_index(site, kind, content, source_ref, title=''):
    """Index in a worker thread so the HTTP request returns immediately.
    Voyage embedding is ~200ms-1s per batch which is too slow for save()."""
    from .memory_index import index_source

    def _work():
        try:
            index_source(
                site=site, kind=kind, content=content,
                source_ref=source_ref, title=title,
            )
        except Exception as e:
            logger.warning('Auto-index failed (site=%s, kind=%s, ref=%s): %s',
                           site.id, kind, source_ref, e)

    threading.Thread(target=_work, daemon=True).start()


@receiver(post_save, sender=HostedPost)
def index_hosted_post(sender, instance: HostedPost, created, **kwargs):
    """Index/re-index a HostedPost into SiteMemory(kind='article')."""
    if instance.status != 'published':
        return
    full = f"# {instance.title}\n\n{instance.content or ''}"
    _safe_index(
        site=instance.site, kind='article', content=full,
        source_ref=f'hosted:{instance.slug}', title=instance.title,
    )


@receiver(post_delete, sender=HostedPost)
def unindex_hosted_post(sender, instance: HostedPost, **kwargs):
    SiteMemory.objects.filter(
        site=instance.site, kind='article',
        source_ref=f'hosted:{instance.slug}',
    ).delete()


# Track if knowledge_base actually changed before triggering a re-index.
_kb_cache = {}
# Track GSC connect state to fire a baseline capture exactly once per transition.
_gsc_cache = {}


@receiver(pre_save, sender=Site)
def cache_old_kb(sender, instance: Site, **kwargs):
    if not instance.pk:
        return
    try:
        old = Site.objects.only('knowledge_base', 'gsc_refresh_token').get(pk=instance.pk)
        _kb_cache[instance.pk] = old.knowledge_base
        _gsc_cache[instance.pk] = bool(old.gsc_refresh_token)
    except Site.DoesNotExist:
        _kb_cache[instance.pk] = ''
        _gsc_cache[instance.pk] = False


@receiver(post_save, sender=Site)
def index_site_kb(sender, instance: Site, created, **kwargs):
    old_kb = _kb_cache.pop(instance.pk, None)
    new_kb = instance.knowledge_base or ''
    if created or old_kb != new_kb:
        if not (created and not new_kb.strip()):
            _safe_index(
                site=instance, kind='kb', content=new_kb,
                source_ref='site-kb', title='Knowledge base',
            )


@receiver(post_save, sender=Site)
def capture_baseline_on_gsc_connect(sender, instance: Site, created, **kwargs):
    """Fire baseline capture once when GSC transitions disconnected -> connected.

    Runs in a daemon thread so the save() returns immediately. Failure is
    swallowed; the daily baseline_capture cron will catch up.
    """
    was_connected = _gsc_cache.pop(instance.pk, False)
    is_connected = bool(instance.gsc_refresh_token and instance.gsc_property_url)
    just_connected = (created and is_connected) or (not was_connected and is_connected)
    if not just_connected:
        return

    def _work():
        try:
            from . import proof_loop
            proof_loop.capture_baseline(instance)
        except Exception as e:
            logger.warning('Baseline auto-capture failed (site=%s): %s', instance.id, e)

    threading.Thread(target=_work, daemon=True).start()
