"""Compatibility wrapper for the music feature module."""

from .features.music import GuildPlayer, MusicManager, Track, create_music_manager

__all__ = ["Track", "GuildPlayer", "MusicManager", "create_music_manager"]
