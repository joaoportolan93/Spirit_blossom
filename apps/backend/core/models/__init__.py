"""
Modelos de domínio do app core organizados por subdomínio.
Reexportados aqui para compatibilidade com Django migrations e `from core.models import ...`.
"""

from .feature_flags import FeatureFlag
from .moderation import ModerationLog, PermanentBanRecord, Report
from .notifications import Notification, PushDevice
from .posts import Draft, Hashtag, Post, PostBookmark, PostLike
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
    "PushDevice",
    "Report",
    "User",
    "UserManager",
    "UserProfile",
]
