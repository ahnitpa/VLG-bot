import os
import random
import time
import traceback
from datetime import timedelta
from threading import Thread
from typing import Optional

import discord
from discord import app_commands
from discord.ext import tasks
from flask import Flask

import music

# ====================== CONFIG ======================
ROLE_ID = 1535617025744048268
CUSTOM_EMOJI_ID = 1548670697486688358

# ====================== BOT SETUP ======================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Registers music commands (slash commands)
music.setup(bot, tree)

# Global configuration variable trackers
synced_once = False
inactive_config = {}

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


async def handle_prefix_command(message: discord.Message, command: str, args: list) -> None:
    """Every `!v <command>` lands here."""
    guild = message.guild
    author = message.author
    send = message.channel.send

    async def deny_admin():
        await send("❌ **Access Denied:** Missing privileges.")

    async def deny_perm(label: str):
        await send(f"❌ **Access Denied:** You need the `{label}` permission.")

    # --- HELP ---
    if command == "help":
        await send(PREFIX_HELP)
        return

    # --- SET STATUS ---
    if command == "setstatus":
        if not message_is_authorized(message):
            return await deny_admin()
        if not args:
            return await send("❌ **Usage:** `!v setstatus <text>`")
        status_text = " ".join(args)
        await bot.change_presence(activity=discord.Game(name=status_text))
        return await send(f"✅ Status updated to: **Playing {status_text}**")

    # --- SAY ---
    if command == "say":
        if not message_is_authorized(message):
            return await deny_admin()
        if not args:
            return await send("❌ **Usage:** `!v say <text>`")
        return await send(" ".join(args))

    # --- COINFLIP ---
    if command == "coinflip":
        if random.choice(["Heads", "Tails"]) == "Heads":
            return await send("🪙 **Heads!** You lucked out. You survive... for now.")
        try:
            await author.timeout(timedelta(seconds=60), reason="Lost prefix coinflip")
            return await send("🪙 **Tails!** Enjoy your **1-minute timeout**! :D")
        except discord.Forbidden:
            return await send("🪙 **Tails!** You should be timed out, but your permissions protected you.")

    # --- STEAL ---
    if command == "steal":
        target, _ = resolve_member(message, args)
        if target is None:
            return await send("❌ **Usage:** `!v steal @member`")
        if target == author:
            return await send("You tried robbing yourself... How does that feel?")
        if target == bot.user:
            return await send("Firewall completely vaporized your wallet.")
        if random.choice(["success", "fail"]) == "success":
            amount = random.randint(100, 1000)
            return await send(f"**Success!** {author.mention} stole **{amount} coins** from {target.mention}!")
        return await send(f"**CAUGHT STEALING!** {author.mention} tried to rob {target.mention} and went to imaginary jail!")

    # --- RATE ---
    if command == "rate":
        if not args:
            return await send("❌ **Usage:** `!v rate <thing>`")
        return await send(rate_text(" ".join(args)))

    # --- 8BALL ---
    if command == "8ball":
        if not args:
            return await send("❌ **Usage:** `!v 8ball <question>`")
        return await send(
            f"**The Magic 8-Ball**\n**Question:** {' '.join(args)}\n**Answer:** {random.choice(EIGHTBALL_RESPONSES)}")

    # --- SLAP ---
    if command == "slap":
        target, _ = resolve_member(message, args)
        if target is None:
            return await send("❌ **Usage:** `!v slap @member`")
        if target == author:
            return await send(f"{author.mention} tried to slap themselves but missed.")
        return await send(f"WHACK! {author.mention} slaps {target.mention} with {random.choice(SLAP_ITEMS)}!")

    # --- ROAST ---
    if command == "roast":
        target, _ = resolve_member(message, args)
        if target is None:
            return await send("❌ **Usage:** `!v roast @member`")
        if target == author:
            return await send(f"{author.mention}, roasting error: check code e12.")
        if target == bot.user:
            return await send("You can't roast bots.. Not on discord.. (error code 9)")
        return await send(f"{target.mention}, {random.choice(ROASTS)}")

    # --- AVATAR ---
    if command == "avatar":
        target, _ = resolve_member(message, args)
        return await send(embed=build_avatar_embed(target or author))

    # --- WHOIS ---
    if command == "whois":
        target, _ = resolve_member(message, args)
        return await send(embed=build_whois_embed(target or author, author))

    # --- QNA ---
    if command == "qna":
        topic = args[0] if args else None
        return await send(embed=build_qna_embed(topic))

    # ---------------- MODERATION ----------------
    # --- KICK ---
    if command == "kick":
        if not has_mod_perms(message, "kick_members"):
            return await deny_perm("Kick Members")
        member, rest = resolve_member(message, args)
        if member is None:
            return await send("❌ **Usage:** `!v kick @member [reason]`")
        error = hierarchy_error(author, member, guild, "kick")
        if error:
            return await send(error)
        reason = " ".join(rest) or "No reason provided"
        try:
            await member.kick(reason=f"{author} | {reason}")
            return await send(f"{member} has been kicked.\nReason: {reason}")
        except discord.Forbidden:
            return await send("I don't have permission to kick this member. (error code e13)")

    # --- BAN ---
    if command == "ban":
        if not has_mod_perms(message, "ban_members"):
            return await deny_perm("Ban Members")
        member, rest = resolve_member(message, args)
        if member is None:
            return await send("❌ **Usage:** `!v ban @member [reason]`")
        error = hierarchy_error(author, member, guild, "ban")
        if error:
            return await send(error)
        reason = " ".join(rest) or "No reason provided"
        try:
            await member.ban(reason=f"{author} | {reason}")
            return await send(f"{member} has been banned.\nReason: {reason}")
        except discord.Forbidden:
            return await send("I don't have permission to ban this member.")

    # --- TIMEOUT ---
    if command == "timeout":
        if not has_mod_perms(message, "moderate_members"):
            return await deny_perm("Moderate Members")
        member, rest = resolve_member(message, args)
        if member is None or not rest or not rest[0].isdigit():
            return await send("❌ **Usage:** `!v timeout @member <minutes> [reason]`")
        minutes = int(rest[0])
        if not 1 <= minutes <= 40320:
            return await send("❌ Minutes must be between 1 and 40320.")
        error = hierarchy_error(author, member, guild, "timeout")
        if error:
            return await send(error)
        reason = " ".join(rest[1:]) or "No reason provided"
        try:
            await member.timeout(timedelta(minutes=minutes), reason=f"{author} | {reason}")
            return await send(f"{member} has been timed out for {minutes} minutes.\nReason: {reason}")
        except discord.Forbidden:
            return await send("I don't have permission to timeout this member.")

    # --- REMOVE TIMEOUT ---
    if command == "removetimeout":
        if not has_mod_perms(message, "moderate_members"):
            return await deny_perm("Moderate Members")
        member, _ = resolve_member(message, args)
        if member is None:
            return await send("❌ **Usage:** `!v removetimeout @member`")
        try:
            await member.timeout(None)
            return await send(f"Timeout removed from {member}.")
        except discord.Forbidden:
            return await send("I don't have permission to remove the timeout.")

    # --- ADD ROLE / REMOVE ROLE ---
    if command in ("addrole", "removerole"):
        if not has_mod_perms(message, "manage_roles"):
            return await deny_perm("Manage Roles")
        member, rest = resolve_member(message, args)
        role = resolve_role(message, rest[0]) if rest else None
        if member is None or role is None:
            return await send(f"❌ **Usage:** `!v {command} @member @role`")
        if role >= guild.me.top_role:
            return await send("That role is higher than my highest role.")
        adding = command == "addrole"
        if role >= author.top_role and not is_privileged_user(author, guild):
            word = "give" if adding else "remove"
            return await send(f"You can't {word} a role equal to or higher than your own.")
        try:
            if adding:
                if role in member.roles:
                    return await send(f"{member} already has the {role.name} role.")
                await member.add_roles(role, reason=f"Given by {author}")
                return await send(f"Gave {role.name} to {member}.")
            if role not in member.roles:
                return await send(f"{member} doesn't have the {role.name} role.")
            await member.remove_roles(role, reason=f"Removed by {author}")
            return await send(f"Removed {role.name} from {member}.")
        except discord.Forbidden:
            return await send("I don't have permission to manage that role.")

    # ---------------- CHANNEL UTILITIES ----------------
    # --- CREATE CATEGORY ---
    if command == "createcategory":
        if not message_is_authorized(message):
            return await deny_admin()
        if not args:
            return await send("❌ **Usage:** `!v createcategory <name>`")
        try:
            category = await guild.create_category(name=" ".join(args))
            return await send(f"📁 Successfully created category: **{category.name}**")
        except discord.Forbidden:
            return await send("❌ Error: I do not have permission to manage channels.")
        except Exception as e:
            return await send(f"❌ Failed to create category: `{e}`")

    # --- CREATE CHANNEL / CREATE VOICE ---
    if command in ("createchannel", "createvoice"):
        if not message_is_authorized(message):
            return await deny_admin()
        if not args:
            return await send(f"❌ **Usage:** `!v {command} <name> [category_id]`")

        # An optional trailing number is treated as the category ID
        category = None
        name_parts = list(args)
        if len(name_parts) > 1 and name_parts[-1].isdigit():
            maybe_category = guild.get_channel(int(name_parts[-1]))
            if isinstance(maybe_category, discord.CategoryChannel):
                category = maybe_category
                name_parts = name_parts[:-1]
        name = " ".join(name_parts)

        try:
            location_text = f" inside **{category.name}**" if category else ""
            if command == "createchannel":
                channel = await guild.create_text_channel(name=name.lower().replace(" ", "-"), category=category)
                return await send(f"💬 Successfully created text channel: {channel.mention}{location_text}")
            voice_channel = await guild.create_voice_channel(name=name, category=category)
            return await send(f"🔊 Successfully created voice channel: **{voice_channel.name}**{location_text}")
        except discord.Forbidden:
            return await send("❌ Error: I do not have permission to manage channels.")
        except Exception as e:
            return await send(f"❌ Failed to create channel: `{e}`")

    # --- MOVE CHANNEL ---
    if command == "movechannel":
        if not message_is_authorized(message):
            return await deny_admin()
        target = resolve_channel(message, args[0]) if args else None
        direction = args[1].lower() if len(args) > 1 else ""
        if target is None or direction not in ("up", "down"):
            return await send("❌ **Usage:** `!v movechannel <#channel or channel/category ID> <up|down>`")
        try:
            change = -1 if direction == "up" else 1
            await target.edit(position=max(0, target.position + change))
            return await send(f"✅ Successfully moved **{target.name}** {direction}!")
        except discord.Forbidden:
            return await send("❌ Error: I don't have permission to manage this channel. "
                              "Make sure my bot role is high enough in the server settings!")
        except Exception as e:
            return await send(f"❌ Failed to move channel: `{e}`")

    # Unknown command: stay quiet so normal chat starting with "!v " isn't spammed


