"""
Modelos de domínio do app core organizados por subdomínio.
Reexportados aqui para compatibilidade com Django migrations e `from core.models import ...`.
"""

from .feature_flags import FeatureFlag
from .moderation import ModerationLog, PermanentBanRecord, Report
from .notifications import Notification, PushDevice
from .posts import Draft, DraftMedia, Hashtag, Post, PostBookmark, PostLike, PostMedia
from .social import Block, Follow, Mute
from .users import (
    AccessLog,
    OAuthAccount,
    PasswordResetToken,
    User,
    UserManager,
    UserProfile,
)

__all__ = [
    "AccessLog",
    "Block",
    "Draft",
    "DraftMedia",
    "FeatureFlag",
    "Follow",
    "Hashtag",
    "ModerationLog",
    "Mute",
    "Notification",
    "OAuthAccount",
    "PasswordResetToken",
    "PermanentBanRecord",
    "Post",
    "PostBookmark",
    "PostLike",
    "PostMedia",
    "PushDevice",
    "Report",
    "User",
    "UserManager",
    "UserProfile",
]
