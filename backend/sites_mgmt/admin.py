"""
Django admin for Gridar. Surfaces every user-facing entity so the operator
can debug, support, and intervene without writing SQL.
"""
from datetime import timedelta

from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count, Sum
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from .models import (
    ApiToken,
    CreditBalance,
    CreditTransaction,
    HostedCategory,
    HostedPost,
    HostedTag,
    MonthlyArticleQuota,
    Redirect,
    SerpRank,
    Site,
    Subscription,
    TrackedKeyword,
    UploadedImage,
)


# ---------------------------------------------------------------------------
# User admin: inject Subscription + CreditBalance inlines so the operator can
# see a user's complete state on a single page.
# ---------------------------------------------------------------------------

class SubscriptionInline(admin.StackedInline):
    model = Subscription
    can_delete = False
    extra = 0
    fk_name = 'user'
    fields = (
        'plan',
        'status',
        'is_paid_display',
        'current_period_end',
        'cancel_at_period_end',
        'stripe_customer_id',
        'stripe_subscription_id',
    )
    readonly_fields = ('is_paid_display', 'stripe_customer_id', 'stripe_subscription_id')

    @admin.display(description='Payé')
    def is_paid_display(self, obj):
        return '✅ Oui' if obj.is_paid else '❌ Non'


class CreditBalanceInline(admin.StackedInline):
    model = CreditBalance
    can_delete = False
    extra = 0
    fields = ('balance', 'updated_at')
    readonly_fields = ('updated_at',)


User = get_user_model()
admin.site.unregister(User)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = (
        'username',
        'email',
        'plan_display',
        'credit_balance_display',
        'sites_count',
        'is_active',
        'date_joined',
        'last_login',
    )
    list_filter = (
        'is_active',
        'is_staff',
        'is_superuser',
        'date_joined',
        'subscription__plan',
    )
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-date_joined',)
    inlines = [SubscriptionInline, CreditBalanceInline]

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('subscription', 'credit_balance').annotate(
            _sites=Count('sites', distinct=True),
        )

    @admin.display(description='Plan', ordering='subscription__plan')
    def plan_display(self, obj):
        sub = getattr(obj, 'subscription', None)
        if not sub:
            return '-'
        colors = {'free': '#71717a', 'solo': '#3b82f6', 'pro': '#10b981', 'agency': '#a855f7'}
        color = colors.get(sub.plan, '#71717a')
        return format_html('<span style="color:{};font-weight:600">{}</span>', color, sub.plan)

    @admin.display(description='Crédits')
    def credit_balance_display(self, obj):
        bal = getattr(obj, 'credit_balance', None)
        return bal.balance if bal else 0

    @admin.display(description='Sites', ordering='_sites')
    def sites_count(self, obj):
        return obj._sites

    # -----------------------------------------------------------------------
    # Bulk actions: grant a plan or add credits to selected users in one
    # click. Useful for support (give Pro to a customer who reported a bug),
    # marketing (free month to early signups), and dogfooding (make ourselves
    # Pro on the prod DB without touching Stripe).
    # -----------------------------------------------------------------------
    actions = [
        'grant_solo_30d', 'grant_pro_30d', 'grant_agency_30d',
        'grant_pro_1y', 'grant_agency_1y',
        'reset_to_free',
        'add_10_credits', 'add_50_credits', 'add_200_credits',
    ]

    def _grant_plan(self, request, queryset, plan, days):
        from .models import Subscription
        end = timezone.now() + timedelta(days=days)
        count = 0
        for user in queryset:
            sub, _ = Subscription.objects.get_or_create(user=user)
            sub.plan = plan
            sub.status = 'active'
            sub.current_period_end = end
            sub.cancel_at_period_end = False
            sub.save()
            count += 1
        self.message_user(
            request,
            f"{count} user(s) passes en {plan} jusqu'au {end.strftime('%Y-%m-%d')}.",
            messages.SUCCESS,
        )

    @admin.action(description="Donner Solo (30 jours)")
    def grant_solo_30d(self, request, queryset):
        self._grant_plan(request, queryset, 'solo', 30)

    @admin.action(description="Donner Pro (30 jours)")
    def grant_pro_30d(self, request, queryset):
        self._grant_plan(request, queryset, 'pro', 30)

    @admin.action(description="Donner Agence (30 jours)")
    def grant_agency_30d(self, request, queryset):
        self._grant_plan(request, queryset, 'agency', 30)

    @admin.action(description="Donner Pro (1 an)")
    def grant_pro_1y(self, request, queryset):
        self._grant_plan(request, queryset, 'pro', 365)

    @admin.action(description="Donner Agence (1 an)")
    def grant_agency_1y(self, request, queryset):
        self._grant_plan(request, queryset, 'agency', 365)

    @admin.action(description="Repasser en Free (annule la sub)")
    def reset_to_free(self, request, queryset):
        from .models import Subscription
        count = 0
        for user in queryset:
            sub, _ = Subscription.objects.get_or_create(user=user)
            sub.plan = 'free'
            sub.status = 'canceled'
            sub.cancel_at_period_end = False
            sub.current_period_end = None
            sub.save()
            count += 1
        self.message_user(
            request, f"{count} user(s) repasses en Free.", messages.SUCCESS,
        )

    def _add_credits(self, request, queryset, amount):
        from .quota import add_credits
        for user in queryset:
            add_credits(
                user, amount, kind='gift',
                description=f"Cadeau admin (+{amount}) par {request.user.username}",
            )
        self.message_user(
            request,
            f"{queryset.count()} user(s) ont recu +{amount} credits.",
            messages.SUCCESS,
        )

    @admin.action(description="Ajouter 10 credits")
    def add_10_credits(self, request, queryset):
        self._add_credits(request, queryset, 10)

    @admin.action(description="Ajouter 50 credits")
    def add_50_credits(self, request, queryset):
        self._add_credits(request, queryset, 50)

    @admin.action(description="Ajouter 200 credits")
    def add_200_credits(self, request, queryset):
        self._add_credits(request, queryset, 200)


