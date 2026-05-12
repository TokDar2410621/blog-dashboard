"""Admin for the canonical blog app (used by external-mode sites and as a
fallback). For hosted-mode posts see sites_mgmt.admin.HostedPostAdmin."""
from django.contrib import admin

from .models import BlogPost, Category, Tag


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ('title', 'language', 'status', 'featured', 'published_at', 'view_count')
    list_filter = ('status', 'language', 'featured', 'published_at', 'category')
    search_fields = ('title', 'slug', 'excerpt', 'content', 'author')
    filter_horizontal = ('tags',)
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    readonly_fields = ('created_at', 'updated_at', 'translation_group')


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    search_fields = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)