# ====================== INACTIVITY TRACKING TASK ======================
@tasks.loop(minutes=1)
async def check_inactivity_timers():
    """Loops every 60 seconds to monitor server playback inactivity."""
    for guild_id, info in list(inactive_config.items()):
        guild = bot.get_guild(guild_id)
        if not guild:
            continue

        vc = guild.voice_client
        player = music.players.get(guild_id) if hasattr(music, "players") else None

        is_user_active = False

        if vc and vc.channel:
            active_listeners = [m for m in vc.channel.members if not m.bot]
            if (vc.is_playing() or vc.is_paused()) and len(active_listeners) > 0:
                is_user_active = True

        if player and (player.current or player.queue):
            if getattr(player, "auto_paused", False):
                is_user_active = False
            elif player.current:
                is_user_active = True

        if is_user_active:
            info["idle_since"] = None
        else:
            if info["idle_since"] is None:
                info["idle_since"] = time.time()
            elif time.time() - info["idle_since"] >= 300:
                target_channel = guild.get_channel(info["channel_id"])
                if target_channel and (vc is None or vc.channel != target_channel):
                    try:
                        if vc is None:
                            await target_channel.connect()
                        else:
                            await vc.move_to(target_channel)
                        print(f"💤 Uptime Connection: Auto-joined idle channel in server {guild.name}")
                    except Exception as e:
                        print(f"Could not complete auto-join sequence: {e}")
                    info["idle_since"] = None


