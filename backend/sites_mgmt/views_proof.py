"""DRF views for the proof loop (baseline + attribution + public share).

Six routes:

  GET  /api/sites/<id>/proof/baseline/        list ArticleBaseline rows
  GET  /api/sites/<id>/proof/attribution/     list ArticleAttribution (filter ?post=)
  GET  /api/sites/<id>/proof/summary/         aggregated site-level delta
  GET  /api/sites/<id>/proof/share/           current share token state
  POST /api/sites/<id>/proof/share/           enable (creates token if needed) or rotate
  DELETE /api/sites/<id>/proof/share/         revoke
  GET  /api/public/proof/<token>/             public read-only summary (no auth)

The authenticated routes reuse `get_site_for_user` from views.py for the
multi-tenant access check. The public route is no-auth + IP-throttled.
"""
from __future__ import annotations

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework.views import APIView
from rest_framework import status

from . import proof_loop
from .models import (
    ArticleAttribution, ArticleBaseline, HostedPost, ProofShareToken, Site,
)
from .views import get_site_for_user


def _serialize_baseline(b: ArticleBaseline) -> dict:
    return {
        'id': b.id,
        'post_id': b.post_id,
        'post_slug': b.post.slug if b.post else None,
        'post_title': b.post.title if b.post else None,
        'captured_at': b.captured_at.isoformat(),
        'period_start': b.period_start.isoformat(),
        'period_end': b.period_end.isoformat(),
        'impressions': b.impressions,
        'clicks': b.clicks,
        'avg_position': b.avg_position,
        'top_queries': b.top_queries,
        'is_pre_gridar': b.is_pre_gridar,
    }


def _serialize_attribution(a: ArticleAttribution) -> dict:
    return {
        'id': a.id,
        'post_id': a.post_id,
        'post_slug': a.post.slug,
        'post_title': a.post.title,
        'days_since_publish': a.days_since_publish,
        'captured_at': a.captured_at.isoformat(),
        'period_start': a.period_start.isoformat(),
        'period_end': a.period_end.isoformat(),
        'indexed': a.indexed,
        'impressions': a.impressions,
        'clicks': a.clicks,
        'avg_position': a.avg_position,
        'top_queries': a.top_queries,
        'delta_vs_baseline': a.delta_vs_baseline,
    }


class ProofBaselineView(APIView):
    """GET /api/sites/<id>/proof/baseline/  - list baselines for the site."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        rows = (ArticleBaseline.objects
                .filter(site=site)
                .select_related('post')
                .order_by('-captured_at')[:200])
        return Response({'baselines': [_serialize_baseline(b) for b in rows]})


class ProofAttributionView(APIView):
    """GET /api/sites/<id>/proof/attribution/?post=<pk>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        qs = (ArticleAttribution.objects
              .filter(post__site=site)
              .select_related('post')
              .order_by('post_id', '-days_since_publish'))
        post_id = request.query_params.get('post')
        if post_id:
            try:
                qs = qs.filter(post_id=int(post_id))
            except ValueError:
                return Response({'error': 'invalid post id'},
                                status=status.HTTP_400_BAD_REQUEST)
        return Response({'attributions': [_serialize_attribution(a) for a in qs[:500]]})


class ProofSummaryView(APIView):
    """GET /api/sites/<id>/proof/summary/  - aggregated site-level delta."""
    permission_classes = [IsAuthenticated]

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        return Response(proof_loop.site_proof_summary(site))


class ProofShareView(APIView):
    """GET/POST/DELETE /api/sites/<id>/proof/share/

    GET    returns the token state (enabled, token if enabled, url).
    POST   enables the share + returns the token (creates if needed).
           Optional body: {"rotate": true} to regenerate the token.
    DELETE disables the share + records revoked_at.
    """
    permission_classes = [IsAuthenticated]

    def _build_public_url(self, request, token_str):
        return request.build_absolute_uri(f'/proof/{token_str}')

    def get(self, request, site_id):
        site = get_site_for_user(request, site_id)
        token = ProofShareToken.objects.filter(site=site).first()
        if not token:
            return Response({'enabled': False, 'token': None, 'public_url': None})
        return Response({
            'enabled': token.enabled,
            'token': token.token if token.enabled else None,
            'public_url': self._build_public_url(request, token.token) if token.enabled else None,
            'created_at': token.created_at.isoformat(),
            'revoked_at': token.revoked_at.isoformat() if token.revoked_at else None,
        })

    def post(self, request, site_id):
        site = get_site_for_user(request, site_id)
        rotate = bool((request.data or {}).get('rotate'))
        token = proof_loop.regenerate_proof_token(site) if rotate \
            else proof_loop.ensure_proof_token(site)
        token.enabled = True
        token.revoked_at = None
        token.save(update_fields=['enabled', 'revoked_at'])
        return Response({
            'enabled': True,
            'token': token.token,
            'public_url': self._build_public_url(request, token.token),
            'rotated': rotate,
        })

    def delete(self, request, site_id):
        site = get_site_for_user(request, site_id)
        token = ProofShareToken.objects.filter(site=site).first()
        if not token or not token.enabled:
            return Response({'enabled': False})
        token.enabled = False
        token.revoked_at = timezone.now()
        token.save(update_fields=['enabled', 'revoked_at'])
        return Response({'enabled': False, 'revoked_at': token.revoked_at.isoformat()})


class _ProofPublicThrottle(AnonRateThrottle):
    rate = '60/hour'


class PublicProofView(APIView):
    """GET /api/public/proof/<token>/  - no auth, IP-throttled.

    Returns the site-level summary if the token is enabled. Hidden 404 on
    revoked / disabled tokens (don't leak existence).
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [_ProofPublicThrottle]

    def get(self, request, token):
        share = get_object_or_404(ProofShareToken, token=token, enabled=True)
        summary = proof_loop.site_proof_summary(share.site)
        summary['domain'] = share.site.domain
        summary['site_name'] = share.site.name
        return Response(summary)
