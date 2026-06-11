import re
import uuid

from django.db import models
from django.contrib.auth.models import User
from pgvector.django import VectorField

class UploadedImage(models.Model):
    """Images stockees en base de donnees (pas de filesystem persistant sur Railway)."""
    uid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    data = models.BinaryField(verbose_name="Donnees image")
    mime_type = models.CharField(max_length=50)
    filename = models.CharField(max_length=255, blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_images')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.filename} ({self.uid})"


class Site(models.Model):
    LANGUAGE_CHOICES = [('fr', 'Français'), ('en', 'English'), ('es', 'Español')]
    BUSINESS_MODEL_CHOICES = [
        ('agency', 'Agence'),
        ('saas', 'SaaS'),
        ('ecommerce', 'E-commerce'),
        ('marketplace', 'Marketplace'),
        ('media', 'Média / Édition'),
        ('personal_blog', 'Blog personnel'),
    ]

    # ── Identité ──────────────────────────────────────────────────────
    name = models.CharField(max_length=200, verbose_name="Nom du site")
    domain = models.CharField(
        max_length=255, blank=True, db_index=True,
        verbose_name="Domaine du site",
        help_text="Sans https:// ni slash final (ex: tokamdarius.ca)"
    )
    description = models.TextField(
        blank=True, default='',
        verbose_name="Description",
        help_text="Courte description (utilisée pour Open Graph / about-page)"
    )
    og_image_url = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="Image OG par défaut",
        help_text="URL de l'image utilisée comme fallback Open Graph quand un article n'a pas de cover"
    )

    # ── Config IA ─────────────────────────────────────────────────────
    knowledge_base = models.TextField(
        blank=True, default='',
        verbose_name="Base de connaissances",
        help_text="Contexte personnel pour la génération d'articles (qui tu es, tes projets, ton ton, etc.)"
    )
    competitors = models.TextField(
        blank=True, default='',
        verbose_name="Marques à NE PAS citer",
        help_text="Une marque par ligne. Le générateur évitera de les mentionner et n'y mettra jamais de lien sortant."
    )
    # ── Business model (onboarding obligatoire) ───────────────────────
    business_model = models.CharField(
        max_length=20, choices=BUSINESS_MODEL_CHOICES, default='personal_blog',
        verbose_name="Modèle d'affaires",
        help_text="Détermine l'angle éditorial : SaaS pousse comparatifs/use-cases, "
                  "e-commerce pousse fiches produits/buying guides, agence pousse "
                  "case studies, etc. Champ obligatoire avant toute génération."
    )
    default_author = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Auteur par défaut",
        help_text="Nom d'auteur attribué aux articles générés (utilisé aussi pour Schema.org). Vide = 'Admin'."
    )
    # ── EEAT - author profile (Schema.org Person) ─────────────────────
    author_role = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Rôle / titre de l'auteur",
        help_text="Ex: Fondateur, Consultant SEO, Avocat fiscaliste"
    )
    author_bio = models.TextField(
        blank=True, default='',
        verbose_name="Bio de l'auteur",
        help_text="2-4 phrases qui établissent l'expertise (E-E-A-T : experience, expertise, authority, trust)"
    )
    author_credentials = models.TextField(
        blank=True, default='',
        verbose_name="Crédentials / qualifications",
        help_text="Diplômes, certifications, expérience pertinente. Visible publiquement et utilisé en JSON-LD."
    )
    author_image_url = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="Photo de l'auteur",
        help_text="URL d'une photo professionnelle (JSON-LD Person.image)"
    )
    author_linkedin = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="LinkedIn",
    )
    author_twitter = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="Twitter / X",
    )
    author_website = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="Site personnel",
    )

    # ── CTA primaire (injecte en conclusion de chaque article genere) ────
    primary_cta_text = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Texte du CTA principal",
        help_text=(
            "Phrase d'appel a l'action injectee en conclusion de chaque article "
            "genere (ex: 'Reserve ta consultation gratuite'). Le generateur "
            "construit un bouton/lien naturel a partir de ce texte + l'URL ci-dessous."
        )
    )
    primary_cta_url = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="URL du CTA principal",
        help_text=(
            "Destination du CTA (ex: page de contact, page d'inscription, formulaire "
            "de devis). Inclus uniquement si le texte du CTA est aussi renseigne."
        )
    )

    default_language = models.CharField(
        max_length=2, choices=LANGUAGE_CHOICES, default='fr',
        verbose_name="Langue par défaut",
        help_text="Langue présélectionnée dans l'éditeur et la génération IA"
    )
    available_languages = models.JSONField(
        blank=True, default=list,
        verbose_name="Langues disponibles",
        help_text="Liste de codes ISO acceptés (ex: ['fr','en']). Vide = toutes (fr/en/es)."
    )

    # ── Stockage des articles ─────────────────────────────────────────
    database_url = models.TextField(
        blank=True, default='',
        verbose_name="DATABASE_URL PostgreSQL",
        help_text="Laisser vide pour utiliser le stockage hébergé du dashboard"
    )
    blog_config = models.JSONField(
        blank=True, null=True, default=None,
        verbose_name="Config tables blog",
        help_text="Mapping des tables/colonnes si le site n'utilise pas les tables blog_* standard"
    )
    # ── Public blog (mode hosted: notre frontend Next.js) ─────────────
    public_blog_domain = models.CharField(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name="Domaine du blog public",
        help_text="Hostname où le blog est servi (ex: blog.restaurant.ca, restofoo.blog-quebec.ca). Différent de `domain` qui désigne la marque."
    )
    theme_config = models.JSONField(
        blank=True, null=True, default=None,
        verbose_name="Configuration du thème",
        help_text="Couleurs, polices, logo pour le frontend public. Format: {brand_color, brand_fg, font_sans, font_display, logo_url}"
    )
    # ── WordPress integration (mode "WP") ─────────────────────────────
    wp_url = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="WordPress - URL du site",
        help_text="Ex: https://monsite.ca (sans /wp-admin). Si renseigné, le site est en mode WordPress."
    )
    wp_username = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="WordPress - username",
        help_text="Le nom d'utilisateur WordPress qui possède l'Application Password."
    )
    wp_app_password = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="WordPress - Application Password",
        help_text="Application Password généré dans WP → Profil → Application Passwords."
    )

    # ── Shopify integration (mode "Shopify") ──────────────────────────
    shopify_domain = models.CharField(
        max_length=255, blank=True, default='', db_index=True,
        verbose_name="Shopify - myshopify.com",
        help_text="Ex: monstore.myshopify.com (le domaine technique, pas le custom domain). Si renseigné, le site est en mode Shopify."
    )
    shopify_access_token = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Shopify - Admin API access token",
        help_text="Token de la custom app Shopify (Admin → Apps → Develop apps → Create app → Admin API access token). Scope requis: write_content."
    )
    shopify_blog_id = models.CharField(
        max_length=50, blank=True, default='',
        verbose_name="Shopify - Blog ID",
        help_text="ID du blog Shopify où publier (un store peut avoir plusieurs blogs). Auto-détecté à la connexion."
    )

    # ── Webflow integration (mode "Webflow") ──────────────────────────
    webflow_token = models.CharField(
        max_length=300, blank=True, default='',
        verbose_name="Webflow - API token",
        help_text="Site Token (Project Settings → Apps & Integrations → API access). Si renseigné avec un site_id et collection_id, le site est en mode Webflow."
    )
    webflow_site_id = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name="Webflow - Site ID",
        help_text="Identifiant du Webflow site (auto-rempli à la connexion)."
    )
    webflow_collection_id = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name="Webflow - Collection ID",
        help_text="ID de la collection CMS où publier les articles (auto-rempli à la connexion)."
    )
    webflow_field_map = models.JSONField(
        blank=True, null=True, default=None,
        verbose_name="Webflow - Mapping de champs",
        help_text="Mapping de nos champs vers les slugs Webflow. Format: {title, slug, body, summary, image, status}. Auto-détecté à la connexion."
    )

    # ── Intégrations externes ─────────────────────────────────────────
    vercel_deploy_hook = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="Vercel Deploy Hook",
        help_text="URL du Deploy Hook pour redéployer Vercel après chaque modification d'article"
    )
    gsc_property_url = models.URLField(
        max_length=300, blank=True, default='',
        verbose_name="Search Console - URL propriété",
        help_text="URL de la propriété Search Console (ex: https://tokamdarius.ca/)"
    )
    gsc_refresh_token = models.TextField(
        blank=True, default='',
        verbose_name="Search Console - refresh token",
        help_text="OAuth2 refresh token (sensible - ne pas exposer côté frontend)"
    )
    gsc_oauth_verifier_pending = models.CharField(
        max_length=128, blank=True, default='',
        verbose_name="GSC OAuth - PKCE verifier en cours",
        help_text=(
            "Verifier PKCE genere lors du build de l'auth URL, replay au callback "
            "pour le fetch_token. Survit a un OAuth roundtrip via DB plutot que "
            "cache memoire (les workers gunicorn ne partagent pas LocMemCache). "
            "Efface apres succes ou echec - jamais sensitif tout seul."
        )
    )

    # ── API publique ──────────────────────────────────────────────────
    api_key = models.CharField(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name="Clé API publique",
        help_text="Utilisée comme header X-Api-Key pour les endpoints publics. Auto-générée."
    )

    # ── Mode autopilote ───────────────────────────────────────────────
    # Quand activé, le management command `run_autopilot` (cron horaire) génère
    # autopilot_weekly_count articles par semaine en piochant les sujets parmi
    # les TrackedKeyword du site qui n'ont pas encore d'article. Les articles
    # générés restent en statut 'draft' - le user décide quand publier.
    autopilot_enabled = models.BooleanField(
        default=False, db_index=True,
        verbose_name="Mode autopilote",
        help_text="Si actif, Gridar génère automatiquement des articles selon la cadence configurée"
    )
    autopilot_weekly_count = models.PositiveSmallIntegerField(
        default=2,
        verbose_name="Articles par semaine",
        help_text="Nombre d'articles que l'autopilote doit générer chaque semaine (1-7)"
    )
    autopilot_last_run_at = models.DateTimeField(
        null=True, blank=True,
        verbose_name="Dernier run autopilote",
        help_text="Datetime du dernier article généré par l'autopilote (succès)"
    )
    autopilot_last_error = models.TextField(
        blank=True, default='',
        verbose_name="Dernière erreur autopilote",
        help_text="Stack trace ou message si le dernier run a échoué (vidé au prochain succès)"
    )
    autopilot_auto_publish = models.BooleanField(
        default=False,
        verbose_name="Publication automatique",
        help_text="Si actif, les articles générés par l'autopilote sont publiés directement (sans passer par draft). Désactivé par défaut pour garder une étape de review."
    )
    AUTOPILOT_MODE_CHOICES = [
        ('refresh_first', 'Refresh first - prioriser le rafraichissement des articles en perte de trafic'),
        ('create_only', 'Create only - generer uniquement de nouveaux articles'),
        ('balanced', 'Balanced - alterner refresh et creation (1 refresh / 2 creations)'),
    ]
    autopilot_mode = models.CharField(
        max_length=20, choices=AUTOPILOT_MODE_CHOICES, default='balanced',
        verbose_name="Strategie autopilote",
        help_text=(
            "create_only: comportement legacy, ne genere que de nouveaux articles. "
            "refresh_first: prioritise systematiquement le refresh des articles en "
            "decay (impressions GSC -20% ou plus). balanced (defaut): alterne 1 "
            "refresh pour 2 creations."
        ),
    )
    min_refresh_interval_days = models.PositiveIntegerField(
        default=30,
        verbose_name="Intervalle minimum entre 2 refresh d'un meme article (jours)",
        help_text=(
            "Empeche l'autopilote de rafraichir 2x de suite le meme article. "
            "Un article ne peut etre refreshe que si son updated_at est plus "
            "ancien que ce nombre de jours."
        ),
    )

    # ── Méta ──────────────────────────────────────────────────────────
    is_active = models.BooleanField(
        default=True, db_index=True,
        verbose_name="Actif",
        help_text="Décoche pour suspendre le site (lectures bloquées, génération désactivée)"
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sites')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['owner', 'name'],
                name='uniq_site_owner_name',
            ),
        ]
        indexes = [
            models.Index(fields=['owner', 'is_active']),
        ]

    @property
    def is_wordpress(self):
        """Site connected via WordPress REST API + Application Password."""
        return bool(self.wp_url and self.wp_app_password)

    @property
    def is_shopify(self):
        """Site connected via Shopify Admin API (custom app token)."""
        return bool(self.shopify_domain and self.shopify_access_token)

    @property
    def is_webflow(self):
        """Site connected via Webflow CMS API (site token + collection)."""
        return bool(self.webflow_token and self.webflow_site_id and self.webflow_collection_id)

    @property
    def is_hosted(self):
        """Site without external storage (no DB URL, no CMS) uses the dashboard's hosted storage."""
        return (
            not self.database_url
            and not self.is_wordpress
            and not self.is_shopify
            and not self.is_webflow
        )

    @property
    def author_for_articles(self):
        """Default author name to attribute on generated articles."""
        return self.default_author or 'Admin'

    @property
    def effective_languages(self):
        """List of language codes accepted by this site (always non-empty)."""
        return list(self.available_languages) if self.available_languages else ['fr', 'en', 'es']

    def supports_language(self, code):
        """True if `code` is allowed for this site."""
        return code in self.effective_languages

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = uuid.uuid4().hex
        # Normalize domain: strip scheme + trailing slash
        if self.domain:
            self.domain = self.domain.replace('https://', '').replace('http://', '').rstrip('/')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.domain or 'no domain'})"