# ====================== EVENTS ======================
@bot.event
async def on_ready():
    global synced_once
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print("Registered slash commands:", sorted(c.name for c in tree.get_commands()))

    if not check_inactivity_timers.is_running():
        check_inactivity_timers.start()
        print("⏰ Background inactivity tracking routine initialized.")

    if not synced_once:
        synced_once = True
        try:
            print("🔄 Syncing slash commands globally...")
            synced = await tree.sync()
            print(f"✅ Success! Synced {len(synced)} commands globally.")
        except Exception:
            traceback.print_exc()


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    is_dev = message.author.id in TRUSTED_DEV_IDS
    is_owner = message.author.id == message.guild.owner_id
    content_lower = message.content.lower()

    # !setup: owner/dev initializes the bot and refreshes slash commands
    if content_lower == "!setup":
        if not (is_dev or is_owner):
            await message.channel.send(
                "❌ **Access Denied:** Only the Server Owner or an authorized developer can initialize the bot.")
            return

        status = await message.channel.send("⚙️ *Initializing configuration and syncing slash commands globally...*")
        try:
            synced = await tree.sync()
            embed = discord.Embed(
                title="✅ Setup Successfully Completed!",
                description=(
                    f"Thank you for activating me on **{message.guild.name}**!\n\n"
                    f"📦 **{len(synced)} Slash Commands Registered!**\n"
                    "Type `/` to see slash commands, or use `!v help` for prefix commands."
                ),
                color=discord.Color.green()
            )
            await status.delete()
            await message.channel.send(embed=embed)
        except Exception as e:
            await status.edit(content=f"❌ **Setup Failed:** `{e}`")
        return

    # !forcesync: owner/dev manually refreshes slash commands
    if content_lower == "!forcesync":
        if not (is_dev or is_owner):
            await message.channel.send(
                "❌ **Access Denied:** Only the Server Owner or an authorized developer can force an update.")
            return

        status = await message.channel.send("🔄 *Manually broadcasting and refreshing command layout strings globally...*")
        try:
            synced = await tree.sync()
            await status.edit(
                content=f"**Force-Sync Complete!** `{len(synced)}` global app slash commands refreshed everywhere.")
        except Exception as e:
            await status.edit(content=f"❌ **Force-Sync Failed:** `{e}`")
        return

    # !serverlist: developers only
    if content_lower == "!serverlist":
        if not is_dev:
            await message.channel.send("❌ **Access Denied:** Developer eyes only.")
            return

        sorted_guilds = sorted(bot.guilds, key=lambda g: g.member_count or 0, reverse=True)
        report = "**Bot Server Presence List (Largest to Smallest):**\n\n"
        for index, guild in enumerate(sorted_guilds, start=1):
            report += f"`{index}.` **{guild.name}** | ID: `{guild.id}` | 👥 Members: `{guild.member_count}`\n"
            if len(report) > 1800:
                report += "...and more servers."
                break

        await message.channel.send(report)
        return

    # !inactive <voice_channel_id>: 5-minute automated inactivity fallback channel
    if content_lower.startswith("!inactive"):
        if not (is_dev or is_owner):
            await message.channel.send("❌ **Access Denied:** Server Owner or Devs only.")
            return

        parts = message.content.split()
        if len(parts) < 2:
            await message.channel.send("❌ **Usage:** `!inactive <voice_channel_id>`")
            return

        try:
            channel_id = int(parts[1])
            vc_channel = bot.get_channel(channel_id) or await bot.fetch_channel(channel_id)

            if not isinstance(vc_channel, discord.VoiceChannel):
                await message.channel.send(
                    "❌ **Error:** That ID belongs to a text or category channel. "
                    "Please supply a valid Voice Channel ID.")
                return

            inactive_config[message.guild.id] = {"channel_id": vc_channel.id, "idle_since": None}
            await message.channel.send(
                f"**Inactive Channel activated**, I will automatically join **{vc_channel.name}**.")

        except ValueError:
            await message.channel.send("❌ **Error:** The voice channel ID must be a valid number.")
        except discord.NotFound:
            await message.channel.send("❌ **Error:** Could not locate that voice channel ID. Is it hidden from me?")
        except Exception as e:
            await message.channel.send(f"❌ **Failed to map channel:** `{e}`")
        return

    # ============================================================
    # THE !V PREFIX COMMANDS
    # ============================================================
    if content_lower.startswith("!v "):
        parts = message.content.split()
        if len(parts) >= 2:
            try:
                await handle_prefix_command(message, parts[1].lower(), parts[2:])
            except Exception as e:
                traceback.print_exc()
                try:
                    await message.channel.send(f"Something went wrong: `{str(e)[:300]}`")
                except discord.HTTPException:
                    pass
        return

    # Reply ONLY when the bot is explicitly @mentioned
    if bot.user in message.mentions and not message.mention_everyone:
        if f"<@{bot.user.id}>" in message.content or f"<@!{bot.user.id}>" in message.content:
            try:
                await message.reply("Hi")
            except discord.HTTPException:
                pass
            return

    # React to the word "vlg"
    if "vlg" in content_lower:
        try:
            emoji = bot.get_emoji(CUSTOM_EMOJI_ID)
            await message.add_reaction(emoji if emoji else "❤️")
        except discord.HTTPException:
            pass


