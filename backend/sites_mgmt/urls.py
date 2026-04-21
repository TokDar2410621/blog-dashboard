from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    SiteViewSet, UserProfileView,
    SitePostsView, SitePostDetailView,
    SiteStatsView, SiteCategoriesView, SiteTagsView, SiteCannibalizationView,
    PexelsSearchView, SerperImageSearchView, GenerateImageView,
    GenerateArticleView, GenerateInlineView, GenerateTagsView,
    UploadImageView, ServeImageView, SEOAuditView, SEOFixView, SEOSuggestView,
    SEOSynonymsView, SEOCacheClearView, TranslatePostView, CompetitorAnalysisView,
    KeywordResearchView,
    PageSpeedView, LinkSuggestionsView, BacklinksView, SEOSchemaView,
    PublicSiteView, PublicPostsView, PublicPostDetailView,
    PublicTranslationsView, PublicCategoriesView,
)

router = DefaultRouter()
router.register(r'sites', SiteViewSet, basename='site')

urlpatterns = [
    path('auth/me/', UserProfileView.as_view(), name='user-profile'),
    path('sites/<int:site_id>/posts/', SitePostsView.as_view(), name='site-posts'),
    path('sites/<int:site_id>/posts/<slug:slug>/', SitePostDetailView.as_view(), name='site-post-detail'),
    path('sites/<int:site_id>/stats/', SiteStatsView.as_view(), name='site-stats'),
    path('sites/<int:site_id>/categories/', SiteCategoriesView.as_view(), name='site-categories'),
    path('sites/<int:site_id>/tags/', SiteTagsView.as_view(), name='site-tags'),
    path('sites/<int:site_id>/cannibalization/', SiteCannibalizationView.as_view(), name='site-cannibalization'),
    path('sites/<int:site_id>/generate/', GenerateArticleView.as_view(), name='site-generate-article'),
    path('sites/<int:site_id>/generate-inline/', GenerateInlineView.as_view(), name='site-generate-inline'),
    path('sites/<int:site_id>/link-suggestions/', LinkSuggestionsView.as_view(), name='site-link-suggestions'),
    path('pexels/search/', PexelsSearchView.as_view(), name='pexels-search'),
    path('serper/images/', SerperImageSearchView.as_view(), name='serper-images'),
    path('generate-image/', GenerateImageView.as_view(), name='generate-image'),
    path('upload-image/', UploadImageView.as_view(), name='upload-image'),
    path('images/<uuid:uid>/', ServeImageView.as_view(), name='serve-image'),
    path('generate-tags/', GenerateTagsView.as_view(), name='generate-tags'),
    path('translate/', TranslatePostView.as_view(), name='translate-post'),
    path('seo-audit/', SEOAuditView.as_view(), name='seo-audit'),
    path('seo-fix/', SEOFixView.as_view(), name='seo-fix'),
    path('seo-suggest/', SEOSuggestView.as_view(), name='seo-suggest'),
    path('seo-synonyms/', SEOSynonymsView.as_view(), name='seo-synonyms'),
    path('seo-cache/clear/', SEOCacheClearView.as_view(), name='seo-cache-clear'),
    path('competitors/', CompetitorAnalysisView.as_view(), name='competitors'),
    path('keyword-research/', KeywordResearchView.as_view(), name='keyword-research'),
    path('page-speed/', PageSpeedView.as_view(), name='page-speed'),
    path('backlinks/', BacklinksView.as_view(), name='backlinks'),
    path('seo-schema/', SEOSchemaView.as_view(), name='seo-schema'),
    # Public API — for site frontends
    path('public/sites/<int:site_id>/', PublicSiteView.as_view(), name='public-site'),
    path('public/sites/<int:site_id>/posts/', PublicPostsView.as_view(), name='public-posts'),
    path('public/sites/<int:site_id>/posts/<slug:slug>/', PublicPostDetailView.as_view(), name='public-post-detail'),
    path('public/sites/<int:site_id>/posts/<slug:slug>/translations/', PublicTranslationsView.as_view(), name='public-translations'),
    path('public/sites/<int:site_id>/categories/', PublicCategoriesView.as_view(), name='public-categories'),
    path('', include(router.urls)),
]
