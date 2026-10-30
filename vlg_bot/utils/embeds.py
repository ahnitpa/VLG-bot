"""Shared embeds for the VLG bot."""

import discord


def build_qna_embed(topic: str | None = None) -> discord.Embed:
    import random
    from vlg_bot.utils.permissions import GENERAL_QUESTIONS, TOPIC_QUESTIONS

    if topic and topic.lower() in TOPIC_QUESTIONS:
        description = random.choice(TOPIC_QUESTIONS[topic.lower()])
    else:
        description = random.choice(GENERAL_QUESTIONS)
    embed = discord.Embed(title="Random Silly Question", description=description, color=discord.Color.random())
    if topic:
        embed.set_footer(text=f"Topic: {topic}")
    return embed


def build_avatar_embed(target: discord.Member) -> discord.Embed:
    embed = discord.Embed(title=f"Avatar of {target.display_name}", color=target.color if target.color.value else discord.Color.blue())
    if target.avatar:
        embed.set_image(url=target.avatar.url)
        embed.description = f"[Open original image]({target.avatar.url})"
    else:
        embed.set_image(url=target.default_avatar.url)
        embed.description = "This user is using the default Discord avatar. (error code 5)"
    return embed


def build_whois_embed(target: discord.Member, requester: discord.Member) -> discord.Embed:
    account_created = target.created_at.strftime("%d %b %Y")
    server_joined = target.joined_at.strftime("%d %b %Y") if target.joined_at else "Unknown"
    roles = [role.mention for role in target.roles if role.name != "@everyone"]
    roles_display = " ".join(roles[:15]) if roles else "No special roles"
    if len(roles) > 15:
        roles_display += f" (+{len(roles) - 15} more)"
    status_tags = []
    if target.guild_permissions.administrator:
        status_tags.append("Administrator")
    elif target.guild_permissions.manage_guild:
        status_tags.append("Server Manager")
    elif target.guild_permissions.kick_members or target.guild_permissions.ban_members:
        status_tags.append("Moderator")
    if target.bot:
        status_tags.append("Bot Account")
    status_display = ", ".join(status_tags) if status_tags else "Regular Member"
    embed = discord.Embed(title=f"User Info - {target}", color=target.color if target.color.value else discord.Color.blue())
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Display Name", value=target.mention, inline=True)
    embed.add_field(name="Account ID", value=f"{target.id}", inline=True)
    embed.add_field(name="Status", value=status_display, inline=True)
    embed.add_field(name="Created On", value=account_created, inline=True)
    embed.add_field(name="Joined Server", value=server_joined, inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_display, inline=False)
    embed.set_footer(text=f"Requested by {requester.display_name}")
    return embed


__all__ = ["build_qna_embed", "build_avatar_embed", "build_whois_embed"]