# ====================== ADVANCED LOGGING MODULE ======================
@bot.event
async def on_guild_channel_delete(channel: discord.abc.GuildChannel):
    """Logs unusual activity like text, voice, or category channels being deleted."""
    log_channel = discord.utils.get(channel.guild.text_channels, name="bot-logs")
    if not log_channel:
        return

    # Don't log if the logging channel itself is being deleted
    if channel.name == "bot-logs":
        return

    embed = discord.Embed(
        title="Unusual Activity: Channel Deleted",
        description=f"The channel/category **{channel.name}** (Type: `{channel.type}`) was deleted from the server.",
        color=discord.Color.dark_red()
    )
    embed.add_field(name="Channel ID", value=f"`{channel.id}`", inline=True)

    try:
        await log_channel.send(embed=embed)
    except discord.HTTPException:
        pass


# ====================== SLASH ERROR HANDLER ======================
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = f"Slow down! Try again in **{error.retry_after:.1f}** seconds. (error code 4)"
    elif isinstance(error, app_commands.MissingPermissions):
        needed = ", ".join(p.replace("_", " ").title() for p in error.missing_permissions)
        msg = f"**Access Denied!** You need these permissions: `{needed}`. (error code 6)"
    elif isinstance(error, app_commands.CheckFailure):
        if interaction.response.is_done():
            return
        msg = "You can't use this command."
    else:
        original = getattr(error, "original", error)
        traceback.print_exception(type(original), original, original.__traceback__)
        msg = f"Something went wrong: `{str(original)[:300]}`"

    try:
        if interaction.response.is_done():
            await interaction.followup.send(msg, ephemeral=True)
        else:
            await interaction.response.send_message(msg, ephemeral=True)
    except discord.HTTPException:
        pass