class Lead(models.Model):
    """Captured email + context from the public /audit lead-magnet page.

    Created when a visitor enters their email to unlock the full audit report.
    No user account required - this is a marketing-funnel artifact, not a
    full account. Sales / onboarding pipeline drives the conversion from here.
    """
    email = models.EmailField(db_index=True)
    domain_audited = models.CharField(max_length=255, blank=True, default='')
    source = models.CharField(
        max_length=50, default='public_audit', db_index=True,
        help_text="Funnel source: 'public_audit', 'wp_plugin', 'newsletter', etc.",
    )
    ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True, default='')
    locale = models.CharField(max_length=10, blank=True, default='', help_text="fr-CA, en-US, etc.")
    consented_marketing = models.BooleanField(
        default=False,
        help_text="Loi 25 / RGPD: explicit opt-in to receive marketing. "
                  "Without this, can only send transactional emails (e.g. the "
                  "audit report itself).",
    )
    score_at_capture = models.IntegerField(
        null=True, blank=True,
        help_text="Composite SEO score at the moment of capture, for cohort analysis.",
    )
    unsubscribed_at = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Loi 25 / RGPD: timestamp of the opt-out. Set on EVERY Lead "
                  "row sharing the same email (the audit page creates one row "
                  "per audit, not per address). Blocks all marketing steps; "
                  "the transactional j0 report still goes out when the person "
                  "explicitly requests a new audit.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    converted_to_user = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='lead_origins',
        help_text="Populated when this lead later signs up for a real account.",
    )

    class Meta:
        verbose_name = "Lead (audit gratuit)"
        verbose_name_plural = "Leads (audit gratuit)"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', '-created_at']),
            models.Index(fields=['source', '-created_at']),
        ]

    def __str__(self):
        return f"{self.email} ({self.domain_audited or 'no domain'})"