# ---------------------------------------------------------------------------
# Subscription, billing, credits
# ---------------------------------------------------------------------------

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'plan',
        'status',
        'is_paid_display',
        'current_period_end',
        'cancel_at_period_end',
        'stripe_customer_id',
        'updated_at',
    )
    list_filter = ('plan', 'status', 'cancel_at_period_end')
    search_fields = ('user__username', 'user__email', 'stripe_customer_id', 'stripe_subscription_id')
    raw_id_fields = ('user',)
    date_hierarchy = 'updated_at'
    readonly_fields = ('created_at', 'updated_at')
    actions = [
        'upgrade_to_solo_30d', 'upgrade_to_pro_30d', 'upgrade_to_agency_30d',
        'extend_30d', 'extend_365d', 'cancel_subscription',
    ]

    @admin.display(description='Payé', boolean=True)
    def is_paid_display(self, obj):
        return obj.is_paid

    def _bulk_update(self, request, queryset, **kwargs):
        end = kwargs.pop('current_period_end', None)
        count = queryset.count()
        for sub in queryset:
            for field, value in kwargs.items():
                setattr(sub, field, value)
            if end is not None:
                sub.current_period_end = end
            sub.save()
        return count

    @admin.action(description="Upgrade -> Solo (30 jours)")
    def upgrade_to_solo_30d(self, request, queryset):
        end = timezone.now() + timedelta(days=30)
        n = self._bulk_update(
            request, queryset,
            plan='solo', status='active', cancel_at_period_end=False, current_period_end=end,
        )
        self.message_user(request, f"{n} sub(s) -> Solo jusqu'au {end:%Y-%m-%d}.", messages.SUCCESS)

    @admin.action(description="Upgrade -> Pro (30 jours)")
    def upgrade_to_pro_30d(self, request, queryset):
        end = timezone.now() + timedelta(days=30)
        n = self._bulk_update(
            request, queryset,
            plan='pro', status='active', cancel_at_period_end=False, current_period_end=end,
        )
        self.message_user(request, f"{n} sub(s) -> Pro jusqu'au {end:%Y-%m-%d}.", messages.SUCCESS)

    @admin.action(description="Upgrade -> Agence (30 jours)")
    def upgrade_to_agency_30d(self, request, queryset):
        end = timezone.now() + timedelta(days=30)
        n = self._bulk_update(
            request, queryset,
            plan='agency', status='active', cancel_at_period_end=False, current_period_end=end,
        )
        self.message_user(request, f"{n} sub(s) -> Agence jusqu'au {end:%Y-%m-%d}.", messages.SUCCESS)

    @admin.action(description="Prolonger de 30 jours (plan inchange)")
    def extend_30d(self, request, queryset):
        count = 0
        for sub in queryset:
            base = sub.current_period_end or timezone.now()
            sub.current_period_end = base + timedelta(days=30)
            sub.status = 'active'
            sub.save()
            count += 1
        self.message_user(request, f"{count} sub(s) prolongees de 30 jours.", messages.SUCCESS)

    @admin.action(description="Prolonger de 365 jours (plan inchange)")
    def extend_365d(self, request, queryset):
        count = 0
        for sub in queryset:
            base = sub.current_period_end or timezone.now()
            sub.current_period_end = base + timedelta(days=365)
            sub.status = 'active'
            sub.save()
            count += 1
        self.message_user(request, f"{count} sub(s) prolongees de 365 jours.", messages.SUCCESS)

    @admin.action(description="Annuler (passer en Free)")
    def cancel_subscription(self, request, queryset):
        n = self._bulk_update(
            request, queryset,
            plan='free', status='canceled', cancel_at_period_end=False, current_period_end=None,
        )
        self.message_user(request, f"{n} sub(s) annulees.", messages.SUCCESS)