# ====================== SLASH COMMANDS ======================

@tree.command(name="setstatus", description="Change the bot's playing status")
@app_commands.describe(text="The text you want the bot to display")
@is_authorized()
async def setstatus(interaction: discord.Interaction, text: str):
    await bot.change_presence(activity=discord.Game(name=text))
    await interaction.response.send_message(
        f"Status successfully updated to: **Playing {text}**",
        ephemeral=True
    )


@tree.command(name="say", description="Make the bot repeat a message")
@app_commands.describe(message="The text you want the bot to say")
@is_authorized()
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Sending message...", ephemeral=True)
    await interaction.channel.send(message)


@tree.command(name="coinflip", description="Flip a coin. Heads you win, Tails you get timed out!")
async def coinflip(interaction: discord.Interaction):
    if random.choice(["Heads", "Tails"]) == "Heads":
        await interaction.response.send_message("🪙 **Heads!** You lucked out. You survive... for now.")
    else:
        try:
            await interaction.user.timeout(timedelta(seconds=60), reason="Lost the coinflip")
            await interaction.response.send_message("🪙 **Tails!** Enjoy your **1-minute timeout**! :D")
        except discord.Forbidden:
            await interaction.response.send_message(
                "🪙 **Tails!** You should be timed out, but your permissions protected you. (error code 7)"
            )


