"""Feature modules for the VLG Bot."""

from .afk import AFK_USERS, afklist_embed, handle_message, prefix_afk, prefix_afklist, set_afk, setup
from .fun import PrefixContext, handle_prefix, setup
from .music import GuildPlayer, MusicManager, Track, create_music_manager

__all__ = [
    "AFK_USERS",
    "GuildPlayer",
    "MusicManager",
    "PrefixContext",
    "Track",
    "afklist_embed",
    "create_music_manager",
    "handle_message",
    "handle_prefix",
    "prefix_afk",
    "prefix_afklist",
    "set_afk",
    "setup",
]