@admin.register(CreditBalance)
class CreditBalanceAdmin(admin.ModelAdmin):
    list_display = ('user', 'balance', 'updated_at')
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)
    readonly_fields = ('updated_at',)


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount', 'kind', 'description', 'stripe_session_id', 'created_at')
    list_filter = ('kind',)
    search_fields = ('user__username', 'user__email', 'description', 'stripe_session_id')
    raw_id_fields = ('user',)
    date_hierarchy = 'created_at'
    readonly_fields = ('created_at',)


@admin.register(MonthlyArticleQuota)
class MonthlyArticleQuotaAdmin(admin.ModelAdmin):
    list_display = ('user', 'month_key', 'count', 'updated_at')
    list_filter = ('month_key',)
    search_fields = ('user__username', 'user__email')
    raw_id_fields = ('user',)
    readonly_fields = ('created_at', 'updated_at')


# ---------------------------------------------------------------------------
# Sites + content
# ---------------------------------------------------------------------------

@admin.register(Site)
class SiteAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'domain',
        'mode_display',
        'owner',
        'default_language',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'default_language', 'created_at')
    search_fields = ('name', 'domain', 'wp_url', 'shopify_domain', 'owner__username', 'owner__email')
    raw_id_fields = ('owner',)
    date_hierarchy = 'created_at'
    readonly_fields = ('api_key', 'created_at', 'updated_at')
    fieldsets = (
        ('Général', {'fields': ('name', 'domain', 'description', 'owner', 'is_active')}),
        ('Branding', {'fields': ('og_image_url', 'theme_config'), 'classes': ('collapse',)}),
        ('Langue', {'fields': ('default_language', 'available_languages')}),
        ('EEAT auteur', {
            'fields': (
                'default_author', 'author_role', 'author_bio', 'author_credentials',
                'author_image_url', 'author_linkedin', 'author_twitter', 'author_website',
            ),
            'classes': ('collapse',),
        }),
        ('Knowledge base', {'fields': ('knowledge_base',), 'classes': ('collapse',)}),
        ('WordPress', {
            'fields': ('wp_url', 'wp_username', 'wp_app_password'),
            'classes': ('collapse',),
        }),
        ('Shopify', {
            'fields': ('shopify_domain', 'shopify_access_token', 'shopify_blog_id'),
            'classes': ('collapse',),
        }),
        ('Webflow', {
            'fields': ('webflow_token', 'webflow_site_id', 'webflow_collection_id', 'webflow_field_map'),
            'classes': ('collapse',),
        }),
        ('Hébergé', {
            'fields': ('public_blog_domain', 'vercel_deploy_hook'),
            'classes': ('collapse',),
        }),
        ('Externe (DB)', {
            'fields': ('database_url', 'blog_config'),
            'classes': ('collapse',),
        }),
        ('GSC', {
            'fields': ('gsc_property_url', 'gsc_refresh_token'),
            'classes': ('collapse',),
        }),
        ('Sécurité', {'fields': ('api_key',), 'classes': ('collapse',)}),
        ('Timestamps', {'fields': ('created_at', 'updated_at')}),
    )

    @admin.display(description='Mode')
    def mode_display(self, obj):
        if obj.wp_url:
            return '🔵 WordPress'
        if obj.shopify_domain:
            return '🟢 Shopify'
        if obj.webflow_token:
            return '🟣 Webflow'
        if obj.database_url:
            return '🟠 Externe'
        return '⚪ Hébergé'


