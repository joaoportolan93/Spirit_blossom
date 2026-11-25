from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    AccessLog,
    Block,
    FeatureFlag,
    Follow,
    Mute,
    Notification,
    Post,
    PushDevice,
    User,
    UserProfile,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "username", "status", "is_active", "date_joined")
    list_filter = ("status", "is_active", "is_staff")
    search_fields = ("email", "username")
    ordering = ("-date_joined",)
    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        ("Status", {"fields": ("status", "is_active", "is_staff", "is_superuser")}),
        ("Permissões", {"fields": ("groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {"classes": ("wide",), "fields": ("email", "username", "password1", "password2")}),
    )


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at")
    raw_id_fields = ("user",)


@admin.register(AccessLog)
class AccessLogAdmin(admin.ModelAdmin):
    list_display = ("user", "ip_hash", "port", "timestamp")
    list_filter = ("timestamp",)
    readonly_fields = ("user", "ip_hash", "port", "timestamp")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "visibility", "created_at")
    list_filter = ("visibility", "created_at")
    search_fields = ("content_text", "author__username")
    readonly_fields = ("id", "created_at", "search_vector")


@admin.register(Follow)
class FollowAdmin(admin.ModelAdmin):
    list_display = ("follower", "followed", "is_close_friend", "created_at")
    raw_id_fields = ("follower", "followed")


@admin.register(Block)
class BlockAdmin(admin.ModelAdmin):
    list_display = ("blocker", "blocked", "created_at")
    raw_id_fields = ("blocker", "blocked")


@admin.register(Mute)
class MuteAdmin(admin.ModelAdmin):
    list_display = ("muter", "muted", "created_at")
    raw_id_fields = ("muter", "muted")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("notification_type", "recipient", "sender", "read", "created_at")
    list_filter = ("notification_type", "read")
    raw_id_fields = ("recipient", "sender")
    readonly_fields = ("created_at",)


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("key", "is_enabled", "rollout_percentage", "created_at", "updated_at")
    list_filter = ("is_enabled",)
    search_fields = ("key", "description")
    filter_horizontal = ("allowed_users",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("key", "description", "is_enabled")}),
        ("Rollout", {"fields": ("rollout_percentage", "allowed_users")}),
        ("Timestamps", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ("user", "platform", "device_name", "is_active", "created_at", "last_used_at")
    list_filter = ("platform", "is_active")
    search_fields = ("user__username", "device_name")
    raw_id_fields = ("user",)
    readonly_fields = ("id", "created_at", "last_used_at")

