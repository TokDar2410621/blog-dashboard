from rest_framework import serializers
from .models import Site
from blog.models import BlogPost, Category, Tag


class SiteSerializer(serializers.ModelSerializer):
    is_hosted = serializers.BooleanField(read_only=True)
    gsc_connected = serializers.SerializerMethodField()

    class Meta:
        model = Site
        fields = ['id', 'name', 'domain', 'description', 'og_image_url',
                  'database_url', 'knowledge_base', 'competitors',
                  'default_author', 'default_language', 'available_languages',
                  'author_role', 'author_bio', 'author_credentials',
                  'author_image_url', 'author_linkedin', 'author_twitter',
                  'author_website',
                  'business_model', 'primary_cta_text', 'primary_cta_url',
                  'delivery_mode',
                  'public_blog_domain', 'theme_config',
                  'vercel_deploy_hook', 'gsc_property_url', 'gsc_connected',
                  'api_key', 'is_hosted', 'is_active',
                  'created_at', 'updated_at',
                  'blog_config']
        read_only_fields = ['id', 'created_at', 'updated_at', 'api_key', 'is_hosted']
        extra_kwargs = {
            'database_url': {'required': False, 'allow_blank': True},
        }

    def get_gsc_connected(self, obj):
        # True once the OAuth refresh token is stored. The token itself stays
        # server-side (never serialized); this boolean is what lets the
        # settings UI render a "connected" state instead of forever offering
        # the "Connect" button.
        return bool(obj.gsc_refresh_token)

    def create(self, validated_data):
        validated_data['owner'] = self.context['request'].user
        return super().create(validated_data)


class SiteListSerializer(serializers.ModelSerializer):
    """Site sans database_url pour la liste (securite)."""
    class Meta:
        model = Site
        fields = ['id', 'name', 'domain', 'created_at']


class TagSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tag
        fields = ['id', 'name']


class CategorySerializer(serializers.ModelSerializer):
    posts_count = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'posts_count']

    def get_posts_count(self, obj):
        return obj.posts.count()


class BlogPostListSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    category_slug = serializers.CharField(source='category.slug', read_only=True)
    tags = serializers.StringRelatedField(many=True)

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'excerpt', 'author',
            'category', 'category_slug', 'tags',
            'cover_image', 'reading_time', 'featured',
            'status', 'view_count', 'language', 'translation_group',
            'published_at', 'created_at', 'updated_at'
        ]


class BlogPostDetailSerializer(serializers.ModelSerializer):
    category = serializers.StringRelatedField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = BlogPost
        fields = [
            'id', 'title', 'slug', 'excerpt', 'content',
            'author', 'category', 'tags',
            'cover_image', 'reading_time', 'featured',
            'status', 'view_count', 'language', 'translation_group',
            'published_at', 'created_at', 'updated_at'
        ]

    def get_tags(self, obj):
        return list(obj.tags.values_list('name', flat=True))


class BlogPostWriteSerializer(serializers.Serializer):
    """Serializer pour creer/modifier un article via DB directe."""
    title = serializers.CharField(max_length=200)
    slug = serializers.SlugField(max_length=200, required=False)
    excerpt = serializers.CharField()
    content = serializers.CharField()
    author = serializers.CharField(max_length=100, required=False, default="Admin")
    category = serializers.CharField(required=False, allow_blank=True)
    tags_input = serializers.ListField(
        child=serializers.CharField(), required=False, default=list
    )
    cover_image = serializers.URLField(required=False, allow_blank=True)
    reading_time = serializers.IntegerField(required=False, default=5)
    featured = serializers.BooleanField(required=False, default=False)
    status = serializers.ChoiceField(
        choices=['draft', 'published', 'scheduled'],
        required=False, default='published'
    )
    scheduled_at = serializers.DateTimeField(required=False, allow_null=True)
    published_at = serializers.DateField(required=False)
    language = serializers.ChoiceField(
        choices=['fr', 'en', 'es'], required=False, default='fr'
    )
    translation_group = serializers.UUIDField(required=False, allow_null=True)
    # RAG feedback loop: list of SiteMemory.id that were retrieved by the
    # generator and injected in the prompt. Passed from generate-inline
    # through to HostedPost so user feedback (good/bad) can be routed back
    # to those exact chunks. Empty list for human-written posts.
    memory_chunks_used = serializers.ListField(
        child=serializers.IntegerField(), required=False, default=list,
    )