class LeadEmailSent(models.Model):
    """Tracking row for each transactional/marketing email we send to a Lead.

    Two purposes:
      1. **Idempotency** - the daily cron command checks for the (lead, step)
         pair before sending so a re-run never double-mails the same step.
      2. **Audit / debug** - if a lead complains they didn't receive the J+3
         email, we can confirm whether Resend's API accepted it and which
         provider message_id it got.

    `step` is a short opaque code we control (e.g. 'j0_audit_report',
    'j1_competitors', 'j3_articles', 'j7_case_study', 'j14_offer'). Steps are
    declared in the management command, not constrained at the DB level, so
    we can iterate the funnel without migrations.
    """
    lead = models.ForeignKey(
        'Lead', on_delete=models.CASCADE, related_name='emails_sent',
    )
    step = models.CharField(max_length=50, db_index=True)
    subject = models.CharField(max_length=200, blank=True, default='')
    provider_message_id = models.CharField(
        max_length=120, blank=True, default='',
        help_text="Resend (or other provider) external id, for tracing.",
    )
    error = models.CharField(
        max_length=300, blank=True, default='',
        help_text="If non-empty, the send failed and we'll retry on the next cron tick.",
    )
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Email envoyé (sequence lead)"
        verbose_name_plural = "Emails envoyés (sequence lead)"
        unique_together = [['lead', 'step']]
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['lead', 'step']),
            models.Index(fields=['-sent_at']),
        ]

    def __str__(self):
        return f"{self.lead.email} · {self.step}"


class SiteMemory(models.Model):
    """Per-site RAG store. Each row is one chunk (article paragraph, KB section,
    audit summary, editorial decision, manual note) with its pgvector embedding.

    Used by ArticleGenerator (and any future LLM call) to fetch the top-k most
    relevant past context for the current generation query, bypassing the
    stateless prompt limitation: the LLM 'remembers' the site across calls.

    Dimensions = 512 (voyage-3-lite). Content_hash lets us skip re-embedding
    identical chunks on re-index.
    """
    KIND_CHOICES = [
        ('article', 'Article publié'),
        ('kb', 'Knowledge base'),
        ('audit', 'Audit SEO'),
        ('decision', 'Décision éditoriale'),
        ('manual', 'Note manuelle'),
    ]

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='memories')
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, db_index=True)
    title = models.CharField(max_length=300, blank=True, default='')
    content = models.TextField()
    embedding = VectorField(dimensions=512, null=True, blank=True)
    source_ref = models.CharField(
        max_length=200, blank=True, default='',
        help_text="Pointer back to the source (HostedPost slug, audit id, etc.). "
                  "Used to wipe + re-index when the source mutates.",
    )
    content_hash = models.CharField(max_length=64, db_index=True)
    token_count = models.PositiveIntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    # Feedback loop: bumped +1 each time this chunk contributed to an article
    # the user kept ("good"), -1 when regenerated/rejected ("bad"). retrieve()
    # subtracts feedback_score * 0.01 from cosine distance so positively-rated
    # chunks float to the top of future retrievals. Capped during retrieval
    # to ±0.5 distance equivalent so a few votes don't drown out semantic match.
    feedback_score = models.IntegerField(default=0, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Mémoire site"
        verbose_name_plural = "Mémoires sites"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site', 'kind']),
            models.Index(fields=['site', 'source_ref']),
        ]

    def __str__(self):
        return f"[{self.kind}] {self.title or self.content[:50]} ({self.site_id})"


