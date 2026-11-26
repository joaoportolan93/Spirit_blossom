"""
Views sociais divididas por subdomínio (ADR-N2).
"""

from .circle import (
    CloseFriendsCandidatesView,
    CloseFriendsListView,
    CloseFriendsView,
)
from .follows import (
    FollowRequestAcceptView,
    FollowRequestListView,
    FollowRequestRejectView,
    FollowSuggestionsView,
    FollowView,
)
from .profiles import ProfileDetailView, ProfileLikesView
from .relationships import (
    BlockedUsersListView,
    BlockView,
    MutedUsersListView,
    MuteView,
)

__all__ = [
    "BlockView",
    "BlockedUsersListView",
    "CloseFriendsCandidatesView",
    "CloseFriendsListView",
    "CloseFriendsView",
    "FollowRequestAcceptView",
    "FollowRequestListView",
    "FollowRequestRejectView",
    "FollowSuggestionsView",
    "FollowView",
    "MuteView",
    "MutedUsersListView",
    "ProfileDetailView",
    "ProfileLikesView",
]
