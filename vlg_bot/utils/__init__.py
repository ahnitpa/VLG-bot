"""Package exports for vlg_bot utilities."""

from .embeds import build_avatar_embed, build_qna_embed, build_whois_embed
from .parsing import resolve_channel, resolve_member, resolve_role
from .permissions import (
    TRUSTED_DEV_IDS,
    dev_or_permissions,
    has_mod_perms,
    hierarchy_error,
    is_authorized,
    is_authorized_user,
    is_privileged_user,
    message_is_authorized,
    rate_comment,
    rate_text,
)

__all__ = [
    "TRUSTED_DEV_IDS",
    "build_avatar_embed",
    "build_qna_embed",
    "build_whois_embed",
    "dev_or_permissions",
    "has_mod_perms",
    "hierarchy_error",
    "is_authorized",
    "is_authorized_user",
    "is_privileged_user",
    "message_is_authorized",
    "rate_comment",
    "rate_text",
    "resolve_channel",
    "resolve_member",
    "resolve_role",
]