class HostedCategory(models.Model):
    """Categories stored in the dashboard's own DB (for sites without database_url)."""
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='hosted_categories')
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    description = models.TextField(blank=True)

    class Meta:
        unique_together = [['site', 'slug']]
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.site.name})"


class HostedTag(models.Model):
    """Tags stored in the dashboard's own DB."""
    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='hosted_tags')
    name = models.CharField(max_length=50)

    class Meta:
        unique_together = [['site', 'name']]
        ordering = ['name']

    def __str__(self):
        return self.name


class HostedPost(models.Model):
    """Blog posts stored in the dashboard's own DB (hosted mode)."""
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('published', 'Publie'),
        ('scheduled', 'Planifie'),
    ]

    LANGUAGE_CHOICES = [
        ('fr', 'Francais'),
        ('en', 'English'),
        ('es', 'Espanol'),
    ]

    site = models.ForeignKey(Site, on_delete=models.CASCADE, related_name='hosted_posts')
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200)
    excerpt = models.TextField()
    content = models.TextField()
    author = models.CharField(max_length=100, default="Admin")
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='fr', db_index=True)
    translation_group = models.UUIDField(default=uuid.uuid4, db_index=True)
    category = models.ForeignKey(
        HostedCategory, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='posts'
    )
    tags = models.ManyToManyField(HostedTag, blank=True, related_name='posts')
    cover_image = models.URLField(max_length=500, blank=True)
    reading_time = models.PositiveIntegerField(default=5)
    featured = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    scheduled_at = models.DateTimeField(null=True, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    published_at = models.DateField(
        null=True, blank=True,
        help_text="Set when status becomes 'published'. Drafts and "
                  "scheduled-but-not-yet-fired posts have null here."
    )
    # RAG feedback loop: stores list of SiteMemory.id that were retrieved and
    # injected in the prompt when this article was AI-generated. Lets us bump
    # feedback_score on those exact chunks when the user signals "good" or
    # "bad". Empty for human-written posts. Capped at ~20 ids = top retrieval.
    memory_chunks_used = models.JSONField(default=list, blank=True)
    feedback_rating = models.SmallIntegerField(
        default=0,
        help_text="0 = no feedback yet, 1 = good (boost chunks), -1 = bad (penalize)",
    )
    schema_jsonld = models.JSONField(
        default=dict, blank=True,
        help_text="Auto-computed FAQPage JSON-LD (schema.org) injected in <head> "
                  "at render time. Filled by HostedPost.save() when the content "
                  "contains a '## FAQ' block with question/answer pairs; empty "
                  "dict otherwise. Re-computed on every save so editing the FAQ "
                  "in the editor keeps the markup in sync.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['site', 'slug']]
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['site', '-published_at']),
            models.Index(fields=['site', 'slug']),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Recompute the FAQPage JSON-LD from the markdown body so the public
        # render template can just inject it without re-parsing. Only published
        # posts get a non-empty payload because Google won't index drafts and
        # surfacing FAQ markup on a hidden page is just noise.
        try:
            if self.status == 'published':
                self.schema_jsonld = _build_faq_jsonld(self.content, self.language) or {}
            else:
                self.schema_jsonld = {}
        except Exception:
            # Never let JSON-LD computation block the save - the field is purely
            # additive. Worst case we lose the FAQ markup for one revision.
            self.schema_jsonld = {}
        # When the caller passes update_fields (partial save), make sure we also
        # persist the recomputed schema_jsonld; otherwise the freshly computed
        # value silently stays in memory only.
        update_fields = kwargs.get('update_fields')
        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add('schema_jsonld')
            kwargs['update_fields'] = list(update_fields)
        super().save(*args, **kwargs)


# Compiled once at import time. Matches a "## FAQ" or "## Foire aux questions"
# H2 (case-insensitive) and captures everything until the next H2 or EOF.
_FAQ_SECTION_RE = re.compile(
    r'^##\s+(?:FAQ|F\.A\.Q\.?|Foire aux questions|Questions fr[ée]quentes|Frequently asked questions)\b[^\n]*\n(.*?)(?=^##\s|\Z)',
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)
# Inside the FAQ block, Q/A pairs can take several shapes. We support:
#   - "### Question?\nAnswer..."  (markdown sub-heading per Q)
#   - "**Question?**\nAnswer..."  (bold question per Q)
#   - "Q: Question?\nR: Answer"   (legacy generator output, FR)
#   - "Q: Question?\nA: Answer"   (legacy generator output, EN)
_FAQ_PAIR_PATTERNS = [
    re.compile(r'^###\s+(?P<q>.+?)\s*\n+(?P<a>.+?)(?=\n###\s|\n\*\*|\nQ\s*:|\Z)',
               re.MULTILINE | re.DOTALL),
    re.compile(r'^\*\*(?P<q>.+?)\*\*\s*\n+(?P<a>.+?)(?=\n\*\*|\n###\s|\nQ\s*:|\Z)',
               re.MULTILINE | re.DOTALL),
    re.compile(r'^Q\s*:\s*(?P<q>.+?)\s*\n+(?:R|A)\s*:\s*(?P<a>.+?)(?=\nQ\s*:|\n###\s|\n\*\*|\Z)',
               re.MULTILINE | re.DOTALL),
]


def _build_faq_jsonld(content, language='fr'):
    """Parse a markdown body and return a schema.org FAQPage JSON-LD dict.

    Returns an empty dict if no FAQ block is found or no Q/A pairs match.
    The returned shape is the standard FAQPage Question/Answer tree:
    https://developers.google.com/search/docs/appearance/structured-data/faqpage

    Idempotent and side-effect-free. Safe to call on every save.
    """
    if not content:
        return {}
    match = _FAQ_SECTION_RE.search(content)
    if not match:
        return {}
    section = match.group(1).strip()
    if not section:
        return {}

    pairs = []
    seen_questions = set()
    for pattern in _FAQ_PAIR_PATTERNS:
        for m in pattern.finditer(section):
            q = (m.group('q') or '').strip().rstrip(':').strip()
            a = (m.group('a') or '').strip()
            if not q or not a:
                continue
            # Strip surrounding markdown (bold/italic) leftovers from the
            # question and collapse internal whitespace.
            q = re.sub(r'\s+', ' ', q).strip('*_ ').strip()
            a = re.sub(r'\s+', ' ', a).strip()
            key = q.lower()
            if key in seen_questions:
                continue
            seen_questions.add(key)
            pairs.append((q, a))
        if pairs:
            # First pattern that matched wins, so we don't double-count when
            # the LLM mixes formats.
            break

    if not pairs:
        return {}

    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'inLanguage': language or 'fr',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': q,
                'acceptedAnswer': {
                    '@type': 'Answer',
                    'text': a,
                },
            }
            for q, a in pairs
        ],
    }