@tree.command(name="steal", description="Attempt to steal imaginary coins!")
@app_commands.describe(target="The server member you want to rob")
async def steal(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message("You tried robbing yourself... (error code 8)", ephemeral=True)
        return
    if target == bot.user:
        await interaction.response.send_message(
            "Firewall completely vaporized your wallet. (error code *e11*)", ephemeral=True)
        return

    if random.choice(["success", "fail"]) == "success":
        amount = random.randint(100, 1000)
        await interaction.response.send_message(
            f"**Success!** {interaction.user.mention} stole **{amount} coins** from {target.mention}!"
        )
    else:
        await interaction.response.send_message(
            f"**CAUGHT STEALING!** {interaction.user.mention} tried to rob {target.mention} and went to imaginary jail!"
        )


@tree.command(name="rate", description="Have the bot judge and rate anything out of 10!")
@app_commands.describe(thing="The object, person, or idea you want rated")
async def rate(interaction: discord.Interaction, thing: str):
    await interaction.response.send_message(rate_text(thing))


@tree.command(name="8ball", description="Ask the Magic 8-Ball a question")
@app_commands.describe(question="The question you want answered")
async def eightball(interaction: discord.Interaction, question: str):
    await interaction.response.send_message(
        f"**The Magic 8-Ball**\n**Question:** {question}\n**Answer:** {random.choice(EIGHTBALL_RESPONSES)}"
    )


@tree.command(name="slap", description="Slap a server member with a random object!")
@app_commands.describe(target="The server member you want to slap")
async def slap(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message(f"{interaction.user.mention} tried to slap themselves but missed.")
        return

    await interaction.response.send_message(
        f"WHACK! {interaction.user.mention} slaps {target.mention} with {random.choice(SLAP_ITEMS)}!"
    )


@tree.command(name="roast", description="Hit a fellow server member with a funny roast!")
@app_commands.describe(target="The server member you want to roast")
async def roast(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message(
            f"{interaction.user.mention}, roasting error: check code e12.", ephemeral=True)
        return
    if target == bot.user:
        await interaction.response.send_message(
            "You can't roast bots.. Not on discord.. (error code 9)", ephemeral=True)
        return

    await interaction.response.send_message(f"{target.mention}, {random.choice(ROASTS)}")


@tree.command(name="avatar", description="Fetch a user's profile picture")
@app_commands.describe(target="The server member (leave empty for yourself)")
async def avatar(interaction: discord.Interaction, target: Optional[discord.Member] = None):
    await interaction.response.send_message(embed=build_avatar_embed(target or interaction.user))


@tree.command(name="whois", description="View detailed profile information")
@app_commands.describe(target="The server member (leave empty for yourself)")
async def whois(interaction: discord.Interaction, target: Optional[discord.Member] = None):
    await interaction.response.send_message(
        embed=build_whois_embed(target or interaction.user, interaction.user))


@tree.command(name="qna", description="Get a random silly question about anything")
@app_commands.describe(topic="Optional topic: food, gaming or life (leave empty for random)")
async def qna(interaction: discord.Interaction, topic: Optional[str] = None):
    await interaction.response.send_message(embed=build_qna_embed(topic))


# ====================== SLASH MODERATION COMMANDS ======================
# Devs and the server owner always pass. Administrators pass automatically.
# Everyone else needs the matching Discord permission. Devs and the owner also
# skip the "equal or higher role" check (the bot's own role must still be high enough).

@tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="The member to kick", reason="Reason for the kick")
@dev_or_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    error = hierarchy_error(interaction.user, member, interaction.guild, "kick")
    if error:
        return await interaction.response.send_message(error, ephemeral=True)

    try:
        await member.kick(reason=f"{interaction.user} | {reason}")
        await interaction.response.send_message(f"{member} has been kicked.\nReason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message(
            "I don't have permission to kick this member. (error code e13)", ephemeral=True)


@tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(
    member="The member to ban",
    reason="Reason for the ban",
    delete_days="Delete messages from last X days"
)
@dev_or_permissions(ban_members=True)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
    delete_days: app_commands.Range[int, 0, 7] = 0
):
    error = hierarchy_error(interaction.user, member, interaction.guild, "ban")
    if error:
        return await interaction.response.send_message(error, ephemeral=True)

    try:
        await member.ban(reason=f"{interaction.user} | {reason}", delete_message_seconds=delete_days * 86400)
        await interaction.response.send_message(f"{member} has been banned.\nReason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to ban this member.", ephemeral=True)


@tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(
    member="The member to timeout",
    minutes="Minutes to last",
    reason="Reason for the timeout"
)
@dev_or_permissions(moderate_members=True)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: app_commands.Range[int, 1, 40320],
    reason: str = "No reason provided"
):
    error = hierarchy_error(interaction.user, member, interaction.guild, "timeout")
    if error:
        return await interaction.response.send_message(error, ephemeral=True)

    try:
        await member.timeout(timedelta(minutes=minutes), reason=f"{interaction.user} | {reason}")
        await interaction.response.send_message(
            f"{member} has been timed out for {minutes} minutes.\nReason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to timeout this member.", ephemeral=True)


