"""Parsing utilities for member, role, and channel resolution."""

from typing import Optional

import discord


def _token_id(token: str, chars: str) -> Optional[int]:
    digits = token.strip(chars)
    return int(digits) if digits.isdigit() else None


def resolve_member(message: discord.Message, args: list):
    if not args:
        return None, []
    member_id = _token_id(args[0], "<@!>")
    member = message.guild.get_member(member_id) if member_id else None
    return member, args[1:]


def resolve_role(message: discord.Message, token: str) -> Optional[discord.Role]:
    role_id = _token_id(token, "<@&>")
    return message.guild.get_role(role_id) if role_id else None


def resolve_channel(message: discord.Message, token: str) -> Optional[discord.abc.GuildChannel]:
    channel_id = _token_id(token, "<#>")
    return message.guild.get_channel(channel_id) if channel_id else None


__all__ = ["resolve_member", "resolve_role", "resolve_channel"]