class ApiToken(models.Model):
    """Long-lived API token for the developer-facing /api/v1/ endpoints.

    The plain-text token is shown ONCE at creation and never stored - only
    its SHA256 hash. Format: `btb_<43-char url-safe random>`.
    Multiple tokens per user (different scopes / contexts).
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='api_tokens'
    )
    name = models.CharField(
        max_length=100,
        help_text="Friendly label set by the user. E.g. 'n8n production', 'Zapier'."
    )
    # Stored = SHA256(plain_token).hexdigest(). Plain is never persisted.
    key_hash = models.CharField(max_length=64, unique=True, db_index=True)
    # First 8 chars of the plain token, kept for UI identification (not enough to reconstruct).
    key_prefix = models.CharField(max_length=12, blank=True, default='')
    last_used_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'revoked_at']),
        ]

    def __str__(self):
        return f"{self.user.username}:{self.name} ({self.key_prefix}...)"

    @property
    def is_active(self):
        return self.revoked_at is None


class Subscription(models.Model):
    """One subscription per user. Tracks the active plan + Stripe IDs.
    Default plan = 'free' (auto-created when missing).
    """
    PLAN_CHOICES = [
        ('free', 'Essai (gratuit)'),
        ('solo', 'Solo'),
        ('pro', 'Pro'),
        ('agency', 'Agence'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('trialing', 'Trial'),
        ('past_due', 'Past Due'),
        ('canceled', 'Cancelled'),
        ('incomplete', 'Incomplete'),
        ('unpaid', 'Unpaid'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='subscription'
    )
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    stripe_customer_id = models.CharField(max_length=100, blank=True, default='', db_index=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, default='')
    current_period_end = models.DateTimeField(null=True, blank=True)
    cancel_at_period_end = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.plan} ({self.status})"

    @property
    def is_paid(self):
        return self.plan in ('solo', 'pro', 'agency') and self.status in ('active', 'trialing')

    def get_limits(self):
        """Return dict of plan limits: {sites_max, articles_per_month, keywords_max}."""
        return {
            'free':   {'sites_max': 1, 'articles_per_month': 1,   'keywords_max': 0},
            'solo':   {'sites_max': 1, 'articles_per_month': 8,   'keywords_max': 10},
            'pro':    {'sites_max': 2, 'articles_per_month': 60,  'keywords_max': 30},
            'agency': {'sites_max': 5, 'articles_per_month': 200, 'keywords_max': 100},
        }.get(self.plan, {'sites_max': 1, 'articles_per_month': 1, 'keywords_max': 0})


class CreditBalance(models.Model):
    """Top-up credit balance per user. One row per user. Credits never expire.
    Consumed AFTER monthly plan quota is exhausted: see `quota.consume_article`.
    """
    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='credit_balance'
    )
    balance = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username}: {self.balance} credits"


class CreditTransaction(models.Model):
    """Audit log of every credit movement (purchase, spend, refund, gift).
    Append-only: rows are never updated or deleted, so the sum should always
    match the user's current `CreditBalance.balance` (sanity-check).
    """
    KIND_CHOICES = [
        ('purchase', 'Achat'),
        ('spend', 'Consommation'),
        ('refund', 'Remboursement'),
        ('gift', 'Cadeau'),
    ]

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='credit_transactions'
    )
    amount = models.IntegerField(
        help_text="Positive for credits added, negative for spent."
    )
    kind = models.CharField(max_length=20, choices=KIND_CHOICES)
    stripe_session_id = models.CharField(
        max_length=120, blank=True, default='', db_index=True,
        help_text="Stripe Checkout Session id for purchase events."
    )
    description = models.CharField(max_length=200, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        sign = '+' if self.amount >= 0 else ''
        return f"{self.user.username} {sign}{self.amount} ({self.kind})"


class MonthlyArticleQuota(models.Model):
    """Counts articles generated by a user during a given calendar month.
    Used to enforce per-plan `articles_per_month` limits. Each (user, month_key)
    row is created lazily on the first generation that month and incremented
    atomically thereafter. `month_key` is `YYYY-MM` so a new month implicitly
    resets the count.
    """
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='article_quotas'
    )
    month_key = models.CharField(max_length=7, db_index=True)
    count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['user', 'month_key']]
        ordering = ['-month_key']
        indexes = [
            models.Index(fields=['user', 'month_key']),
        ]

    def __str__(self):
        return f"{self.user.username} {self.month_key}: {self.count}"


class Redirect(models.Model):
    """301 redirect from an old slug to a new one (per language).

    Auto-created when an article's slug changes via the dashboard, so old
    bookmarks / external backlinks keep working. Can also be created manually
    via the dashboard UI.
    """
    LANGUAGE_CHOICES = Site.LANGUAGE_CHOICES

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name='redirects'
    )
    from_slug = models.CharField(max_length=255)
    to_slug = models.CharField(max_length=255)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='fr')
    hit_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['site', 'from_slug', 'language']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site', 'from_slug', 'language']),
        ]

    def __str__(self):
        return f"{self.from_slug} → {self.to_slug} ({self.language}, {self.site.name})"


class TrackedKeyword(models.Model):
    """Keywords whose Google SERP position the user wants to track over time."""
    LANGUAGE_CHOICES = Site.LANGUAGE_CHOICES
    INTENT_CHOICES = [
        ('info', 'Informationnel'),
        ('commercial', 'Commercial'),
        ('transactional', 'Transactionnel'),
        ('local', 'Local'),
    ]

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name='tracked_keywords'
    )
    keyword = models.CharField(max_length=255)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='fr')
    intent = models.CharField(
        max_length=20, choices=INTENT_CHOICES, default='info', db_index=True,
        help_text="Classification d'intent. Determine le type d'article que "
                  "l'autopilote generera (guide / comparison / review / local)."
    )
    target_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text="Optional. The article URL we expect to rank - used to highlight if the page actually ranks."
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['site', 'keyword', 'language']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site', 'is_active']),
        ]

    def __str__(self):
        return f"{self.keyword} ({self.language}) - {self.site.name}"


class SerpRank(models.Model):
    """One snapshot of a tracked keyword's SERP position at a point in time."""
    tracked = models.ForeignKey(
        TrackedKeyword, on_delete=models.CASCADE, related_name='snapshots'
    )
    position = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Position 1-100, NULL if not in top 100"
    )
    url = models.URLField(max_length=500, blank=True, default='')
    title = models.CharField(max_length=500, blank=True, default='')
    is_target_match = models.BooleanField(
        default=False,
        help_text="True if the ranking URL matches the tracked target_url"
    )
    source = models.CharField(max_length=20, default='serper')
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-recorded_at']
        indexes = [
            models.Index(fields=['tracked', '-recorded_at']),
        ]

    def __str__(self):
        return f"{self.tracked.keyword} #{self.position} ({self.recorded_at.date()})"


