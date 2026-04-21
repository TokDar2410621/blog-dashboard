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
    name = models.CharField(max_length=200, verbose_name="Nom du site")
    database_url = models.TextField(
        blank=True, default='',
        verbose_name="DATABASE_URL PostgreSQL",
        help_text="Laisser vide pour utiliser le stockage hébergé du dashboard"
    )
    domain = models.CharField(max_length=255, blank=True, verbose_name="Domaine du site")
    knowledge_base = models.TextField(
        blank=True, default='',
        verbose_name="Base de connaissances",
        help_text="Contexte personnel pour la generation d'articles (qui tu es, tes projets, ton ton, etc.)"
    )
    vercel_deploy_hook = models.URLField(
        max_length=500, blank=True, default='',
        verbose_name="Vercel Deploy Hook",
        help_text="URL du Deploy Hook Vercel pour redéployer le site après modification d'articles"
    )
    gsc_property_url = models.URLField(
        max_length=300, blank=True, default='',
        help_text="URL de la propriété Search Console (ex: https://tokamdarius.ca/)"
    )
    gsc_refresh_token = models.TextField(
        blank=True, default='',
        help_text="OAuth2 refresh token chiffré"
    )
    blog_config = models.JSONField(
        blank=True, null=True, default=None,
        verbose_name="Config tables blog",
        help_text="Mapping des tables/colonnes si le site n'utilise pas les tables blog_* standard"
    )
    api_key = models.CharField(
        max_length=64, blank=True, default='',
        verbose_name="Clé API publique",
        help_text="Utilisée pour accéder aux articles depuis le frontend du site"
    )
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sites')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Site"
        verbose_name_plural = "Sites"
        ordering = ['-created_at']

    @property
    def is_hosted(self):
        """Site without database_url uses the dashboard's hosted storage."""
        return not self.database_url

    def save(self, *args, **kwargs):
        if not self.api_key:
            self.api_key = uuid.uuid4().hex
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


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
