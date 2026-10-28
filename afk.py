import time
from typing import Any

import discord
from discord import app_commands

AFK_USERS: dict[int, dict[str, Any]] = {}
IGNORED_MESSAGES: set[int] = set()


def format_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    if seconds < 60:
        return f"{seconds}s"

    minutes, secs = divmod(seconds, 60)
    if minutes < 60:
        return f"{minutes}m {secs}s"

    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        return f"{hours}h {minutes}m"

    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h"


async def set_afk(member: discord.Member, reason: str = "AFK") -> str:
    cleaned_reason = str(reason).strip() or "AFK"
    now = time.time()
    AFK_USERS[member.id] = {
        "name": member.display_name,
        "reason": cleaned_reason,
        "timestamp": now,
    }
    return f"📴 **{member.display_name}** is now AFK — *{cleaned_reason}*"


async def remove_afk(member: discord.Member) -> dict[str, Any] | None:
    info = AFK_USERS.pop(member.id, None)
    if info is None:
        return None
    return info


async def handle_message(message: discord.Message) -> bool:
    if message.author.bot or not message.guild:
        return False

    if message.id in IGNORED_MESSAGES:
        IGNORED_MESSAGES.discard(message.id)
        return False

    user_id = message.author.id
    if user_id in AFK_USERS:
        info = await remove_afk(message.author)
        if info is None:
            return False

        duration = time.time() - float(info.get("timestamp", time.time()))
        reason = str(info.get("reason", "AFK")).strip() or "AFK"

        embed = discord.Embed(color=0x2ECC71)
        embed.set_author(name="👋 Welcome Back!")
        embed.description = (
            f"**{message.author.display_name}**, you were AFK for **{format_duration(duration)}**"
        )
        embed.add_field(name="AFK Reason", value=reason, inline=True)
        try:
            await message.channel.send(embed=embed)
        except discord.HTTPException:
            pass

    if not message.mentions:
        return False

    notified: set[int] = set()
    for mention in message.mentions:
        if mention.id in notified:
            continue
        if mention.id not in AFK_USERS:
            continue

        info = AFK_USERS.get(mention.id)
        if info is None:
            continue

        duration = time.time() - float(info.get("timestamp", time.time()))
        reason = str(info.get("reason", "AFK")).strip() or "AFK"

        embed = discord.Embed(color=0xF39C12)
        embed.set_author(name="📴 AFK Notice")
        embed.description = f"**{mention.display_name}** is AFK"
        embed.add_field(name="Reason", value=reason, inline=True)
        embed.add_field(name="Duration", value=format_duration(duration), inline=True)

        try:
            await message.channel.send(
                content=f"📴 **{mention.display_name}** is AFK — *{reason}*",
                embed=embed,
            )
        except discord.HTTPException:
            await message.channel.send(f"📴 **{mention.display_name}** is AFK — *{reason}*")

        notified.add(mention.id)

    return False


async def afklist_embed() -> discord.Embed:
    if not AFK_USERS:
        embed = discord.Embed(color=0x95A5A6)
        embed.set_author(name="📴 AFK List")
        embed.description = "No one is AFK right now"
        return embed

    now = time.time()
    lines = []
    for user_id, info in AFK_USERS.items():
        member = discord.utils.get(discord.utils.utcnow().__class__.__mro__ if False else [], "")
        duration = format_duration(now - float(info.get("timestamp", now)))
        reason = str(info.get("reason", "AFK")).strip() or "AFK"
        lines.append(f"• **{info.get('name', 'Unknown')}** — *{reason}* ({duration} ago)")

    embed = discord.Embed(color=0xF39C12)
    embed.set_author(name=f"📴 AFK List ({len(AFK_USERS)} user{'s' if len(AFK_USERS) != 1 else ''})")
    embed.description = "\n".join(lines)
    return embed


async def prefix_afk(message: discord.Message, reason: str = "AFK") -> str:
    cleaned_reason = str(reason).strip() or "AFK"
    if message.author.id in AFK_USERS:
        return "❌ You are already marked as AFK."

    AFK_USERS[message.author.id] = {
        "name": message.author.display_name,
        "reason": cleaned_reason,
        "timestamp": time.time(),
    }
    IGNORED_MESSAGES.add(message.id)
    return f"📴 **{message.author.display_name}** is now AFK — *{cleaned_reason}*"


async def prefix_afklist() -> discord.Embed:
    return await afklist_embed()


async def slash_afk(interaction: discord.Interaction, reason: str = "AFK") -> None:
    if interaction.user.id in AFK_USERS:
        await interaction.response.send_message(
            embed=discord.Embed(
                title="❌ Already AFK",
                description="You are already marked as AFK",
                color=0xE74C3C,
            ),
            ephemeral=True,
        )
        return

    cleaned_reason = str(reason).strip() or "AFK"
    await set_afk(interaction.user, cleaned_reason)
    embed = discord.Embed(color=0xF39C12)
    embed.set_author(name="📴 AFK Set")
    embed.description = f"**{interaction.user.display_name}** is now AFK"
    embed.add_field(name="Reason", value=cleaned_reason, inline=False)
    await interaction.response.send_message(embed=embed)


def setup(bot: Any, tree: app_commands.CommandTree) -> None:
    @tree.command(name="afk", description="Set yourself as AFK")
    @app_commands.describe(reason="Why are you AFK?")
    async def afk_command(interaction: discord.Interaction, reason: str = "AFK"):
        await slash_afk(interaction, reason)

    @tree.command(name="afklist", description="List everyone who is currently AFK")
    async def afklist_command(interaction: discord.Interaction):
        await interaction.response.send_message(embed=await afklist_embed())

    bot.afk_state = AFK_USERS
    return None
