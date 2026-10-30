"""Utility helpers for permissions, parsing, and embed builders."""

import random
from typing import Optional

import discord
from discord import app_commands

TRUSTED_DEV_IDS = [1151184036681752576, 1373999565312888842, 1325908309534048318]


def is_privileged_user(user: discord.abc.User, guild: Optional[discord.Guild]) -> bool:
    if user.id in TRUSTED_DEV_IDS:
        return True
    return bool(guild and user.id == guild.owner_id)


def is_authorized_user(user: discord.Member, guild: Optional[discord.Guild]) -> bool:
    if is_privileged_user(user, guild):
        return True
    return bool(guild and user.guild_permissions.administrator)


def message_is_authorized(message: discord.Message) -> bool:
    return is_authorized_user(message.author, message.guild)


def has_mod_perms(message: discord.Message, perm_name: str) -> bool:
    if is_authorized_user(message.author, message.guild):
        return True
    return bool(getattr(message.author.guild_permissions, perm_name, False))


def hierarchy_error(actor: discord.Member, target: discord.Member, guild: discord.Guild, verb: str) -> Optional[str]:
    if target == actor:
        return f"You can't {verb} yourself."
    if target == guild.owner:
        return f"You can't {verb} the server owner."
    if target.top_role >= actor.top_role and not is_privileged_user(actor, guild):
        return f"You can't {verb} someone with equal or higher role than you."
    return None


def is_authorized():
    async def predicate(interaction: discord.Interaction) -> bool:
        if is_authorized_user(interaction.user, interaction.guild):
            return True
        await interaction.response.send_message("❌ **Access Denied:** Only the Server Owner, an Administrator, or an authorized developer can use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)


def dev_or_permissions(**perms: bool):
    async def predicate(interaction: discord.Interaction) -> bool:
        if is_privileged_user(interaction.user, interaction.guild):
            return True
        permissions = interaction.permissions
        if permissions.administrator:
            return True
        missing = [name for name, value in perms.items() if getattr(permissions, name) != value]
        if not missing:
            return True
        raise app_commands.MissingPermissions(missing)
    return app_commands.check(predicate)


EIGHTBALL_RESPONSES = ["Absolutely yes.", "Signs point to yes.", "Try again later.", "Don't count on it.", "Don't do it!"]
SLAP_ITEMS = ["a giant wet trout", "a broken keyboard", "a stale baguette", "a comically large rubber duck"]
ROASTS = [
    "is the type of person who pushes a door that clearly says 'Pull'.",
    "looks like a person who claps when the airplane lands.",
    "probably types with their two index fingers while looking at the keyboard.",
    "has the emotional stability of an expired carton of milk.",
    "is the human equivalent of a participation trophy.",
]
GENERAL_QUESTIONS = [
    "If you could have any superpower but it only worked on Tuesdays, what would it be?",
    "Would you rather fight 100 duck-sized horses or 1 horse-sized duck?",
    "What's the weirdest thing you've ever eaten on purpose?",
]
TOPIC_QUESTIONS = {
    "food": ["What's a food combination that sounds disgusting but is actually fire?"],
    "gaming": ["What's the most rage-inducing game you've ever played?"],
    "life": ["What's a piece of advice that actually made your life worse?"],
}


def rate_comment(score: int) -> str:
    if score <= 3:
        return random.choice(["Absolutely tragic. Delete this.", "This is so bad it almost crashed my servers."])
    if score <= 7:
        return random.choice(["It's oki.", "Decent effort."])
    return random.choice(["Magnificent! I'm impressed.", "Amazing"])


def rate_text(thing: str) -> str:
    score = random.randint(0, 10)
    return f"**Judgement Time!**\n**Thing:** {thing}\n**Rating:** `{score}/10`\n*\"{rate_comment(score)}\"*"


def pick_question(topic: Optional[str]) -> str:
    if topic and topic.lower() in TOPIC_QUESTIONS:
        return random.choice(TOPIC_QUESTIONS[topic.lower()])
    return random.choice(GENERAL_QUESTIONS)


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


__all__ = [
    "TRUSTED_DEV_IDS",
    "EIGHTBALL_RESPONSES",
    "SLAP_ITEMS",
    "ROASTS",
    "GENERAL_QUESTIONS",
    "TOPIC_QUESTIONS",
    "is_privileged_user",
    "is_authorized_user",
    "message_is_authorized",
    "has_mod_perms",
    "hierarchy_error",
    "is_authorized",
    "dev_or_permissions",
    "rate_comment",
    "rate_text",
    "pick_question",
    "resolve_member",
    "resolve_role",
    "resolve_channel",
]
