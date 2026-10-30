"""Compatibility wrapper for the moderation feature module."""

from .features.moderation import ModerationManager, create_moderation_manager

__all__ = ["ModerationManager", "create_moderation_manager"]
