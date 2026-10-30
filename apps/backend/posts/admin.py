from django.contrib import admin
from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "visibility", "created_at")
    list_filter = ("visibility", "created_at")
    search_fields = ("content_text", "author__username")
    readonly_fields = ("id", "created_at", "search_vector")