@tree.command(name="removetimeout", description="Remove timeout from a member")
@app_commands.describe(member="The member to remove timeout from")
@dev_or_permissions(moderate_members=True)
async def removetimeout(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None)
        await interaction.response.send_message(f"Timeout removed from {member}.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to remove the timeout.", ephemeral=True)


@tree.command(name="addrole", description="Give a role to a member")
@app_commands.describe(member="The member", role="The role to give")
@dev_or_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("That role is higher than my highest role.", ephemeral=True)
    if role >= interaction.user.top_role and not is_privileged_user(interaction.user, interaction.guild):
        return await interaction.response.send_message(
            "You can't give a role equal to or higher than your own.", ephemeral=True)
    if role in member.roles:
        return await interaction.response.send_message(
            f"{member} already has the {role.name} role.", ephemeral=True)

    try:
        await member.add_roles(role, reason=f"Given by {interaction.user}")
        await interaction.response.send_message(f"Gave {role.name} to {member}.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to manage that role.", ephemeral=True)


@tree.command(name="removerole", description="Remove a role from a member")
@app_commands.describe(member="The member", role="The role to remove")
@dev_or_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("That role is higher than my highest role.", ephemeral=True)
    if role >= interaction.user.top_role and not is_privileged_user(interaction.user, interaction.guild):
        return await interaction.response.send_message(
            "You can't remove a role equal to or higher than your own.", ephemeral=True)
    if role not in member.roles:
        return await interaction.response.send_message(
            f"{member} doesn't have the {role.name} role.", ephemeral=True)

    try:
        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
        await interaction.response.send_message(f"Removed {role.name} from {member}.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to manage that role.", ephemeral=True)