@admin.register(HostedPost)
class HostedPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'site', 'language', 'status', 'featured', 'published_at', 'view_count')
    list_filter = ('status', 'language', 'featured', 'published_at')
    search_fields = ('title', 'slug', 'excerpt', 'content')
    raw_id_fields = ('site', 'category')
    filter_horizontal = ('tags',)
    date_hierarchy = 'published_at'
    readonly_fields = ('created_at', 'updated_at', 'translation_group')
    prepopulated_fields = {'slug': ('title',)}


@admin.register(HostedCategory)
class HostedCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug', 'site')
    search_fields = ('name', 'slug')
    raw_id_fields = ('site',)
    prepopulated_fields = {'slug': ('name',)}


@admin.register(HostedTag)
class HostedTagAdmin(admin.ModelAdmin):
    list_display = ('name', 'site')
    search_fields = ('name',)
    raw_id_fields = ('site',)


# ---------------------------------------------------------------------------
# Auth / integrations
# ---------------------------------------------------------------------------

@admin.register(ApiToken)
class ApiTokenAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'key_prefix', 'last_used_at', 'revoked_status', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('name', 'user__username', 'user__email', 'key_prefix')
    raw_id_fields = ('user',)
    date_hierarchy = 'created_at'
    readonly_fields = ('key_hash', 'key_prefix', 'created_at', 'last_used_at')

    @admin.display(description='Statut')
    def revoked_status(self, obj):
        if obj.revoked_at:
            return format_html('<span style="color:#ef4444">❌ Révoqué {}</span>', obj.revoked_at.strftime('%Y-%m-%d'))
        return format_html('<span style="color:#10b981">✅ Actif</span>')


# ---------------------------------------------------------------------------
# SEO data
# ---------------------------------------------------------------------------

class SerpRankInline(admin.TabularInline):
    model = SerpRank
    extra = 0
    fields = ('position', 'url', 'is_target_match', 'source', 'recorded_at')
    readonly_fields = ('recorded_at',)
    can_delete = False
    show_change_link = False


@admin.register(TrackedKeyword)
class TrackedKeywordAdmin(admin.ModelAdmin):
    list_display = ('keyword', 'site', 'language', 'target_url', 'latest_position_display', 'is_active')
    list_filter = ('language', 'is_active', 'created_at')
    search_fields = ('keyword', 'target_url', 'site__name')
    raw_id_fields = ('site',)
    date_hierarchy = 'created_at'
    inlines = [SerpRankInline]

    @admin.display(description='Dernière position')
    def latest_position_display(self, obj):
        latest = obj.ranks.order_by('-recorded_at').first() if hasattr(obj, 'ranks') else None
        if not latest or latest.position == 0:
            return '-'
        if latest.position <= 3:
            color = '#10b981'
        elif latest.position <= 10:
            color = '#3b82f6'
        elif latest.position <= 30:
            color = '#f59e0b'
        else:
            color = '#ef4444'
        return format_html('<span style="color:{};font-weight:600">#{}</span>', color, latest.position)


@admin.register(SerpRank)
class SerpRankAdmin(admin.ModelAdmin):
    list_display = ('tracked', 'position', 'is_target_match', 'source', 'recorded_at')
    list_filter = ('source', 'is_target_match', 'recorded_at')
    search_fields = ('tracked__keyword', 'url')
    raw_id_fields = ('tracked',)
    date_hierarchy = 'recorded_at'


# ---------------------------------------------------------------------------
# Misc
# ---------------------------------------------------------------------------

@admin.register(Redirect)
class RedirectAdmin(admin.ModelAdmin):
    list_display = ('site', 'from_slug', 'to_slug', 'language', 'hit_count', 'is_active', 'created_at')
    list_filter = ('is_active', 'language')
    search_fields = ('from_slug', 'to_slug', 'site__name')
    raw_id_fields = ('site',)
    date_hierarchy = 'created_at'


@admin.register(UploadedImage)
class UploadedImageAdmin(admin.ModelAdmin):
    list_display = ('filename', 'mime_type', 'owner', 'created_at')
    list_filter = ('mime_type', 'created_at')
    search_fields = ('filename', 'owner__username')
    raw_id_fields = ('owner',)
    readonly_fields = ('uid', 'created_at')
    exclude = ('data',)  # Don't show the binary blob in the admin form.


# ---------------------------------------------------------------------------
# Admin site branding
# ---------------------------------------------------------------------------
admin.site.site_header = 'Gridar - Administration'
admin.site.site_title = 'Gridar admin'
admin.site.index_title = 'Tableau de bord'