class ArticleBaseline(models.Model):
    """Snapshot of a HostedPost's GSC metrics at a fixed reference date.

    Two creation paths:
      1. At GSC-connect time, we snapshot the N most recent published posts
         to anchor "before Gridar" -> `is_pre_gridar=True`, post optional.
      2. At publish time of an AI-generated article, we record day-0 metrics
         (0 impressions, 0 clicks) so the J+30/60/90 attributions have a
         monotonic baseline to compute deltas against -> `is_pre_gridar=False`,
         post mandatory.

    Idempotency: at most ONE baseline per (site, post). Recapture only happens
    if `captured_at` is older than `BASELINE_REFRESH_DAYS` (default 30).
    """
    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name='baselines'
    )
    post = models.ForeignKey(
        HostedPost, on_delete=models.CASCADE,
        related_name='baselines', null=True, blank=True,
        help_text="Null when the baseline is a pre-Gridar site-level anchor.",
    )
    captured_at = models.DateTimeField(auto_now_add=True)
    period_start = models.DateField(
        help_text="GSC window start used for impressions/clicks/position."
    )
    period_end = models.DateField(
        help_text="GSC window end (inclusive)."
    )
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    avg_position = models.FloatField(null=True, blank=True)
    top_queries = models.JSONField(
        default=list, blank=True,
        help_text='[{"query": str, "impressions": int, "clicks": int, "position": float}, ...]',
    )
    is_pre_gridar = models.BooleanField(
        default=False,
        help_text="True for the historical anchor captured at GSC-connect time.",
    )

    class Meta:
        indexes = [
            models.Index(fields=['site', '-captured_at']),
            models.Index(fields=['post']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'post'],
                condition=models.Q(post__isnull=False),
                name='uniq_baseline_per_post',
            ),
        ]

    def __str__(self):
        suffix = 'pre-gridar' if self.is_pre_gridar else (self.post.slug if self.post else 'site')
        return f"Baseline {self.site.name}/{suffix} ({self.captured_at.date()})"


class ArticleAttribution(models.Model):
    """One GSC snapshot of a HostedPost at a fixed horizon from publish.

    Horizons we capture: 30, 60, 90 days after `post.published_at`. The
    `attribution_snapshot_run` cron walks posts whose published_at is exactly
    today - horizon and inserts the row idempotently (unique_together).
    """
    HORIZON_CHOICES = [(30, '30d'), (60, '60d'), (90, '90d')]

    post = models.ForeignKey(
        HostedPost, on_delete=models.CASCADE, related_name='attributions'
    )
    days_since_publish = models.PositiveSmallIntegerField(choices=HORIZON_CHOICES)
    captured_at = models.DateTimeField(auto_now_add=True)
    period_start = models.DateField(
        help_text="GSC window start. Usually published_at, capped at 16 months for GSC."
    )
    period_end = models.DateField(
        help_text="GSC window end. Usually today (captured_at date)."
    )
    indexed = models.BooleanField(
        default=False,
        help_text="True if GSC returned any query rows for this page URL.",
    )
    impressions = models.PositiveIntegerField(default=0)
    clicks = models.PositiveIntegerField(default=0)
    avg_position = models.FloatField(null=True, blank=True)
    top_queries = models.JSONField(default=list, blank=True)
    delta_vs_baseline = models.JSONField(
        default=dict, blank=True,
        help_text='{"impressions": int, "clicks": int, "avg_position": float|null}',
    )

    class Meta:
        unique_together = [('post', 'days_since_publish')]
        indexes = [
            models.Index(fields=['post', 'days_since_publish']),
            models.Index(fields=['-captured_at']),
        ]

    def __str__(self):
        return f"Attribution {self.post.slug} J+{self.days_since_publish}"


class ProofShareToken(models.Model):
    """Public read-only access token to a site's proof summary page.

    One token per site (OneToOne). When `enabled=True`, GET /api/public/proof/<token>/
    returns the site-level before/after summary. Setting enabled=False or
    revoking the token kills the public page immediately.
    """
    site = models.OneToOneField(
        Site, on_delete=models.CASCADE, related_name='proof_token'
    )
    token = models.CharField(
        max_length=48, unique=True, db_index=True,
        help_text="URL-safe random token. Rotated on revoke.",
    )
    enabled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"ProofToken {self.site.name} ({'on' if self.enabled else 'off'})"


# =============================================================================
# Topic Cluster Planner (2026-06-08)
# =============================================================================
# A landing page is structured content (hero / value props / FAQ / CTA) - NOT a
# blog article. The Topic Cluster Planner classifies a target keyword's intent
# then proposes a site structure (one pillar landing + N supporting blog posts)
# the user can approve. HostedLanding stores the landings, KeywordStrategy
# stores the proposal + approval audit trail.