# ====================== SLASH UTILITY CREATION COMMANDS ======================

@tree.command(name="createcategory", description="Create a new category channel in the server.")
@app_commands.describe(name="The name of the new category")
@is_authorized()
async def createcategory(interaction: discord.Interaction, name: str):
    await interaction.response.defer(ephemeral=True)
    try:
        category = await interaction.guild.create_category(name=name)
        await interaction.followup.send(f"📁 Successfully created category: **{category.name}**", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Error: I do not have permission to manage channels.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create category: `{e}`", ephemeral=True)


@tree.command(name="createchannel", description="Create a new text channel inside an optional category.")
@app_commands.describe(name="The name of the text channel", category="The category folder to place this channel into")
@is_authorized()
async def createchannel(
    interaction: discord.Interaction,
    name: str,
    category: Optional[discord.CategoryChannel] = None
):
    await interaction.response.defer(ephemeral=True)
    try:
        formatted_name = name.lower().replace(" ", "-")
        channel = await interaction.guild.create_text_channel(name=formatted_name, category=category)

        location_text = f" inside **{category.name}**" if category else ""
        await interaction.followup.send(
            f"💬 Successfully created text channel: {channel.mention}{location_text}", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Error: I do not have permission to manage channels.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create text channel: `{e}`", ephemeral=True)


@tree.command(name="createvoice", description="Create a new voice channel inside an optional category.")
@app_commands.describe(name="The name of the voice channel", category="The category folder to place this voice channel into")
@is_authorized()
async def createvoice(
    interaction: discord.Interaction,
    name: str,
    category: Optional[discord.CategoryChannel] = None
):
    await interaction.response.defer(ephemeral=True)
    try:
        voice_channel = await interaction.guild.create_voice_channel(name=name, category=category)

        location_text = f" inside **{category.name}**" if category else ""
        await interaction.followup.send(
            f"🔊 Successfully created voice channel: **{voice_channel.name}**{location_text}", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send("❌ Error: I do not have permission to manage channels.", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to create voice channel: `{e}`", ephemeral=True)


@tree.command(name="movechannel", description="Move a channel, voice channel, or category up or down.")
@app_commands.describe(target="The channel, voice channel, or category folder you want to move", direction="Choose whether to nudge it Up or Down")
@app_commands.choices(direction=[
    app_commands.Choice(name="🔼 Move Up", value="up"),
    app_commands.Choice(name="🔽 Move Down", value="down"),
])
@is_authorized()
async def movechannel(
    interaction: discord.Interaction,
    target: discord.abc.GuildChannel,
    direction: app_commands.Choice[str]
):
    await interaction.response.defer(ephemeral=True)

    try:
        # Moving 'up' lowers the position number (closer to 0); 'down' raises it
        change = -1 if direction.value == "up" else 1
        await target.edit(position=max(0, target.position + change))

        await interaction.followup.send(
            f"✅ Successfully moved **{target.name}** {direction.name.lower()}!",
            ephemeral=True
        )

    except discord.Forbidden:
        await interaction.followup.send(
            "❌ Error: I don't have permission to manage this channel. "
            "Make sure my bot role is high enough in the server settings!",
            ephemeral=True
        )
    except Exception as e:
        await interaction.followup.send(f"❌ Failed to move channel: `{e}`", ephemeral=True)


# ====================== KEEP ALIVE ======================
app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is online and active!"


def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)


def keep_alive():
    Thread(target=run_web_server, daemon=True).start()


# ====================== START ======================
if __name__ == "__main__":
    token = os.environ.get("TOKEN")
    if not token:
        raise SystemExit("TOKEN environment variable is not set.")
    keep_alive()
    bot.run(token)
