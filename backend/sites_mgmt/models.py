import uuid

from django.db import models
from django.contrib.auth.models import User


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
    default_author = models.CharField(
        max_length=100, blank=True, default='',
        verbose_name="Auteur par défaut",
        help_text="Nom d'auteur attribué aux articles générés (utilisé aussi pour Schema.org). Vide = 'Admin'."
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

    # ── Intégrations externes ─────────────────────────────────────────
    vercel_deploy_hook = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="Vercel Deploy Hook",
        help_text="URL du Deploy Hook pour redéployer Vercel après chaque modification d'article"
    )
    gsc_property_url = models.URLField(
        max_length=300, blank=True, default='',
        verbose_name="Search Console — URL propriété",
        help_text="URL de la propriété Search Console (ex: https://tokamdarius.ca/)"
    )
    gsc_refresh_token = models.TextField(
        blank=True, default='',
        verbose_name="Search Console — refresh token",
        help_text="OAuth2 refresh token (sensible — ne pas exposer côté frontend)"
    )

    # ── API publique ──────────────────────────────────────────────────
    api_key = models.CharField(
        max_length=64, blank=True, default='', db_index=True,
        verbose_name="Clé API publique",
        help_text="Utilisée comme header X-Api-Key pour les endpoints publics. Auto-générée."
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
    def is_hosted(self):
        """Site without database_url uses the dashboard's hosted storage."""
        return not self.database_url

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
    published_at = models.DateField()
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


class TrackedKeyword(models.Model):
    """Keywords whose Google SERP position the user wants to track over time."""
    LANGUAGE_CHOICES = Site.LANGUAGE_CHOICES

    site = models.ForeignKey(
        Site, on_delete=models.CASCADE, related_name='tracked_keywords'
    )
    keyword = models.CharField(max_length=255)
    language = models.CharField(max_length=2, choices=LANGUAGE_CHOICES, default='fr')
    target_url = models.URLField(
        max_length=500, blank=True, default='',
        help_text="Optional. The article URL we expect to rank — used to highlight if the page actually ranks."
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
        return f"{self.keyword} ({self.language}) — {self.site.name}"


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