class HostedLanding(models.Model):
    """Structured landing page (transactional / service / pillar) hosted on Gridar.

    Distinct from HostedPost (blog article) because landings are NOT prose - they
    are structured blocks (hero, value props, social proof, FAQ, bottom CTA)
    rendered by the public frontend with conversion-optimized layout. Each
    landing targets ONE primary keyword and lives at /landings/<slug>.
    """
    STATUS_CHOICES = [
        ('draft', 'Brouillon'),
        ('published', 'Publie'),
    ]
    LANGUAGE_CHOICES = [
        ('fr', 'Francais'),
        ('en', 'English'),
        ('es', 'Espanol'),
    ]
    PAGE_SUBTYPE_CHOICES = [
        ('service', 'Page service (transactionnel)'),
        ('product', 'Fiche produit'),
        ('pillar', 'Pillar page (cluster)'),
        ('comparison', 'Comparatif'),
        ('local', 'Page locale (geo)'),
        ('about', 'A propos'),
        ('contact', 'Contact'),
        ('generic', 'Generique'),
    ]
    SCHEMA_TYPE_CHOICES = [
        ('WebPage', 'WebPage'),
        ('Service', 'Service'),
        ('Product', 'Product'),
        ('LocalBusiness', 'LocalBusiness'),
        ('FAQPage', 'FAQPage'),
        ('Article', 'Article'),
    ]

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name='hosted_landings'
    )
    title = models.CharField(max_length=200, help_text="SEO <title>")
    slug = models.SlugField(max_length=200)
    h1 = models.CharField(
        max_length=200,
        help_text="Visible H1, often longer / more emotional than the <title>.",
    )
    hero_subtitle = models.CharField(
        max_length=500, blank=True, default='',
        help_text="Sentence under the H1 - 1-2 lines max.",
    )
    hero_cta_text = models.CharField(max_length=80, blank=True, default='')
    hero_cta_url = models.CharField(max_length=500, blank=True, default='')
    value_props = models.JSONField(
        default=list, blank=True,
        help_text='[{"icon": str, "title": str, "description": str}, ...]',
    )
    social_proof = models.JSONField(
        default=list, blank=True,
        help_text='[{"type": "testimonial"|"logo"|"stat", ...}, ...]',
    )
    faq = models.JSONField(
        default=list, blank=True,
        help_text='[{"question": str, "answer": str}, ...]',
    )
    cta_bottom_text = models.CharField(max_length=80, blank=True, default='')
    cta_bottom_url = models.CharField(max_length=500, blank=True, default='')
    body_markdown = models.TextField(
        blank=True, default='',
        help_text="Optional free-form markdown rendered between value_props and FAQ.",
    )
    target_keyword = models.CharField(
        max_length=200, blank=True, default='', db_index=True,
        help_text="Primary keyword this landing targets.",
    )
    schema_type = models.CharField(
        max_length=20, choices=SCHEMA_TYPE_CHOICES, default='WebPage',
    )
    page_subtype = models.CharField(
        max_length=20, choices=PAGE_SUBTYPE_CHOICES, default='generic', db_index=True,
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True,
    )
    language = models.CharField(
        max_length=2, choices=LANGUAGE_CHOICES, default='fr', db_index=True,
    )
    translation_group = models.UUIDField(default=uuid.uuid4, db_index=True)
    cover_image = models.URLField(max_length=500, blank=True, default='')
    meta_description = models.CharField(max_length=300, blank=True, default='')
    schema_jsonld = models.JSONField(
        default=dict, blank=True,
        help_text="Auto-computed JSON-LD (Service/FAQPage/etc) injected at render time.",
    )
    published_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['site', 'slug']]
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['site', 'status']),
            models.Index(fields=['site', 'page_subtype']),
        ]

    def __str__(self):
        return f"{self.title} ({self.site.name})"


class KeywordStrategy(models.Model):
    """Proposed site structure for a target keyword.

    Generated by V1ProposeKeywordStrategyView: classifies intent, analyzes the
    SERP, then proposes the proper structure (single landing / pillar+cluster /
    blog post). User reviews + approves; on approval the engine generates the
    landings + articles described in proposed_pages.
    """
    INTENT_CHOICES = [
        ('transactional', 'Transactionnel'),
        ('commercial', 'Commercial (comparatif / review)'),
        ('informational', 'Informationnel'),
        ('navigational', 'Navigationnel (brand)'),
        ('local', 'Local'),
    ]
    BUSINESS_MODEL_CHOICES = Site.BUSINESS_MODEL_CHOICES
    PROPOSED_STRUCTURE_CHOICES = [
        ('single_landing', 'Une seule landing'),
        ('pillar_cluster', 'Pillar + cluster d articles'),
        ('blog_post', 'Article de blog standalone'),
        ('comparison_table', 'Page comparatif (vs)'),
        ('local_landing', 'Landing locale (geo)'),
    ]
    STATUS_CHOICES = [
        ('draft', 'Brouillon (propose)'),
        ('approved', 'Approuve par l utilisateur'),
        ('generating', 'Generation en cours'),
        ('done', 'Pages generees'),
        ('rejected', 'Rejete'),
    ]

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name='keyword_strategies'
    )
    keyword = models.CharField(max_length=255, db_index=True)
    language = models.CharField(
        max_length=2, choices=Site.LANGUAGE_CHOICES, default='fr',
    )
    intent = models.CharField(
        max_length=20, choices=INTENT_CHOICES, default='informational', db_index=True,
    )
    intent_confidence = models.FloatField(
        default=0.5,
        help_text="0.0-1.0 confidence score from the classifier.",
    )
    business_model_detected = models.CharField(
        max_length=20, choices=BUSINESS_MODEL_CHOICES, blank=True, default='',
        help_text="Business model inferred from SERP (may differ from site's).",
    )
    serp_analysis = models.JSONField(
        default=dict, blank=True,
        help_text="{'top_results': [...], 'features': {...}, 'avg_word_count': int}",
    )
    proposed_structure = models.CharField(
        max_length=30, choices=PROPOSED_STRUCTURE_CHOICES, default='blog_post',
    )
    proposed_pages = models.JSONField(
        default=list, blank=True,
        help_text='[{"type":"landing|article","title":str,"slug":str,'
                  '"keyword":str,"role":"pillar|cluster|alternative"}, ...]',
    )
    rationale = models.TextField(
        blank=True, default='',
        help_text="Plain-language explanation of why this structure was chosen.",
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='draft', db_index=True,
    )
    generated_pages_fks = models.JSONField(
        default=dict, blank=True,
        help_text='{"landings": [<HostedLanding.id>, ...], '
                  '"articles": [<HostedPost.id>, ...]} after approval.',
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='approved_strategies',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [['site', 'keyword']]
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site', 'status']),
            models.Index(fields=['site', 'intent']),
        ]

    def __str__(self):
        return f"Strategy '{self.keyword}' ({self.intent}/{self.status})"


