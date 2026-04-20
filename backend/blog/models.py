import uuid

from django.db import models
from django.utils.text import slugify


class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nom")
    slug = models.SlugField(unique=True, max_length=100)
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "Categorie"
        verbose_name_plural = "Categories"
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True, verbose_name="Nom")

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tags"
        ordering = ['name']

    def __str__(self):
        return self.name


class BlogPost(models.Model):
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

    title = models.CharField(max_length=200, verbose_name="Titre")
    slug = models.SlugField(unique=True, max_length=200)
    excerpt = models.TextField(verbose_name="Extrait")
    content = models.TextField(verbose_name="Contenu")
    author = models.CharField(max_length=100, default="Admin", verbose_name="Auteur")
    language = models.CharField(
        max_length=2, choices=LANGUAGE_CHOICES, default='fr',
        verbose_name="Langue", db_index=True
    )
    translation_group = models.UUIDField(
        default=uuid.uuid4, db_index=True,
        verbose_name="Groupe de traduction",
        help_text="Meme UUID partage par les traductions d'un meme article"
    )

    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True,
        related_name='posts', verbose_name="Categorie"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts', verbose_name="Tags")

    cover_image = models.URLField(max_length=500, blank=True, verbose_name="Image de couverture")
    reading_time = models.PositiveIntegerField(default=5, verbose_name="Temps de lecture (min)")
    featured = models.BooleanField(default=False, verbose_name="En vedette")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published', verbose_name="Statut")
    scheduled_at = models.DateTimeField(null=True, blank=True, verbose_name="Publication planifiee")
    view_count = models.PositiveIntegerField(default=0, verbose_name="Nombre de vues")

    published_at = models.DateField(verbose_name="Date de publication")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Date de creation")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Derniere modification")

    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['slug']),
            models.Index(fields=['featured']),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title
