from rest_framework import serializers
from .models import Site
from blog.models import BlogPost, Category, Tag


class SiteSerializer(serializers.ModelSerializer):
    is_hosted = serializers.BooleanField(read_only=True)

    class Meta:
        model = Site
        fields = ['id', 'name', 'database_url', 'domain', 'knowledge_base',
                  'vercel_deploy_hook', 'gsc_property_url',
                  'available_languages',
                  'api_key', 'is_hosted', 'created_at']
        read_only_fields = ['id', 'created_at', 'api_key', 'is_hosted']
        extra_kwargs = {
            'database_url': {'required': False, 'allow_blank': True},
        }

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