# --------------------------------------------------------------------------
# AI Visibility tracking (2026-06-08)
# Track how a site is mentioned in LLM responses (ChatGPT / Perplexity /
# Gemini / SearchGPT / Claude). One prompt -> N results across engines.
# --------------------------------------------------------------------------

class AiVisibilityPrompt(models.Model):
    """A prompt the user wants to test against LLMs to see if their site is
    cited in the answer (e.g. 'meilleur outil SEO IA pour PME au Quebec').
    """
    TARGET_INTENT_CHOICES = [
        ('informational', 'Informationnel'),
        ('commercial', 'Commercial / Comparatif'),
        ('transactional', 'Transactionnel'),
        ('navigational', 'Navigationnel'),
        ('local', 'Local'),
    ]

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name='ai_visibility_prompts'
    )
    prompt = models.TextField(
        verbose_name="Prompt teste",
        help_text="Question posee aux LLMs pour mesurer la visibilite."
    )
    target_intent = models.CharField(
        max_length=20, choices=TARGET_INTENT_CHOICES, blank=True, null=True,
    )
    language = models.CharField(
        max_length=2, choices=Site.LANGUAGE_CHOICES, default='fr',
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['site', '-created_at']),
        ]

    def __str__(self):
        excerpt = (self.prompt or '')[:60]
        return f"AiVisibilityPrompt #{self.id}: {excerpt}"


class AiVisibilityResult(models.Model):
    """One check of a prompt against one LLM engine. Stores whether the
    site was cited, optional citation_url and rank.
    """
    ENGINE_CHOICES = [
        ('chatgpt', 'ChatGPT'),
        ('perplexity', 'Perplexity'),
        ('gemini', 'Gemini'),
        ('searchgpt', 'SearchGPT'),
        ('claude', 'Claude'),
    ]

    prompt = models.ForeignKey(
        AiVisibilityPrompt, on_delete=models.CASCADE, related_name='results'
    )
    engine = models.CharField(
        max_length=20, choices=ENGINE_CHOICES, db_index=True,
    )
    response_excerpt = models.TextField(
        blank=True, default='',
        help_text="Premiers ~500 caracteres de la reponse du LLM."
    )
    is_cited = models.BooleanField(
        default=False, db_index=True,
        help_text="True si le domaine du site apparait dans la reponse."
    )
    citation_url = models.URLField(
        max_length=500, blank=True, null=True,
    )
    citation_rank = models.PositiveIntegerField(
        blank=True, null=True,
        help_text="Position de la citation dans la reponse (1 = premiere)."
    )
    checked_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-checked_at']
        indexes = [
            models.Index(fields=['prompt', 'engine']),
            models.Index(fields=['prompt', '-checked_at']),
        ]

    def __str__(self):
        return f"AiVisibilityResult #{self.id} ({self.engine}, cited={self.is_cited})"


class StrategicOpportunity(models.Model):
    """Cached output of the strategic SEO engine.

    For each (site, tracked_keyword) pair where the keyword's intent is
    transactional / commercial / local AND no landing already targets it,
    the engine produces a structured page concept (page_type, hook,
    capture_mechanism, conversion_path, etc.) plus a traffic / lead
    estimate. Stored here so the UI doesn't have to re-run Claude on every
    page load.

    Status flow:
      proposed  -> generated by the engine, waiting for user review
      approved  -> user clicked "Create", a HostedLanding was generated
      dismissed -> user clicked "Pas pertinent" (won't re-propose unless
                   they explicitly refresh)
      done      -> the landing has been published and is live
    """

    STATUS_CHOICES = [
        ('proposed', 'Proposée'),
        ('approved', 'Approuvée'),
        ('dismissed', 'Écartée'),
        ('done', 'Page créée'),
    ]
    PRIORITY_CHOICES = [
        ('high', 'Élevée'),
        ('medium', 'Moyenne'),
        ('low', 'Faible'),
    ]

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name='strategic_opportunities'
    )
    tracked_keyword = models.ForeignKey(
        TrackedKeyword, on_delete=models.CASCADE,
        related_name='strategic_opportunities',
        null=True, blank=True,
        help_text="Mot-clé source. NULL si l'opportunité est issue d'une "
                  "suggestion machine plutôt que d'un keyword tracké.",
    )
    keyword = models.CharField(
        max_length=255, db_index=True,
        help_text="Copie du mot-clé pour requêtes sans join.",
    )
    intent = models.CharField(
        max_length=20, choices=TrackedKeyword.INTENT_CHOICES, default='commercial',
        db_index=True,
    )
    language = models.CharField(
        max_length=2, choices=Site.LANGUAGE_CHOICES, default='fr',
    )

    # Concept JSON populated by the Claude prompt. Schema:
    # {
    #   page_concept, page_type, suggested_title, suggested_url_path,
    #   hook, capture_mechanism, conversion_path, angle,
    #   asset_match (bool), asset_used (str|null), why_this_works,
    # }
    concept = models.JSONField(default=dict, blank=True)

    # Traffic + conversion estimate. Schema mirrors
    # strategic_opportunities.compute_traffic_estimate() output.
    estimate = models.JSONField(default=dict, blank=True)

    # Snapshot of the keyword's SERP position at proposal time, for context.
    current_position = models.PositiveIntegerField(null=True, blank=True)

    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default='medium', db_index=True,
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='proposed', db_index=True,
    )

    # Forward links so the UI can navigate to the generated landing.
    generated_landing = models.ForeignKey(
        HostedLanding, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='source_opportunities',
    )

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    refreshed_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Dernier appel Claude. Sert à éviter de re-générer un "
                  "concept tant qu'il n'a pas vieilli.",
    )
    dismissed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        # One live opportunity per (site, keyword). Re-running the engine
        # updates the same row instead of duplicating.
        constraints = [
            models.UniqueConstraint(
                fields=['site', 'keyword', 'language'],
                name='uniq_opportunity_per_keyword',
            ),
        ]
        ordering = ['-priority', '-created_at']
        indexes = [
            models.Index(fields=['site', 'status']),
            models.Index(fields=['site', '-created_at']),
        ]

    def __str__(self):
        return f"StrategicOpportunity #{self.id} kw='{self.keyword}' status={self.status}"
