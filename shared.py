"""
shared.py - permission helpers, shared fun content, embed builders and prefix-parsing helpers
used by bot.py (moved out of it to keep every file short).
"""
import random
from typing import Optional

import discord
from discord import app_commands

# ====================== MASTER DEV LIST ======================
TRUSTED_DEV_IDS = [
    1151184036681752576,  # pepper
    1373999565312888842,  # ahnitpa
    1325908309534048318,  # luchoo (Lightsout)
]


# ====================== PERMISSION HELPERS ======================
def is_privileged_user(user: discord.abc.User, guild: Optional[discord.Guild]) -> bool:
    """Trusted developers and the server owner (they also skip role-hierarchy checks)."""
    if user.id in TRUSTED_DEV_IDS:
        return True
    return bool(guild and user.id == guild.owner_id)


def is_authorized_user(user: discord.Member, guild: Optional[discord.Guild]) -> bool:
    """Developer, owner, or any administrator."""
    if is_privileged_user(user, guild):
        return True
    return bool(guild and user.guild_permissions.administrator)


def message_is_authorized(message: discord.Message) -> bool:
    return is_authorized_user(message.author, message.guild)


def has_mod_perms(message: discord.Message, perm_name: str) -> bool:
    """Dev/owner/admin always pass; everyone else needs the named permission."""
    if is_authorized_user(message.author, message.guild):
        return True
    return bool(getattr(message.author.guild_permissions, perm_name, False))


def hierarchy_error(actor: discord.Member, target: discord.Member,
                    guild: discord.Guild, verb: str) -> Optional[str]:
    """Shared safety checks for kick / ban / timeout (slash and prefix)."""
    if target == actor:
        return f"You can't {verb} yourself."
    if target == guild.owner:
        return f"You can't {verb} the server owner."
    if target.top_role >= actor.top_role and not is_privileged_user(actor, guild):
        return f"You can't {verb} someone with equal or higher role than you."
    return None


# ----- slash-command check decorators -----
def is_authorized():
    """Devs, the server owner, or any administrator."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if is_authorized_user(interaction.user, interaction.guild):
            return True

        await interaction.response.send_message(
            "❌ **Access Denied:** Only the Server Owner, an Administrator, or an authorized developer can use this command.",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)


def dev_or_permissions(**perms: bool):
    """Like has_permissions(), but trusted devs and the server owner always pass.
    Administrators pass automatically because Discord grants them every permission."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if is_privileged_user(interaction.user, interaction.guild):
            return True

        permissions = interaction.permissions
        if permissions.administrator:
            return True

        missing = [name for name, value in perms.items() if getattr(permissions, name) != value]
        if not missing:
            return True

        # Handled by on_app_command_error ("Access Denied! You need these permissions...")
        raise app_commands.MissingPermissions(missing)
    return app_commands.check(predicate)


# ====================== SHARED CONTENT ======================
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
    return (f"**Judgement Time!**\n**Thing:** {thing}\n**Rating:** `{score}/10`\n"
            f"*\"{rate_comment(score)}\"*")


def pick_question(topic: Optional[str]) -> str:
    if topic and topic.lower() in TOPIC_QUESTIONS:
        return random.choice(TOPIC_QUESTIONS[topic.lower()])
    return random.choice(GENERAL_QUESTIONS)


def build_qna_embed(topic: Optional[str]) -> discord.Embed:
    embed = discord.Embed(title="Random Silly Question", description=pick_question(topic),
                          color=discord.Color.random())
    if topic:
        embed.set_footer(text=f"Topic: {topic}")
    return embed


def build_avatar_embed(target: discord.Member) -> discord.Embed:
    embed = discord.Embed(
        title=f"Avatar of {target.display_name}",
        color=target.color if target.color.value else discord.Color.blue()
    )
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

    embed = discord.Embed(
        title=f"User Info - {target}",
        color=target.color if target.color.value else discord.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Display Name", value=target.mention, inline=True)
    embed.add_field(name="Account ID", value=f"{target.id}", inline=True)
    embed.add_field(name="Status", value=status_display, inline=True)
    embed.add_field(name="Created On", value=account_created, inline=True)
    embed.add_field(name="Joined Server", value=server_joined, inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_display, inline=False)
    embed.set_footer(text=f"Requested by {requester.display_name}")
    return embed


# ====================== PREFIX PARSING HELPERS ======================
def _token_id(token: str, chars: str) -> Optional[int]:
    digits = token.strip(chars)
    return int(digits) if digits.isdigit() else None


def resolve_member(message: discord.Message, args: list):
    """Reads a member (@mention or ID) from the first argument. Returns (member, remaining_args)."""
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


PREFIX_HELP = (
    "**📖 `!v` commands**\n"
    "**Fun:** `coinflip`, `steal @member`, `rate <thing>`, `8ball <question>`, `slap @member`, "
    "`roast @member`, `qna [food|gaming|life]`\n"
    "**Info:** `avatar [@member]`, `whois [@member]`\n"
    "**Moderation:** `kick @member [reason]`, `ban @member [reason]`, "
    "`timeout @member <minutes> [reason]`, `removetimeout @member`, "
    "`addrole @member @role`, `removerole @member @role`\n"
    "**Admin:** `setstatus <text>`, `say <text>`, `createcategory <name>`, "
    "`createchannel <name> [category_id]`, `createvoice <name> [category_id]`, "
    "`movechannel <#channel or id> <up|down>`\n"
    "Music uses slash commands (`/play`, `/queue`, ...)."
)
