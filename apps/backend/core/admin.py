from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    AccessLog,
    Block,
    Draft,
    DraftMedia,
    FeatureFlag,
    Follow,
    Hashtag,
    ModerationLog,
    Mute,
    Notification,
    PermanentBanRecord,
    Post,
    PostMedia,
    PushDevice,
    Report,
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


class PostMediaInline(admin.TabularInline):
    model = PostMedia
    extra = 0
    readonly_fields = ("id", "file", "order", "alt_text", "width", "height", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "visibility", "get_is_ephemeral", "expires_at", "created_at")
    list_filter = ("visibility", "created_at")
    search_fields = ("content_text", "author__username")
    readonly_fields = ("id", "created_at", "search_vector")
    inlines = [PostMediaInline]

    @admin.display(boolean=True, description="Efêmero")
    def get_is_ephemeral(self, obj):
        return obj.is_ephemeral


class DraftMediaInline(admin.TabularInline):
    model = DraftMedia
    extra = 0
    readonly_fields = ("id", "file", "order", "alt_text", "width", "height", "created_at")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Draft)
class DraftAdmin(admin.ModelAdmin):
    list_display = ("id", "author", "visibility", "ephemeral_duration_hours", "updated_at")
    list_filter = ("visibility", "ephemeral_duration_hours")
    search_fields = ("content_text", "author__username")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [DraftMediaInline]


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
    list_display = (
        "key",
        "is_enabled",
        "admin_only",
        "rollout_percentage",
        "created_at",
        "updated_at",
    )
    list_filter = ("is_enabled", "admin_only")
    search_fields = ("key", "description")
    filter_horizontal = ("allowed_users",)
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        (None, {"fields": ("key", "description", "is_enabled", "admin_only")}),
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


@admin.register(Hashtag)
class HashtagAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at")
    search_fields = ("name",)
    readonly_fields = ("id", "created_at")


@admin.register(PermanentBanRecord)
class PermanentBanRecordAdmin(admin.ModelAdmin):
    list_display = ("username", "preserve_for_authorities", "banned_at", "deleted_at")
    list_filter = ("preserve_for_authorities",)
    search_fields = ("username", "email_hash")
    readonly_fields = ("id", "username", "email_hash", "banned_at", "deleted_at")


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ("target_type", "target_id", "reason", "status", "reporter", "created_at")
    list_filter = ("target_type", "reason", "status")
    search_fields = ("target_id", "reporter__username", "description")
    raw_id_fields = ("reporter", "moderator")
    readonly_fields = ("id", "created_at")


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = (
        "action",
        "target_type",
        "target_id",
        "affected_user",
        "moderator",
        "created_at",
    )
    list_filter = ("action", "target_type")
    search_fields = ("target_id", "reason")
    raw_id_fields = ("affected_user", "moderator", "report")
    readonly_fields = ("id", "created_at")
