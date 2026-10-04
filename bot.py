# VLG (BETA)

# This code was Clarified by Claude.
# This code has notes on every command in this code, so you dont get lost in all of the lines of code. (‾◡◝)
import random
from datetime import timedelta
from threading import Thread
import yt_dlp
import discord
from discord import app_commands
from flask import Flask

# ====================== CONFIG ======================
TOKEN = "MTU0ODY1MjUwNDY1NTMzMTQwOQ.GqD8h1.6W1LyIbWtzjDY_wZ7Fh2nvyBnQ1qp5qp4Cdn7Q"          # Put your real discord token here (✿◡‿◡)
SERVER_ID = 1478447010284568781
ROLE_ID = 1535617025744048268
CUSTOM_EMOJI_ID = 1548670697486688358

MY_SERVER = discord.Object(id=SERVER_ID)

# ====================== BOT SETUP ======================
intents = discord.Intents.default()
intents.message_content = True          # needed for on_message
intents.members = True                  # needed for roles, timeouts, whois, etc.
intents.guilds = True
intents.voice_states = True				# voice channel join perms

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# ====================== OWNER CHECK ======================
def is_server_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        if interaction.user.id == interaction.guild.owner_id:
            return True
        await interaction.response.send_message(
            "Only the server owner can use this command. (error code #1)",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

# ====================== EVENTS ======================
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user or message.guild is None:
        return

    # Force sync command (owner only)
    if message.content.lower() == "!forcesync":
        if message.author.id != message.guild.owner_id:
            await message.channel.send("**Access Denied:** Server Owner only.")
            return

        status = await message.channel.send("🔄 Forcing command sync...")
        tree.copy_global_to(guild=MY_SERVER)
        await tree.sync(guild=MY_SERVER)
        await status.edit(content="**Force-Sync Complete!** Commands refreshed.")
        return

    # Reply ONLY when the bot is explicitly @mentioned (not when someone just replies)
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        if f"<@{bot.user.id}>" in message.content or f"<@!{bot.user.id}>" in message.content:
            try:
                await message.reply("Hi")
                return
            except discord.Forbidden:
                pass

    # Random interrupter (10% chance)
    if random.random() < 0.10:
        funny_responses = [
            "Yeah",
            "silly.",
            "Sir, this is a Wendy's.",
            "what",
            "funny one.",
            "why?"
        ]
        try:
            await message.reply(random.choice(funny_responses))
        except discord.Forbidden:
            pass

    # React to the word "gamble"
    if "gamble" in message.content.lower():
        try:
            emoji = bot.get_emoji(CUSTOM_EMOJI_ID)
            if emoji:
                await message.add_reaction(emoji)
            else:
                await message.add_reaction("❤️")
        except discord.Forbidden:
            pass
   
# ====================== SLASH COMMANDS ======================

# SET STATUS COMMAND. FOR SERVER OWNERS ONLY.

@tree.command(name="setstatus", description="Change the bot's playing status")
@app_commands.describe(text="The text you want the bot to display")
@is_server_owner()
async def setstatus(interaction: discord.Interaction, text: str):
    await bot.change_presence(activity=discord.Game(name=text))
    await interaction.response.send_message(
        f"Status successfully updated to: **Playing {text}**",
        ephemeral=True
    )

# /GAMBLE COMMAND 🎰🎰🎰🎰🎰🎰🎰🎰🎰🎰

@tree.command(name="gamble", description="Take a 1-in-5 chance to win a special role!")
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
async def gamble(interaction: discord.Interaction):
    member = interaction.user
    role = interaction.guild.get_role(ROLE_ID)

    if not role:
        await interaction.response.send_message("The target role was not found (error code 3)", ephemeral=True)
        return

    if role in member.roles:
        await interaction.response.send_message("You already have this role! (error code *e10*)", ephemeral=True)
        return

    roll = random.randint(1, 5)
    if roll == 1:
        try:
            await member.add_roles(role)
            await interaction.response.send_message(
                f"**Lucky!** You rolled a {roll}/5 and won the **{role.name}** role!"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "I don't have permission to give that role. Contact bot developer or drag the bot role higher then the target role. (error code 3)",
                ephemeral=True
            )
    else:
        await interaction.response.send_message(
            f"**Unlucky!** You rolled a {roll}/5. Try again next time!",
            ephemeral=True
        )

@gamble.error
async def gamble_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(
            f"Slow down! Try again in **{error.retry_after:.1f}** seconds. (error code 4)",
            ephemeral=True
        )
    else:
        raise error

# /SAY COMMAND; MAKE A BOT REPEAT WHAT YOU WROTE

@tree.command(name="say", description="Make the bot repeat a message")
@app_commands.describe(message="The text you want the bot to say")
@app_commands.checks.has_permissions(administrator=True)
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Sending message...", ephemeral=True)
    await interaction.channel.send(message)

@say.error
async def say_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message(
            "**Access Denied!** You need `Administrator` permissions. (error code 6)",
            ephemeral=True
        )
    else:
        raise error

# SUSPICIOUS COINFLIP

@tree.command(name="coinflip", description="Flip a coin. Heads you win, Tails you get timed out for 1 minute!")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])

    if result == "Heads":
        await interaction.response.send_message("🪙 **Heads!** You lucked out. You survive... for now.")
    else:
        try:
            await interaction.user.timeout(timedelta(seconds=60), reason="Lost the coinflip")
            await interaction.response.send_message(
                "🪙 **Tails!** Enjoy your **1-minute timeout**! :D"
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                "🪙 **Tails!** You should be timed out, but your Administrator permissions protected you. (error code 7)"
            )

# STEAL IMAGINARY COINS THAT DOESN'T EVEN EXIST (LMAO)

@tree.command(name="steal", description="Attempt to steal imaginary coins from a server member!")
@app_commands.describe(target="The server member you want to rob")
async def steal(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message("You tried robbing yourself... (error code 8)", ephemeral=True)
        return
    if target == bot.user:
        await interaction.response.send_message("Firewall completely vaporized your wallet. (error code *e11*)", ephemeral=True)
        return

    if random.choice(["success", "fail"]) == "success":
        amount = random.randint(100, 1000)
        await interaction.response.send_message(
            f"**Success!** {interaction.user.mention} stole **{amount} coins** from {target.mention}!"
        )
    else:
        await interaction.response.send_message(
            f"**CAUGHT STEALING!** {interaction.user.mention} tried to rob {target.mention} and got thrown into imaginary jail!"
        )

# RANDOM RATING (THIS THING RATED THE CODE 6/10 BTW)

@tree.command(name="rate", description="Have the bot judge and rate anything out of 10!")
@app_commands.describe(thing="The object, person, or idea you want rated")
async def rate(interaction: discord.Interaction, thing: str):
    score = random.randint(0, 10)

    if score <= 3:
        comments = ["Absolutely tragic. Delete this.", "This is so bad it almost crashed my servers."]
    elif score <= 7:
        comments = ["It's oki.", "Decent effort."]
    else:
        comments = ["Magnificent! I'm impressed.", "Amazing"]

    await interaction.response.send_message(
        f"**Judgement Time!**\n"
        f"**Thing:** {thing}\n"
        f"**Rating:** `{score}/10`\n"
        f'*"{random.choice(comments)}"*'
    )

# 8BALL. NOTHING REALLY IMPRESSIVE, THE CODE ISNT STOLEN TRUST ME :D

@tree.command(name="8ball", description="Ask the Magic 8-Ball a question")
@app_commands.describe(question="The question you want answered")
async def eightball(interaction: discord.Interaction, question: str):
    responses = [
        "Absolutely yes.",
        "Signs point to yes.",
        "Try again later.",
        "Don't count on it.",
        "Don't do it!"
    ]
    await interaction.response.send_message(
        f"**The Magic 8-Ball**\n"
        f"**Question:** {question}\n"
        f"**Answer:** {random.choice(responses)}"
    )

# SLAP YOUR FRIEND WITH 3 RANDOM OBJECTS. MY FAV IS BROKEN KEYBOARD. LMAO.

@tree.command(name="slap", description="Slap a server member with a random object!")
@app_commands.describe(target="The server member you want to slap")
async def slap(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message(
            f" {interaction.user.mention} tried to slap themselves but missed."
        )
        return

    items = [
        "a giant wet trout",
        "a broken keyboard",
        "a stale baguette",
        "a comically large rubber duck"
    ]
    await interaction.response.send_message(
        f"**WHACK!** {interaction.user.mention} slaps {target.mention} with {random.choice(items)}!"
    )

# /ROAST YOUR GF AND GO DRINK WATER.

@tree.command(name="roast", description="Hit a fellow server member with a funny roast!")
@app_commands.describe(target="The server member you want to roast")
async def roast(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message(
            f" {interaction.user.mention}, roasting error go read the (error code *e12*) in the error guide.",
            ephemeral=True
        )
        return
    if target == bot.user:
        await interaction.response.send_message("You can't roast bots.. Not on discord.. (error code 9)", ephemeral=True)
        return

    roasts = [
        "is the type of person who pushes a door that clearly says 'Pull'.",
        "looks like a person who claps when the airplane lands.",
        "probably types with their two index fingers while looking at the keyboard.",
        "has the emotional stability of an expired carton of milk.",
        "is the human equivalent of a participation trophy.",
        "looks like they remind the teacher to assign homework right before the bell.",
        "probably puts milk in the bowl before the cereal. Absolutely criminal.",
        "is like software update notifications—annoying and always showing up at the worst time."
    ]

    await interaction.response.send_message(
        f" {target.mention}, {random.choice(roasts)}"
    )

# AVATAR SNATCHER. VERY USEFULL TO STEAL ANIME PICS.

@tree.command(name="avatar", description="Fetch a user's profile picture")
@app_commands.describe(target="The server member (leave empty for yourself)")
async def avatar(interaction: discord.Interaction, target: discord.Member = None):
    if target is None:
        target = interaction.user

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

    await interaction.response.send_message(embed=embed)

# GET A DASHBOARD OF A USER. DON'T ABUSE IT ON YOUR GF. JUST SAYING.
# hey... how can abuse it.. by @owo.pepper
# fun fact: you can leave it empty for yourself!


@tree.command(name="whois", description="View detailed profile information")
@app_commands.describe(target="The server member (leave empty for yourself)")
async def whois(interaction: discord.Interaction, target: discord.Member = None):
    if target is None:
        target = interaction.user

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
        title=f"User Info — {target}",
        color=target.color if target.color.value else discord.Color.blue()
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="Display Name", value=target.mention, inline=True)
    embed.add_field(name="Account ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Status", value=status_display, inline=True)
    embed.add_field(name="Created On", value=account_created, inline=True)
    embed.add_field(name="Joined Server", value=server_joined, inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_display, inline=False)
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)

# error handler for checks
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CheckFailure):
        return  # already handled by the check
    print(f"Unexpected error: {error}")

# ====================== MODERATION COMMANDS ======================

@tree.command(name="kick", description="Kick a member from the server")
@app_commands.describe(member="The member to kick", reason="Reason for the kick")
@app_commands.checks.has_permissions(kick_members=True)
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    if member == interaction.user:
        return await interaction.response.send_message("You can't kick yourself.", ephemeral=True)
    if member == interaction.guild.owner:
        return await interaction.response.send_message("You can't kick the server owner.", ephemeral=True)
    if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message("**You can't kick someone with equal or higher role than you.**", ephemeral=True)

    try:
        await member.kick(reason=f"{interaction.user} | {reason}")
        await interaction.response.send_message(f"**{member}** has been kicked.\n**Reason:** {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to kick this member. (error code e13)", ephemeral=True)


@tree.command(name="ban", description="Ban a member from the server")
@app_commands.describe(member="The member to ban", reason="Reason for the ban", delete_days="Delete messages from the last X days (0-7)")
@app_commands.checks.has_permissions(ban_members=True)
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided", delete_days: app_commands.Range[int, 0, 7] = 0):
    if member == interaction.user:
        return await interaction.response.send_message("You can't ban yourself.", ephemeral=True)
    if member == interaction.guild.owner:
        return await interaction.response.send_message("You can't ban the server owner.", ephemeral=True)
    if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message("You can't ban someone with equal or higher role than you. (error code e13)", ephemeral=True)

    try:
        await member.ban(reason=f"{interaction.user} | {reason}", delete_message_days=delete_days)
        await interaction.response.send_message(f"**{member}** has been banned.\n**Reason:** {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to ban this member. (error code #e14)", ephemeral=True)


@tree.command(name="timeout", description="Timeout a member")
@app_commands.describe(
    member="The member to timeout",
    minutes="How many minutes the timeout should last",
    reason="Reason for the timeout"
)
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: app_commands.Range[int, 1, 40320], reason: str = "No reason provided"):
    if member == interaction.user:
        return await interaction.response.send_message("You can't timeout yourself.", ephemeral=True)
    if member == interaction.guild.owner:
        return await interaction.response.send_message("You can't timeout the server owner.", ephemeral=True)
    if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message("You can't timeout someone with equal or higher role than you. (error code e13)", ephemeral=True)

    duration = timedelta(minutes=minutes)
    try:
        await member.timeout(duration, reason=f"{interaction.user} | {reason}")
        await interaction.response.send_message(
            f"**{member}** has been timed out for **{minutes} minutes**.\n**Reason:** {reason}"
        )
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to timeout this member. (error code #e14)", ephemeral=True)


@tree.command(name="removetimeout", description="Remove timeout from a member")
@app_commands.describe(member="The member to remove timeout from")
@app_commands.checks.has_permissions(moderate_members=True)
async def untimeout(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None)
        await interaction.response.send_message(f"Timeout removed from **{member}**.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to remove the timeout. (error code #e14)", ephemeral=True)


@tree.command(name="addrole", description="Give a role to a member")
@app_commands.describe(member="The member", role="The role to give")
@app_commands.checks.has_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("That role is higher than my highest role. (error code #e14)", ephemeral=True)
    if role in member.roles:
        return await interaction.response.send_message(f"**{member}** already has the **{role.name}** role.", ephemeral=True)

    try:
        await member.add_roles(role, reason=f"Given by {interaction.user}")
        await interaction.response.send_message(f"Gave **{role.name}** to **{member}**.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to manage that role. (error code #e14)", ephemeral=True)


@tree.command(name="removerole", description="Remove a role from a member")
@app_commands.describe(member="The member", role="The role to remove")
@app_commands.checks.has_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("That role is higher than my highest role. (error code #e14)", ephemeral=True)
    if role not in member.roles:
        return await interaction.response.send_message(f"**{member}** doesn't have the **{role.name}** role.", ephemeral=True)

    try:
        await member.remove_roles(role, reason=f"Removed by {interaction.user}")
        await interaction.response.send_message(f"Removed **{role.name}** from **{member}**.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to manage that role. (error code #e14)", ephemeral=True)


# ====================== QnA COMMAND ======================

from typing import Optional   # make sure this is at the top with your other imports

@tree.command(name="qna", description="Get a random silly question about anything")
@app_commands.describe(topic="Optional topic (leave empty for completely random)")
async def qna(interaction: discord.Interaction, topic: Optional[str] = None):
    general_questions = [
        "If you could have any superpower but it only worked on Tuesdays, what would it be?",
        "Would you rather fight 100 duck-sized horses or 1 horse-sized duck?",
        "What’s the weirdest thing you’ve ever eaten on purpose?",
        "If animals could talk, which one would be the rudest?",
        "What’s a conspiracy theory you half-believe?",
        "If you had to rename yourself after a food, what would it be?",
        "Would you rather always have to sing instead of talk, or dance instead of walk?",
        "What’s the most useless talent you have?",
        "If your life had a loading screen tip, what would it say?",
        "What’s something that should be illegal but isn’t?",
        "If you could only eat one color of food for the rest of your life, what color?",
        "Would you rather have a pause button or a rewind button for your life?",
        "What’s the dumbest way you’ve ever hurt yourself?",
        "If ghosts were real, what would you do to annoy them?",
        "What’s a hill you’re willing to die on that nobody else cares about?",
    ]

    topic_questions = {
        "food": [
            "What’s a food combination that sounds disgusting but is actually fire?",
            "If you had to eat the same meal every day for a year, what would it be?",
            "Pineapple on pizza: war crime or genius?",
        ],
        "gaming": [
            "What’s the most rage-inducing game you’ve ever played?",
            "If you could live in any game world, which one and why?",
            "What’s a game mechanic that should exist but doesn’t?",
        ],
        "life": [
            "What’s a piece of advice that actually made your life worse?",
            "If you could restart your life at any age, which age would you pick?",
            "What’s something everyone pretends to like but secretly hates?",
        ]
    }
	

    if topic and topic.lower() in topic_questions:
        question = random.choice(topic_questions[topic.lower()])
    else:
        question = random.choice(general_questions)

    embed = discord.Embed(
        title="Random Silly Question",
        description=question,
        color=discord.Color.random()
    )
    if topic:
        embed.set_footer(text=f"Topic: {topic}")
    
    await interaction.response.send_message(embed=embed)
	
    if topic and topic.lower() in topic_questions:
        question = random.choice(topic_questions[topic.lower()])
    else:
        question = random.choice(general_questions)

    embed = discord.Embed(
        title="Random Silly Question",
        description=question,
        color=discord.Color.random()
    )
    if topic:
        embed.set_footer(text=f"Topic: {topic}")
    
    await interaction.response.send_message(embed=embed)

"""
bot/cogs/music.py — Music commands (yt-dlp + FFmpeg, no lavalink needed).
Commands: join, leave, play, pause, resume, stop, skip, queue, revive,
          nowplaying, volume, shuffle, loop (single/queue), remove, clear, radio, favorite,
          playlist (create/delete/add/remove/save/play/list)

Requirements (all pip-installable except FFmpeg):
    pip install discord.py yt-dlp PyNaCl

FFmpeg must be installed on the system:
    - On Wispbyte: Add to startup command or install via apt
    - e.g., apt install ffmpeg OR use a container with FFmpeg
"""

import asyncio
import functools
import math
import os
import random
import traceback
from collections import deque

import discord
import yt_dlp
from discord import app_commands
from discord.abc import Messageable
from discord.ext import commands

from bot.cogs.checks import perms_or_developer
from bot.services.music import (
    classify_ytdl_error,
    extract_info,
    get_ffmpeg_opts,
    get_ytdl_opts,
    is_apple_url,
    is_soundcloud_url,
    is_spotify_url,
    parse_spotify_url,
    parse_apple_url,
    search_query_for,
    fetch_apple_metadata,
    fetch_spotify_metadata,
    build_filter_string,
    youtube_search_query,
)
from bot.services.music.models import GuildPlayer, Track

EMOJI_MUSIC_PLAY = "<a:musicplay:1485243787084042270>"
EMOJI_MUSIC_PAUSE = "<a:musicpause:1485244346386350111>"
EMOJI_MUSIC_NEXT = "<a:musicnext:1485244699605471312>"
EMOJI_MUSIC_STOP = "⏹️"
EMOJI_MUSIC_SHUFFLE = "<a:musicshuffle:1485245854548885626>"
EMOJI_MUSIC_LOOP = "<a:musicloop:1485246094505017515>"
EMOJI_MUSIC_VOL = "<a:musicvol:1485246400940867695>"
EMOJI_MUSIC_QUEUE = "<a:musicqueue:1485246769318072431>"

__all__ = [
    "Music", "Track", "GuildPlayer",
    "build_filter_string", "get_ffmpeg_opts", "get_ytdl_opts",
]

class Music(commands.Cog, name="music"):
    """Music playback commands (YouTube via yt-dlp)."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._players: dict[int, GuildPlayer] = {}
        self._last_fetch_error: str | None = None

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Auto-leave when everyone leaves the voice channel."""
        if member.bot:
            return
        try:
            if before.channel and before.channel.guild:
                guild = before.channel.guild
                voice_client = guild.voice_client
                player = self._get_player(guild.id)
                player.skip_votes.discard(member.id)
                if voice_client and voice_client.channel == before.channel:
                    if (
                        len(voice_client.channel.members) == 1
                        and voice_client.channel.members[0].bot
                    ):
                        player.last_track = player.current
                        player.queue.clear()
                        player.current = None
                        player.skip_votes.clear()
                        self._reset_player_settings(player)
                        try:
                            await self._update_presence(None, guild)
                            await voice_client.disconnect()
                        except Exception:
                            pass
        except Exception:
            pass

    async def _update_presence(self, track: Track | None, guild: discord.Guild) -> None:
        """Update the voice channel status to show the current track."""
        try:
            voice_client = guild.voice_client
            if voice_client:
                if track:
                    await voice_client.channel.edit(
                        status=f"<a:dance:1484553189964644352> Listening: {track.title[:100]}"
                    )
                else:
                    await voice_client.channel.edit(status=None)
        except Exception:
            pass

    def _build_now_playing_embed(
        self, track: Track, player: GuildPlayer
    ) -> discord.Embed:
        """Build the now playing embed for a track."""
        embed = discord.Embed(color=0x1DB954)
        embed.set_author(name="Now Playing", icon_url=None)
        embed.description = (
            f"[{track.title}]({track.url})" if track.url else track.title
        )
        embed.add_field(name="Duration", value=track.fmt_duration(), inline=True)
        embed.add_field(name="Requested by", value=track.requester.mention, inline=True)
        embed.add_field(
            name=f"{EMOJI_MUSIC_LOOP} Loop",
            value=self._loop_state(player),
            inline=True,
        )
        embed.add_field(
            name=f"{EMOJI_MUSIC_VOL} Volume",
            value=f"{int(player.volume * 100)}%",
            inline=True,
        )
        return embed

    def _make_embed(
        self, title: str, color: int, description: str = ""
    ) -> discord.Embed:
        embed = discord.Embed(color=color)
        embed.set_author(
            name=title,
            icon_url=None,
        )
        if description:
            embed.description = description
        return embed

    def _get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self._players:
            self._players[guild_id] = GuildPlayer(guild_id)
        return self._players[guild_id]

    async def _fetch_track(self, query: str, requester: discord.Member) -> Track | None:
        search_query = query
        self._last_fetch_error = None

        spotify = parse_spotify_url(query)
        if spotify:
            kind, spotify_id = spotify
            if kind != "track":
                self._last_fetch_error = (
                    f"I can't play a Spotify **{kind}** link. Open the song in "
                    "Spotify, then send me that song's own link."
                )
                return None

            info = await fetch_spotify_metadata(spotify_id)
            if not info:
                self._last_fetch_error = (
                    "Couldn't read that Spotify track. The Web API isn't "
                    "configured — add `SPOTIPY_CLIENT_ID` and "
                    "`SPOTIPY_CLIENT_SECRET` to `.env`, or just send a search term."
                )
                return None
            search_query = search_query_for(info["title"], info["artist"])
            print(f"Spotify '{spotify_id}' -> YouTube search: {search_query}")

        apple = parse_apple_url(query)
        if apple:
            kind, song_id = apple
            if kind != "song":
                self._last_fetch_error = (
                    "I can't play an Apple Music **album** link. Open the song "
                    "in Apple Music, then send me that song's own link."
                )
                return None

            info = await fetch_apple_metadata(song_id)
            if not info:
                self._last_fetch_error = (
                    "Couldn't read that Apple Music track. Try sending a search "
                    "term instead."
                )
                return None
            search_query = search_query_for(info["title"], info["artist"])
            print(f"Apple Music '{song_id}' -> YouTube search: {search_query}")

        is_external_url = query.startswith("http")

        if is_external_url and not (spotify or apple):
            if is_spotify_url(query) or is_apple_url(query):
                # A Spotify/Apple link we couldn't parse is still unplayable: never
                # hand it to yt-dlp, which has no extractor for either service.
                self._last_fetch_error = (
                    "That link doesn't point at a single song. Send the **song's** "
                    "share link, or just a search term."
                )
                return None
            if is_soundcloud_url(query):
                print(f"SoundCloud URL detected: {query}")

        try:
            full_query = (
                search_query
                if search_query.startswith("http")
                else youtube_search_query(search_query)
            )
            data = await extract_info(full_query)
        except Exception as e:
            print(f"yt-dlp error: {e}")
            self._last_fetch_error = classify_ytdl_error(e)
            return None

        if data is None:
            return None

        if "entries" in data:
            if not data["entries"]:
                return None
            data = data["entries"][0]

        return Track(data, requester)


    def _schedule_play_next(self, guild_id: int) -> None:
        """Schedule _play_next on the bot loop and surface any errors."""
        try:
            future = asyncio.run_coroutine_threadsafe(
                self._play_next(guild_id), self.bot.loop
            )
        except Exception:
            traceback.print_exc()
            return

        def _done_callback(fut) -> None:
            try:
                exc = fut.exception()
            except asyncio.CancelledError:
                return
            if exc:
                print(f"Music queue error in guild {guild_id}:")
                traceback.print_exception(type(exc), exc, exc.__traceback__)

        try:
            future.add_done_callback(_done_callback)
        except Exception:
            traceback.print_exc()

    async def _play_next(self, guild_id: int) -> None:
        """Called when a track finishes; schedules the next one."""
        try:
            await self._play_next_impl(guild_id)
        except Exception:
            print(f"Music queue error in guild {guild_id}:")
            traceback.print_exc()

    async def _play_next_impl(self, guild_id: int) -> None:
        player = self._get_player(guild_id)
        if player.game_active:
            return
        player.skip_votes.clear()
        requeue = self._requeue_finished(player)
        if requeue == "front":
            player.queue.appendleft(player.current)
        elif requeue == "back":
            player.queue.append(player.current)
        if player.queue:
            player.current = player.queue.popleft()
            loop = asyncio.get_running_loop()
            ydl_opts = get_ytdl_opts()
            try:
                ytdl_instance = yt_dlp.YoutubeDL(ydl_opts)
                data = await loop.run_in_executor(
                    None,
                    functools.partial(
                        ytdl_instance.extract_info,
                        player.current.url or f"ytsearch1:{player.current.title}",
                        download=False,
                    ),
                )
                if data:
                    if "entries" in data and data["entries"]:
                        data = data["entries"][0]
                    new_url = data.get("url", "")
                    if new_url:
                        player.current.stream_url = new_url
            except Exception:
                pass
            filter_str = build_filter_string(player)
            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(player.current.stream_url, **get_ffmpeg_opts(filter_str)),
                volume=player.volume,
            )
            guild = self.bot.get_guild(guild_id)
            voice_client = guild and guild.voice_client
            if not voice_client:
                return

            def after_callback(error: Exception | None) -> None:
                if error:
                    print(f"Playback error in guild {guild_id}:")
                    traceback.print_exception(type(error), error, error.__traceback__)
                self._schedule_play_next(guild_id)

            try:
                player._start_time = asyncio.get_running_loop().time()
                voice_client.play(source, after=after_callback)
            except Exception as e:
                # Only failing to *start* playback is fatal. The cosmetic updates
                # below used to share this handler, so a failed presence update or
                # a blocked "now playing" message wiped the whole queue.
                print(f"Voice connection error: {e}")
                player.current = None
                await self._notify(
                    player,
                    self._make_embed(
                        "❌ Voice Error", 0xE74C3C,
                        "Voice connection failed. Please rejoin — your queue is kept.",
                    ),
                )
                return

            # Everything from here on is cosmetic: it must never touch the queue.
            try:
                await self._update_presence(player.current, guild)
            except Exception as e:
                print(f"Presence update failed in guild {guild_id}: {e}")
            try:
                await self._maybe_start_spectrum(guild_id, guild)
            except Exception as e:
                print(f"Spectrum failed to start in guild {guild_id}: {e}")
            await self._notify(
                player, self._build_now_playing_embed(player.current, player)
            )
        else:
            if player.autoplay and player.last_track:
                loop = asyncio.get_running_loop()
                try:
                    related_query = f"ytsearch1:{player.last_track.title} similar"
                    ydl_opts = get_ytdl_opts()
                    ytdl_instance = yt_dlp.YoutubeDL(ydl_opts)
                    data = await loop.run_in_executor(
                        None,
                        functools.partial(ytdl_instance.extract_info, related_query, download=False),
                    )
                    if data and "entries" in data and data["entries"]:
                        entry = data["entries"][0]
                        if entry:
                            track = Track(entry, player.last_track.requester)
                            player.queue.append(track)
                            await self._play_next(guild_id)
                            return
                except Exception:
                    pass
            player.current = None
            player.skip_votes.clear()
            guild = self.bot.get_guild(guild_id)
            if guild and guild.voice_client:
                await self._update_presence(None, guild)
            await self._notify(
                player, self._make_embed("🎵 Queue Finished", 0x95A5A6, "No more tracks in queue.")
            )

    async def _notify(self, player: GuildPlayer, embed: discord.Embed) -> None:
        """Send a status embed to the player's text channel, if one is available.

        Delivery is best-effort: a missing permission or a deleted channel must
        never propagate into the playback path, where it would be mistaken for a
        fatal playback error.
        """
        channel = player.text_channel
        if channel is None:
            return
        try:
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Could not post music status in guild {player.guild_id}: {e}")

    @staticmethod
    def _remember_text_channel(player: GuildPlayer, ctx: commands.Context) -> None:
        """Remember where to post status messages for this guild.

        Any Messageable qualifies. A voice channel's text chat arrives as
        ``discord.VoiceChannel``, so restricting this to ``TextChannel`` used to
        silently drop every status message for commands run inside voice chat.
        """
        player.text_channel = ctx.channel if isinstance(ctx.channel, Messageable) else None

    # ── join ──────────────────────────────────────────────────────────────────
    @commands.command(name="join", aliases=["connect", "j", "cd"])
    async def join(self, ctx: commands.Context) -> None:
        """Join your voice channel to play music. Usage: alpha join"""
        if not ctx.author.voice:
            embed = self._make_embed(
                "❌ Not Connected", 0xE74C3C, "You are not in a voice channel"
            )
            await ctx.send(embed=embed)
            return
        channel = ctx.author.voice.channel
        try:
            if ctx.voice_client:
                try:
                    await ctx.voice_client.disconnect()
                    await asyncio.sleep(0.5)
                except Exception:
                    pass
            await channel.connect()
            embed = self._make_embed(
                "Connected", 0x3498DB, f"Joined voice channel: **{channel.name}**"
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = self._make_embed(
                "❌ Connection Failed", 0xE74C3C, f"Could not join voice channel: {e}"
            )
            await ctx.send(embed=embed)

    # ── leave ─────────────────────────────────────────────────────────────────
    @commands.command(name="leave", aliases=["disconnect", "dc", "exit"])
    async def leave(self, ctx: commands.Context) -> None:
        """Leave the voice channel and stop playback. Usage: alpha leave"""
        if not ctx.voice_client:
            embed = self._make_embed(
                "❌ Not Connected", 0xE74C3C, "Bot is not in a voice channel"
            )
            await ctx.send(embed=embed)
            return
        player = self._get_player(ctx.guild.id)
        player.last_track = player.current
        player.queue.clear()
        player.current = None
        self._reset_player_settings(player)
        vc = ctx.voice_client
        await self._update_presence(None, ctx.guild)
        await self._maybe_stop_spectrum(ctx.guild.id)
        await vc.disconnect()
        embed = self._make_embed("Disconnected", 0x3498DB, "Left the voice channel.")
        await ctx.send(embed=embed)

    async def _maybe_start_spectrum(self, guild_id: int, guild: discord.Guild) -> None:
        """Start spectrum visualizer if the cog is loaded and enabled."""
        try:
            spectrum_cog = self.bot.get_cog("spectrum")
            if spectrum_cog and spectrum_cog._spectrum_enabled.get(guild_id, False):
                viz = spectrum_cog._get_visualizer(guild_id)
                if not viz.is_active:
                    await viz.start(self.bot, guild_id)
        except Exception:
            pass

    async def _maybe_stop_spectrum(self, guild_id: int) -> None:
        """Stop spectrum visualizer."""
        try:
            spectrum_cog = self.bot.get_cog("spectrum")
            if spectrum_cog:
                viz = spectrum_cog._get_visualizer(guild_id)
                if viz.is_active:
                    await viz.stop()
        except Exception:
            pass

    def _reset_player_settings(self, player: GuildPlayer) -> None:
        """Reset all player settings to default."""
        player.volume = 1.0
        player.loop = False
        player.queue_loop = False
        player.autoplay = False
        player.bassboost = False
        player.nightcore = False
        player.eight_d = False
        player.slowed = False
        player.equalizer = "flat"

    # ── revive ────────────────────────────────────────────────────────────────
    @commands.command(name="revive", aliases=["resumequeue", "rq"])
    async def revive(self, ctx: commands.Context) -> None:
        """Revive the last track after bot disconnect. Usage: alpha revive"""
        player = self._get_player(ctx.guild.id)

        if player.current or player.queue:
            embed = self._make_embed(
                "❌ Queue Active", 0xE74C3C, "A queue is already active. Use `alpha skip` to clear it first."
            )
            await ctx.send(embed=embed)
            return

        if not player.last_track:
            embed = self._make_embed(
                "❌ No Queue", 0xE74C3C, "No previous queue found to revive."
            )
            await ctx.send(embed=embed)
            return

        if not ctx.author.voice:
            embed = self._make_embed(
                "❌ Not in VC", 0xE74C3C, "You must be in a voice channel"
            )
            await ctx.send(embed=embed)
            return

        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        player.current = player.last_track
        player.last_track = None
        filter_str = build_filter_string(player)
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(player.current.stream_url, **get_ffmpeg_opts(filter_str)),
            volume=player.volume,
        )

        def after_callback(error: Exception | None) -> None:
            if error:
                print(f"Playback error: {error}")
                traceback.print_exception(type(error), error, error.__traceback__)
            self._schedule_play_next(ctx.guild.id)

        ctx.voice_client.play(source, after=after_callback)
        await self._update_presence(player.current, ctx.guild)
        self._remember_text_channel(player, ctx)
        await ctx.send(embed=self._build_now_playing_embed(player.current, player))

    # ── play ──────────────────────────────────────────────────────────────────
    @commands.command(name="play", aliases=["p"])
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def play(self, ctx: commands.Context, *, query: str) -> None:
        """Play a song or add it to the queue. Usage: alpha play <url or search query>"""
        player = self._get_player(ctx.guild.id)
        if player.game_active:
            embed = self._make_embed(
                "❌ Game In Progress",
                0xE74C3C,
                "A song-guessing game is running in this voice channel. "
                "Wait for it to finish before playing music.",
            )
            await ctx.send(embed=embed)
            return
        if not ctx.author.voice:
            embed = self._make_embed(
                "❌ Not Connected", 0xE74C3C, "You must be in a voice channel"
            )
            await ctx.send(embed=embed)
            return
        if not ctx.voice_client:
            try:
                await ctx.author.voice.channel.connect()
            except Exception as e:
                embed = self._make_embed(
                    "❌ Connection Failed", 0xE74C3C, f"Could not join voice: {e}"
                )
                await ctx.send(embed=embed)
                return

        is_external = query.startswith("http") or bool(parse_spotify_url(query) or parse_apple_url(query))
        if is_external:
            if parse_spotify_url(query):
                msg = await ctx.send(embed=self._make_embed("🔍 Spotify Detected", 0x1DB954, "Finding on YouTube..."))
            elif is_apple_url(query):
                msg = await ctx.send(embed=self._make_embed("🔍 Apple Music Detected", 0xFC3C44, "Finding on YouTube..."))
            elif is_soundcloud_url(query):
                msg = await ctx.send(embed=self._make_embed("🔍 SoundCloud Detected", 0xFF5500, "Loading..."))
            else:
                msg = await ctx.send(embed=self._make_embed("🔍 Searching...", 0x1DB954, query))
        else:
            msg = await ctx.send(embed=self._make_embed("🔍 Searching...", 0x1DB954, query))

        async with ctx.typing():
            track = await self._fetch_track(query, ctx.author)

        if msg:
            try:
                await msg.delete()
            except Exception:
                pass

        if track is None:
            friendly = getattr(self, "_last_fetch_error", None)
            embed = self._make_embed(
                "❌ Not Found", 0xE74C3C, friendly or f"Could not find **'{query}'**"
            )
            await ctx.send(embed=embed)
            return

        player = self._get_player(ctx.guild.id)
        self._remember_text_channel(player, ctx)

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            player.queue.append(track)
            embed = discord.Embed(color=0x1DB954)
            embed.set_author(
                name="➕ Added to Queue",
                icon_url=None,
            )
            embed.description = (
                f"[{track.title}]({track.url})" if track.url else track.title
            )
            embed.add_field(
                name="📍 Position", value=f"**{len(player.queue)}**", inline=True
            )
            embed.add_field(name="⏱️ Duration", value=track.fmt_duration(), inline=True)
            embed.set_footer(text=f"Requested by {track.requester.display_name}")
            await ctx.send(embed=embed)
            return

        player.current = track
        filter_str = build_filter_string(player)
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(track.stream_url, **get_ffmpeg_opts(filter_str)),
            volume=player.volume,
        )

        def after_callback(error: Exception | None) -> None:
            if error:
                print(f"Playback error: {error}")
                traceback.print_exception(type(error), error, error.__traceback__)
            self._schedule_play_next(ctx.guild.id)

        player._start_time = asyncio.get_running_loop().time()
        ctx.voice_client.play(source, after=after_callback)
        await self._update_presence(track, ctx.guild)
        await self._maybe_start_spectrum(ctx.guild.id, ctx.guild)
        await ctx.send(embed=self._build_now_playing_embed(track, player))

    # ── pause ─────────────────────────────────────────────────────────────────
    @commands.command(name="pause")
    async def pause(self, ctx: commands.Context) -> None:
        """Pause the current track. Usage: alpha pause"""
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            embed = self._make_embed("Paused", 0x95A5A6, f"{EMOJI_MUSIC_PAUSE} Playback paused.")
            await ctx.send(embed=embed)
        else:
            embed = self._make_embed(
                "❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing"
            )
            await ctx.send(embed=embed)

    # ── resume ────────────────────────────────────────────────────────────────
    @commands.command(name="resume", aliases=["unpause"])
    async def resume(self, ctx: commands.Context) -> None:
        """Resume paused playback. Usage: alpha resume"""
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            embed = self._make_embed("Resumed", 0x2ECC71, f"{EMOJI_MUSIC_PLAY} Playback resumed.")
            await ctx.send(embed=embed)
        else:
            embed = self._make_embed(
                "❌ Not Paused", 0xE74C3C, "Playback is not paused"
            )
            await ctx.send(embed=embed)

    # ── stop ──────────────────────────────────────────────────────────────────
    @commands.command(name="stop")
    async def stop(self, ctx: commands.Context) -> None:
        """Stop playback and clear the queue. Usage: alpha stop"""
        if not ctx.voice_client:
            embed = self._make_embed(
                "❌ Not Connected", 0xE74C3C, "Bot is not in a voice channel"
            )
            await ctx.send(embed=embed)
            return
        player = self._get_player(ctx.guild.id)
        if player.game_active:
            embed = self._make_embed(
                "❌ Game In Progress",
                0xE74C3C,
                "A song-guessing game is running in this voice channel. "
                "Wait for it to finish before stopping playback.",
            )
            await ctx.send(embed=embed)
            return
        player.queue.clear()
        player.current = None
        self._reset_player_settings(player)
        ctx.voice_client.stop()
        await self._update_presence(None, ctx.guild)
        embed = self._make_embed(
            "Stopped",
            0xE74C3C,
            f"{EMOJI_MUSIC_STOP} Playback stopped and queue cleared.",
        )
        await ctx.send(embed=embed)

    # ── skip ──────────────────────────────────────────────────────────────────
    @commands.command(name="skip", aliases=["s", "next"])
    async def skip(self, ctx: commands.Context) -> None:
        """Vote to skip the current track (auto-votes). Skip triggers at 50% votes. Usage: alpha skip"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = self._make_embed(
                "❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing"
            )
            await ctx.send(embed=embed)
            return

        if not ctx.author.voice or ctx.author.voice.channel != ctx.voice_client.channel:
            embed = self._make_embed(
                "❌ Not in VC", 0xE74C3C, "You must be in the same voice channel"
            )
            await ctx.send(embed=embed)
            return

        player = self._get_player(ctx.guild.id)

        if not player.current:
            embed = self._make_embed(
                "❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing"
            )
            await ctx.send(embed=embed)
            return

        if ctx.author.id == player.current.requester.id:
            await self._fade_out_and_skip(ctx.guild.id)
            embed = self._make_embed(
                "Skipped", 0xF39C12, f"Requester skipped: **{player.current.title}**"
            )
            await ctx.send(embed=embed)
            return

        if ctx.author.id in player.skip_votes:
            player.skip_votes.discard(ctx.author.id)
            total_members = len([m for m in ctx.voice_client.channel.members if not m.bot])
            needed = math.ceil(total_members / 2)
            embed = self._make_embed(
                "Vote Removed", 0x95A5A6,
                f"Vote removed. **{len(player.skip_votes)}/{needed}** votes needed."
            )
            await ctx.send(embed=embed)
            return

        player.skip_votes.add(ctx.author.id)

        total_members = len([m for m in ctx.voice_client.channel.members if not m.bot])
        needed = math.ceil(total_members / 2)
        current_votes = len(player.skip_votes)

        if current_votes >= needed:
            track_name = player.current.title if player.current else "Unknown"
            await self._fade_out_and_skip(ctx.guild.id)
            player.skip_votes.clear()
            embed = self._make_embed(
                "Vote Skip!", 0x2ECC71,
                f"Skip passed with **{current_votes}/{total_members}** votes!\nSkipped: **{track_name}**"
            )
            await ctx.send(embed=embed)
        else:
            embed = self._make_embed(
                "Vote Added", 0x3498DB,
                f"**{ctx.author}** voted to skip.\n**{current_votes}/{needed}** votes needed."
            )
            await ctx.send(embed=embed)

    async def _fade_out_and_skip(self, guild_id: int) -> None:
        """Fade out volume over 5 seconds then skip."""
        player = self._get_player(guild_id)
        guild = self.bot.get_guild(guild_id)
        if not guild or not guild.voice_client:
            return
        
        voice_client = guild.voice_client
        if not voice_client:
            return
        if not voice_client.source:
            try:
                voice_client.stop()
            except Exception:
                pass
            return

        original_volume = player.volume
        steps = 10
        fade_delay = 0.5
        volume_step = original_volume / steps

        for i in range(steps):
            await asyncio.sleep(fade_delay)
            try:
                if voice_client and voice_client.source:
                    new_vol = max(0, original_volume - (volume_step * (i + 1)))
                    voice_client.source.volume = new_vol
            except Exception:
                pass

        try:
            voice_client.stop()
        except Exception:
            pass

    # ── queue ─────────────────────────────────────────────────────────────────
    @commands.command(name="queue", aliases=["q"])
    async def queue(self, ctx: commands.Context) -> None:
        """View the current music queue. Usage: alpha queue"""
        player = self._get_player(ctx.guild.id)
        embed = discord.Embed(color=0x1DB954)
        embed.set_author(
            name=f"{EMOJI_MUSIC_QUEUE} Music Queue",
            icon_url=None,
        )

        if player.current:
            embed.add_field(
                name="Now Playing",
                value=f"`{player.current.title}` [{player.current.fmt_duration()}] — {player.current.requester.mention}",
                inline=False,
            )
        if player.queue:
            lines = "\n".join(
                f"`{i + 1}.` {t.title} [{t.fmt_duration()}]"
                for i, t in enumerate(list(player.queue)[:15])
            )
            if len(player.queue) > 15:
                lines += f"\n… and {len(player.queue) - 15} more"
            embed.add_field(
                name=f"Queue ({len(player.queue)} tracks)",
                value=lines,
                inline=False,
            )
        else:
            embed.add_field(name="Queue", value="Empty", inline=False)
        embed.add_field(
            name=f"{EMOJI_MUSIC_LOOP} Loop",
            value=self._loop_state(player),
            inline=True,
        )
        embed.add_field(
            name=f"{EMOJI_MUSIC_VOL} Volume",
            value=f"{int(player.volume * 100)}%",
            inline=True,
        )
        await ctx.send(embed=embed)

    # ── nowplaying ────────────────────────────────────────────────────────────
    @commands.command(name="nowplaying", aliases=["np", "current"])
    async def nowplaying(self, ctx: commands.Context) -> None:
        """Show what's currently playing. Usage: alpha nowplaying"""
        player = self._get_player(ctx.guild.id)
        if not player.current:
            embed = self._make_embed(
                "❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing"
            )
            await ctx.send(embed=embed)
            return
        await ctx.send(embed=self._build_now_playing_embed(player.current, player))

    # ── volume ────────────────────────────────────────────────────────────────
    @commands.command(name="volume", aliases=["vol"])
    async def volume(self, ctx: commands.Context, level: int) -> None:
        """Adjust the music volume. Usage: alpha volume <0-200>"""
        if not 0 <= level <= 200:
            embed = self._make_embed(
                "❌ Invalid Volume", 0xE74C3C, "Value must be between 0 and 200"
            )
            await ctx.send(embed=embed)
            return
        player = self._get_player(ctx.guild.id)
        player.volume = level / 100
        if ctx.voice_client and ctx.voice_client.source:
            ctx.voice_client.source.volume = player.volume
        embed = self._make_embed(
            "Volume Changed", 0x2ECC71, f"{EMOJI_MUSIC_VOL} Volume set to **{level}%**"
        )
        await ctx.send(embed=embed)

    # ── shuffle ───────────────────────────────────────────────────────────────
    @commands.command(name="shuffle")
    async def shuffle(self, ctx: commands.Context) -> None:
        """Shuffle the music queue. Usage: alpha shuffle"""
        player = self._get_player(ctx.guild.id)
        if len(player.queue) < 2:
            embed = self._make_embed(
                "❌ Not Enough Tracks",
                0xE74C3C,
                "Not enough tracks in queue to shuffle",
            )
            await ctx.send(embed=embed)
            return
        q = list(player.queue)
        random.shuffle(q)
        player.queue = deque(q)
        embed = self._make_embed(
            "Queue Shuffled",
            0x9B59B6,
            f"{EMOJI_MUSIC_SHUFFLE} Queue shuffled ({len(player.queue)} tracks)",
        )
        await ctx.send(embed=embed)

    # ── loop ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _requeue_finished(player: GuildPlayer) -> str | None:
        """Where the finished track is re-enqueued: 'front' (single-track loop),
        'back' (whole-queue loop), or None."""
        if player.loop and player.current:
            return "front"
        if player.queue_loop and player.current:
            return "back"
        return None

    @staticmethod
    def _loop_state(player: GuildPlayer) -> str:
        if player.queue_loop:
            return "ON — queue"
        if player.loop:
            return "ON — single"
        return "OFF"

    @commands.command(name="loop", aliases=["repeat"])
    async def loop(self, ctx: commands.Context, mode: str = None) -> None:
        """Loop the current track or the whole queue. Usage: alpha loop [queue|single|off]"""
        player = self._get_player(ctx.guild.id)
        choice = (mode or "").strip().lower()

        if choice in ("queue", "all", "playlist"):
            player.queue_loop = not player.queue_loop
            if player.queue_loop:
                player.loop = False
            state = "enabled (**whole queue**)" if player.queue_loop else "disabled"
        elif choice in ("", "single", "track", "one"):
            player.loop = not player.loop
            if player.loop:
                player.queue_loop = False
            state = "enabled (**single track**)" if player.loop else "disabled"
        elif choice in ("off", "none", "stop"):
            player.loop = False
            player.queue_loop = False
            state = "disabled"
        else:
            embed = self._make_embed(
                "❌ Invalid Mode", 0xE74C3C, "Use: `alpha loop [queue|single|off]`"
            )
            await ctx.send(embed=embed)
            return

        embed = self._make_embed("Loop Toggled", 0xF39C12, f"{EMOJI_MUSIC_LOOP} Loop {state}")
        await ctx.send(embed=embed)

    # ── remove ────────────────────────────────────────────────────────────────
    @commands.command(name="remove")
    async def remove(self, ctx: commands.Context, index: int) -> None:
        """Remove a track from queue by position. Usage: alpha remove <position>"""
        player = self._get_player(ctx.guild.id)
        if not player.queue or not 1 <= index <= len(player.queue):
            embed = self._make_embed(
                "❌ Invalid Index", 0xE74C3C, "Invalid queue index"
            )
            await ctx.send(embed=embed)
            return
        q = list(player.queue)
        removed = q.pop(index - 1)
        player.queue = deque(q)
        embed = self._make_embed(
            "Track Removed", 0xE67E22, f"Removed: **{removed.title}**"
        )
        await ctx.send(embed=embed)

    # ── radio ─────────────────────────────────────────────────────────────────
    @commands.command(name="radio")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def radio(self, ctx: commands.Context, *, genre: str) -> None:
        """Play a radio stream of a music genre. Usage: alpha radio <genre>"""
        if not ctx.author.voice:
            embed = self._make_embed(
                "❌ Not Connected", 0xE74C3C, "You must be in a voice channel"
            )
            await ctx.send(embed=embed)
            return
        if not ctx.voice_client:
            await ctx.author.voice.channel.connect()

        loading_embed = self._make_embed(
            "📻 Loading Radio", 0x3498DB, f"Searching for **{genre}** genre mixes..."
        )
        loading_msg = await ctx.send(embed=loading_embed)

        player = self._get_player(ctx.guild.id)
        self._remember_text_channel(player, ctx)

        search_queries = [
            f"ytsearch15:{genre} mix",
            f"ytsearch15:{genre} playlist popular",
            f"ytsearch10:{genre} music compilation",
        ]

        tracks_found = []
        loop = asyncio.get_running_loop()
        ydl_opts = get_ytdl_opts()
        ytdl_instance = yt_dlp.YoutubeDL(ydl_opts)

        for query in search_queries:
            if len(tracks_found) >= 10:
                break
            try:
                data = await loop.run_in_executor(
                    None,
                    functools.partial(ytdl_instance.extract_info, query, download=False),
                )
                if data and "entries" in data:
                    for entry in data["entries"]:
                        if entry and entry not in tracks_found:
                            tracks_found.append(entry)
            except Exception:
                continue

        if not tracks_found:
            await loading_msg.edit(embed=self._make_embed(
                "❌ No Results", 0xE74C3C, f"Could not find any **{genre}** genre tracks"
            ))
            return

        unique_tracks = []
        seen_urls = set()
        for track_data in tracks_found:
            if track_data and track_data.get("url") not in seen_urls:
                seen_urls.add(track_data["url"])
                unique_tracks.append(Track(track_data, ctx.author))

        random.shuffle(unique_tracks)

        added_count = len(unique_tracks)
        for track in unique_tracks:
            player.queue.append(track)

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            embed = self._make_embed(
                "📻 Radio Queued", 0x9B59B6,
                f"Added **{added_count}** tracks from **{genre}** genre to queue"
            )
            await loading_msg.edit(embed=embed)
        else:
            if player.queue:
                player.current = player.queue.popleft()
                filter_str = build_filter_string(player)
                source = discord.PCMVolumeTransformer(
                    discord.FFmpegPCMAudio(player.current.stream_url, **get_ffmpeg_opts(filter_str)),
                    volume=player.volume,
                )

                def after_callback(error: Exception | None) -> None:
                    if error:
                        print(f"Playback error: {error}")
                        traceback.print_exception(type(error), error, error.__traceback__)
                    self._schedule_play_next(ctx.guild.id)

                ctx.voice_client.play(source, after=after_callback)
                await self._update_presence(player.current, ctx.guild)

            embed = discord.Embed(color=0x9B59B6)
            embed.set_author(name="📻 Radio Started", icon_url=None)
            embed.description = f"Playing **{len(player.queue) + (1 if player.current else 0)}** tracks from **{genre}** genre"
            embed.add_field(name="Genre", value=genre.title(), inline=True)
            embed.add_field(name="Tracks", value=f"**{added_count}** in queue", inline=True)
            if player.current:
                embed.add_field(
                    name="Now Playing",
                    value=f"[{player.current.title}]({player.current.url})" if player.current.url else player.current.title,
                    inline=False,
                )
            await loading_msg.edit(embed=embed)

    # ── clearqueue ────────────────────────────────────────────────────────────
    @commands.command(name="clearqueue", aliases=["cq"])
    async def clearqueue(self, ctx: commands.Context) -> None:
        """Clear all tracks from the queue. Usage: alpha clearqueue"""
        player = self._get_player(ctx.guild.id)
        count = len(player.queue)
        player.queue.clear()
        embed = self._make_embed(
            "Queue Cleared", 0x95A5A6, f"Cleared **{count}** track(s) from queue"
        )
        await ctx.send(embed=embed)

    # ── seek ──────────────────────────────────────────────────────────────────
    @commands.command(name="seek")
    async def seek(self, ctx: commands.Context, position: str) -> None:
        """Seek to a position in the track. Usage: alpha seek <MM:SS>"""
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            embed = self._make_embed("❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing")
            await ctx.send(embed=embed)
            return
        
        player = self._get_player(ctx.guild.id)
        if not player.current:
            embed = self._make_embed("❌ No Track", 0xE74C3C, "No track loaded")
            await ctx.send(embed=embed)
            return

        try:
            parts = position.split(":")
            if len(parts) == 2:
                secs = int(parts[0]) * 60 + int(parts[1])
            else:
                secs = int(position)
        except ValueError:
            embed = self._make_embed("❌ Invalid Format", 0xE74C3C, "Use format: MM:SS or seconds")
            await ctx.send(embed=embed)
            return

        if secs < 0 or secs > player.current.duration:
            embed = self._make_embed("❌ Out of Range", 0xE74C3C, f"Track duration is {player.current.fmt_duration()}")
            await ctx.send(embed=embed)
            return

        ctx.voice_client.pause()
        filter_str = build_filter_string(player)
        opts = get_ffmpeg_opts(filter_str)
        opts["before_options"] = f"{opts['before_options']} -ss {secs}"
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(player.current.stream_url, **opts),
            volume=player.volume,
        )

        def after_callback(error: Exception | None) -> None:
            if error:
                print(f"Playback error: {error}")
                traceback.print_exception(type(error), error, error.__traceback__)
            self._schedule_play_next(ctx.guild.id)

        ctx.voice_client.play(source, after=after_callback)
        embed = self._make_embed("⏩ Seek", 0x2ECC71, f"Jumped to **{position}**")
        await ctx.send(embed=embed)

    # ── replay ────────────────────────────────────────────────────────────────
    @commands.command(name="replay")
    async def replay(self, ctx: commands.Context) -> None:
        """Replay the current track from the beginning. Usage: alpha replay"""
        if not ctx.voice_client or not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            embed = self._make_embed("❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing")
            await ctx.send(embed=embed)
            return
        
        player = self._get_player(ctx.guild.id)
        if not player.current:
            embed = self._make_embed("❌ No Track", 0xE74C3C, "No track to replay")
            await ctx.send(embed=embed)
            return

        player.queue.appendleft(player.current)
        player.current = None
        ctx.voice_client.stop()
        embed = self._make_embed("🔄 Replaying", 0x9B59B6, f"Replaying: **{player.queue[0].title if player.queue else 'Unknown'}**")
        await ctx.send(embed=embed)

    # ── autoplay ─────────────────────────────────────────────────────────────
    @commands.command(name="autoplay")
    async def autoplay(self, ctx: commands.Context) -> None:
        """Toggle autoplay for similar tracks. Usage: alpha autoplay"""
        player = self._get_player(ctx.guild.id)
        player.autoplay = not player.autoplay
        state = "**enabled**" if player.autoplay else "**disabled**"
        embed = self._make_embed("🔄 Autoplay", 0xF39C12, f"Autoplay {state}")
        await ctx.send(embed=embed)

    # ── bassboost ────────────────────────────────────────────────────────────
    @commands.command(name="bassboost")
    async def bassboost(self, ctx: commands.Context) -> None:
        """Toggle bass boost effect. Usage: alpha bassboost"""
        player = self._get_player(ctx.guild.id)
        player.bassboost = not player.bassboost
        state = "**enabled**" if player.bassboost else "**disabled**"
        embed = self._make_embed("🔊 Bass Boost", 0xE67E22, f"Bass boost {state}")
        await ctx.send(embed=embed)

    # ── nightcore ────────────────────────────────────────────────────────────
    @commands.command(name="nightcore")
    async def nightcore(self, ctx: commands.Context) -> None:
        """Toggle nightcore effect (faster + higher pitch). Usage: alpha nightcore"""
        player = self._get_player(ctx.guild.id)
        player.nightcore = not player.nightcore
        state = "**enabled**" if player.nightcore else "**disabled**"
        embed = self._make_embed("🌙 Nightcore", 0x9B59B6, f"Nightcore effect {state}")
        await ctx.send(embed=embed)

    # ── 8d ───────────────────────────────────────────────────────────────────
    @commands.command(name="8d", aliases=["eightd"])
    async def eight_d(self, ctx: commands.Context) -> None:
        """Toggle 8D audio effect. Usage: alpha 8d"""
        if not ctx.voice_client or not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            embed = self._make_embed("❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing")
            await ctx.send(embed=embed)
            return
        player = self._get_player(ctx.guild.id)
        player.eight_d = not player.eight_d
        state = "**enabled**" if player.eight_d else "**disabled**"
        embed = self._make_embed("🎧 8D Audio", 0x3498DB, f"8D effect {state}\n*Rotating audio with reverb*")
        await ctx.send(embed=embed)

    # ── equalizer ────────────────────────────────────────────────────────────
    @commands.command(name="equalizer", aliases=["eq"])
    async def equalizer(self, ctx: commands.Context, preset: str = "flat") -> None:
        """Set equalizer preset. Usage: alpha equalizer <preset>"""
        player = self._get_player(ctx.guild.id)
        valid_presets = ["flat", "bass", "treble", "pop", "rock", "jazz", "classical", "electronic"]
        preset = preset.lower()
        if preset not in valid_presets:
            embed = self._make_embed("❌ Invalid Preset", 0xE74C3C, f"Valid presets: {', '.join(valid_presets)}")
            await ctx.send(embed=embed)
            return
        player.equalizer = preset
        embed = self._make_embed("🎚️ Equalizer", 0x2ECC71, f"Equalizer set to **{preset}**")
        await ctx.send(embed=embed)

    # ── lyrics ───────────────────────────────────────────────────────────────
    @commands.command(name="lyrics")
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def lyrics(self, ctx: commands.Context, *, query: str = None) -> None:
        """Search for song lyrics. Usage: alpha lyrics <song name>"""
        if not query:
            player = self._get_player(ctx.guild.id)
            if player.current:
                query = player.current.title
            else:
                embed = self._make_embed("❌ No Query", 0xE74C3C, "Provide a song name or play a song first")
                await ctx.send(embed=embed)
                return

        msg = await ctx.send(embed=self._make_embed("🔍 Searching...", 0x9B59B6, f"Searching lyrics for: **{query}**"))

        loop = asyncio.get_running_loop()
        try:
            search_query = f"ytsearch1:{query} lyrics official"
            ydl_opts = get_ytdl_opts()
            ytdl_instance = yt_dlp.YoutubeDL(ydl_opts)
            data = await loop.run_in_executor(
                None,
                functools.partial(ytdl_instance.extract_info, search_query, download=False),
            )
            if data and "entries" in data and data["entries"]:
                entry = data["entries"][0]
                title = entry.get("title", query)
                url = entry.get("webpage_url", "")
                
                embed = discord.Embed(color=0x9B59B6)
                embed.set_author(name="🎤 Lyrics Search", icon_url=None)
                embed.description = f"**{title}**"
                embed.add_field(name="Search", value=f"[YouTube Search]({url})", inline=True)
                embed.add_field(name="Tip", value="Search on Genius or lyrics.com", inline=True)
                await msg.edit(embed=embed)
            else:
                await msg.edit(embed=self._make_embed("❌ Not Found", 0xE74C3C, f"Could not find lyrics for: **{query}**"))
        except Exception as e:
            await msg.edit(embed=self._make_embed("❌ Error", 0xE74C3C, f"Search failed: {e}"))

    # ── favorite / favorites ──────────────────────────────────────────────────
    def _add_favorite(self, user_id: int, entry: str) -> bool:
        """Append *entry* to a user's favorites file; False if already saved."""
        path = f"data/favorites_{user_id}.txt"
        os.makedirs("data", exist_ok=True)
        existing = set()
        if os.path.exists(path):
            with open(path, "r") as f:
                existing = {line.strip().lower() for line in f if line.strip()}
        if entry.lower() in existing:
            return False
        with open(path, "a") as f:
            f.write(f"{entry}\n")
        return True

    @commands.command(name="favorite", aliases=["fav", "star"])
    async def favorite(self, ctx: commands.Context) -> None:
        """Favorite the currently playing track. Usage: alpha favorite"""
        player = self._get_player(ctx.guild.id)
        if not player.current:
            embed = self._make_embed("❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing")
            await ctx.send(embed=embed)
            return
        added = self._add_favorite(ctx.author.id, player.current.title)
        if added:
            embed = self._make_embed(
                "⭐ Favorited", 0xF1C40F, f"Added to favorites: **{player.current.title}**"
            )
        else:
            embed = self._make_embed(
                "⭐ Already Saved", 0xF1C40F, f"**{player.current.title}** is already in your favorites"
            )
        await ctx.send(embed=embed)

    @commands.command(name="favorites", aliases=["favs"])
    async def favorites(self, ctx: commands.Context, action: str = None, *, query: str = None) -> None:
        """Manage your favorites. Usage: alpha favorites [add|remove|list] [song name]. Tip: use `alpha favorite` while a track plays."""
        player = self._get_player(ctx.guild.id)
        user_id = str(ctx.author.id)
        
        favorites_file = f"data/favorites_{user_id}.txt"
        os.makedirs("data", exist_ok=True)
        
        if not os.path.exists(favorites_file):
            with open(favorites_file, "w") as f:
                pass
        
        with open(favorites_file, "r") as f:
            user_favs = [line.strip() for line in f if line.strip()]
        
        if not action:
            if not user_favs:
                embed = self._make_embed("⭐ Favorites", 0xF1C40F, "Your favorites list is empty. Use `alpha favorites add <song>` to add.")
                await ctx.send(embed=embed)
                return
            embed = discord.Embed(color=0xF1C40F)
            embed.set_author(name="⭐ Your Favorites", icon_url=None)
            lines = "\n".join(f"`{i+1}.` {f}" for i, f in enumerate(user_favs[:15]))
            if len(user_favs) > 15:
                lines += f"\n… and {len(user_favs) - 15} more"
            embed.description = lines
            await ctx.send(embed=embed)
            return
        
        action = action.lower()
        
        if action == "add":
            if not query:
                embed = self._make_embed("❌ No Song", 0xE74C3C, "Provide a song name to add")
                await ctx.send(embed=embed)
                return
            if player.current and query.lower() in player.current.title.lower():
                fav_entry = player.current.title
            else:
                fav_entry = query
            added = self._add_favorite(ctx.author.id, fav_entry)
            if added:
                embed = self._make_embed("⭐ Added", 0xF1C40F, f"Added to favorites: **{fav_entry}**")
            else:
                embed = self._make_embed("⭐ Already Saved", 0xF1C40F, f"**{fav_entry}** is already in your favorites")
            await ctx.send(embed=embed)
        
        elif action == "remove":
            if not query:
                embed = self._make_embed("❌ No Song", 0xE74C3C, "Provide a song name to remove")
                await ctx.send(embed=embed)
                return
            removed = False
            with open(favorites_file, "r") as f:
                lines = f.readlines()
            with open(favorites_file, "w") as f:
                for line in lines:
                    if query.lower() not in line.strip().lower():
                        f.write(line)
                    else:
                        removed = True
            if removed:
                embed = self._make_embed("⭐ Removed", 0xE74C3C, f"Removed from favorites: **{query}**")
            else:
                embed = self._make_embed("❌ Not Found", 0xE74C3C, f"Could not find: **{query}**")
            await ctx.send(embed=embed)
        
        elif action == "list":
            if not user_favs:
                embed = self._make_embed("⭐ Favorites", 0xF1C40F, "Your favorites list is empty")
                await ctx.send(embed=embed)
                return
            embed = discord.Embed(color=0xF1C40F)
            embed.set_author(name="⭐ Your Favorites", icon_url=None)
            lines = "\n".join(f"`{i+1}.` {f}" for i, f in enumerate(user_favs[:20]))
            embed.description = lines
            await ctx.send(embed=embed)
        
        else:
            embed = self._make_embed("❌ Invalid Action", 0xE74C3C, "Use: `alpha favorites add <song>`, `alpha favorites remove <song>`, or `alpha favorites`")
            await ctx.send(embed=embed)

    # ── playlist ────────────────────────────────────────────────────────────
    @commands.command(name="playlist")
    async def playlist(self, ctx: commands.Context, action: str = None, name: str = None, *, query: str = None) -> None:
        """Manage playlists. Usage: alpha playlist [create|delete|add|remove|save|play|list] [name] [song]. `save` saves the whole queue."""
        playlists_dir = "data/playlists"
        os.makedirs(playlists_dir, exist_ok=True)
        
        if not action:
            playlists = [f.replace(".txt", "") for f in os.listdir(playlists_dir) if f.endswith(".txt")]
            if not playlists:
                embed = self._make_embed("🎶 Playlists", 0x9B59B6, "No playlists yet. Use `alpha playlist create <name>` to create one.")
                await ctx.send(embed=embed)
                return
            embed = discord.Embed(color=0x9B59B6)
            embed.set_author(name="🎶 Server Playlists", icon_url=None)
            embed.description = "\n".join(f"`{p}`" for p in playlists)
            await ctx.send(embed=embed)
            return
        
        action = action.lower()
        
        if action == "create":
            if not name:
                embed = self._make_embed("❌ No Name", 0xE74C3C, "Provide a playlist name")
                await ctx.send(embed=embed)
                return
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()[:50]
            playlist_file = os.path.join(playlists_dir, f"{safe_name}.txt")
            if os.path.exists(playlist_file):
                embed = self._make_embed("❌ Exists", 0xE74C3C, f"Playlist **{safe_name}** already exists")
                await ctx.send(embed=embed)
                return
            with open(playlist_file, "w") as f:
                f.write(f"# {safe_name}\n")
            embed = self._make_embed("✅ Created", 0x2ECC71, f"Created playlist: **{safe_name}**")
            await ctx.send(embed=embed)
        
        elif action == "delete":
            if not name:
                embed = self._make_embed("❌ No Name", 0xE74C3C, "Provide a playlist name")
                await ctx.send(embed=embed)
                return
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()[:50]
            playlist_file = os.path.join(playlists_dir, f"{safe_name}.txt")
            if not os.path.exists(playlist_file):
                embed = self._make_embed("❌ Not Found", 0xE74C3C, f"Playlist **{safe_name}** not found")
                await ctx.send(embed=embed)
                return
            os.remove(playlist_file)
            embed = self._make_embed("🗑️ Deleted", 0xE74C3C, f"Deleted playlist: **{safe_name}**")
            await ctx.send(embed=embed)
        
        elif action == "add":
            if not name or not query:
                embed = self._make_embed("❌ Missing Args", 0xE74C3C, "Usage: `alpha playlist add <name> <song>`")
                await ctx.send(embed=embed)
                return
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()[:50]
            playlist_file = os.path.join(playlists_dir, f"{safe_name}.txt")
            if not os.path.exists(playlist_file):
                embed = self._make_embed("❌ Not Found", 0xE74C3C, f"Playlist **{safe_name}** not found")
                await ctx.send(embed=embed)
                return
            with open(playlist_file, "a") as f:
                f.write(f"{query}\n")
            embed = self._make_embed("➕ Added", 0x2ECC71, f"Added to **{safe_name}**: {query}")
            await ctx.send(embed=embed)
        
        elif action == "remove":
            if not name or not query:
                embed = self._make_embed("❌ Missing Args", 0xE74C3C, "Usage: `alpha playlist remove <name> <song>`")
                await ctx.send(embed=embed)
                return
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()[:50]
            playlist_file = os.path.join(playlists_dir, f"{safe_name}.txt")
            if not os.path.exists(playlist_file):
                embed = self._make_embed("❌ Not Found", 0xE74C3C, f"Playlist **{safe_name}** not found")
                await ctx.send(embed=embed)
                return
            with open(playlist_file, "r") as f:
                lines = f.readlines()
            with open(playlist_file, "w") as f:
                for line in lines:
                    if query.lower() not in line.strip().lower():
                        f.write(line)
            embed = self._make_embed("➖ Removed", 0xF39C12, f"Removed from **{safe_name}**: {query}")
            await ctx.send(embed=embed)
        
        elif action in ("save", "savequeue"):
            if not name:
                embed = self._make_embed("❌ No Name", 0xE74C3C, "Usage: `alpha playlist save <name>`")
                await ctx.send(embed=embed)
                return
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()[:50]
            playlist_file = os.path.join(playlists_dir, f"{safe_name}.txt")
            if not os.path.exists(playlist_file):
                embed = self._make_embed("❌ Not Found", 0xE74C3C, f"Playlist **{safe_name}** not found")
                await ctx.send(embed=embed)
                return
            player = self._get_player(ctx.guild.id)
            tracks: list[Track] = []
            if player.current:
                tracks.append(player.current)
            tracks.extend(player.queue)
            if not tracks:
                embed = self._make_embed("❌ Empty Queue", 0xE74C3C, "Nothing in the queue to save")
                await ctx.send(embed=embed)
                return
            with open(playlist_file, "a") as f:
                for t in tracks:
                    f.write(f"{t.title}\n")
            embed = self._make_embed(
                "💾 Queue Saved", 0x2ECC71,
                f"Saved **{len(tracks)}** track(s) from the queue to **{safe_name}**"
            )
            await ctx.send(embed=embed)

        elif action == "play":
            if not name:
                embed = self._make_embed("❌ No Name", 0xE74C3C, "Provide a playlist name")
                await ctx.send(embed=embed)
                return
            if not ctx.author.voice:
                embed = self._make_embed("❌ Not in VC", 0xE74C3C, "You must be in a voice channel")
                await ctx.send(embed=embed)
                return
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()[:50]
            playlist_file = os.path.join(playlists_dir, f"{safe_name}.txt")
            if not os.path.exists(playlist_file):
                embed = self._make_embed("❌ Not Found", 0xE74C3C, f"Playlist **{safe_name}** not found")
                await ctx.send(embed=embed)
                return
            
            with open(playlist_file, "r") as f:
                songs = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            
            if not songs:
                embed = self._make_embed("❌ Empty", 0xE74C3C, f"Playlist **{safe_name}** is empty")
                await ctx.send(embed=embed)
                return
            
            if not ctx.voice_client:
                await ctx.author.voice.channel.connect()
            
            player = self._get_player(ctx.guild.id)
            self._remember_text_channel(player, ctx)
            
            added = 0
            for song in songs[:20]:
                track = await self._fetch_track(song, ctx.author)
                if track:
                    player.queue.append(track)
                    added += 1
            
            embed = self._make_embed("🎶 Playlist Queued", 0x9B59B6, f"Added **{added}** songs from **{safe_name}** to queue")
            await ctx.send(embed=embed)
            
            if not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
                await self._play_next(ctx.guild.id)
        
        elif action == "list":
            if not name:
                playlists = [f.replace(".txt", "") for f in os.listdir(playlists_dir) if f.endswith(".txt")]
                embed = discord.Embed(color=0x9B59B6)
                embed.set_author(name="🎶 All Playlists", icon_url=None)
                embed.description = "\n".join(f"`{p}`" for p in playlists) if playlists else "No playlists yet"
                await ctx.send(embed=embed)
                return
            safe_name = "".join(c for c in name if c.isalnum() or c in " _-").strip()[:50]
            playlist_file = os.path.join(playlists_dir, f"{safe_name}.txt")
            if not os.path.exists(playlist_file):
                embed = self._make_embed("❌ Not Found", 0xE74C3C, f"Playlist **{safe_name}** not found")
                await ctx.send(embed=embed)
                return
            with open(playlist_file, "r") as f:
                songs = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            embed = discord.Embed(color=0x9B59B6)
            embed.set_author(name=f"🎶 {safe_name}", icon_url=None)
            embed.description = "\n".join(f"`{i+1}.` {s}" for i, s in enumerate(songs[:20]))
            if len(songs) > 20:
                embed.set_footer(text=f"… and {len(songs) - 20} more")
            await ctx.send(embed=embed)
        
        else:
            embed = self._make_embed("❌ Invalid Action", 0xE74C3C, "Use: create, delete, add, remove, save, play, list")
            await ctx.send(embed=embed)

    @commands.command(name="refresh")
    @perms_or_developer(administrator=True)
    async def refresh(self, ctx: commands.Context) -> None:
        """Refresh yt-dlp cookies. Usage: alpha refresh"""
        cookies_file = "cookies.txt"
        
        if not os.path.exists(cookies_file):
            embed = discord.Embed(color=0xE74C3C)
            embed.set_author(name="❌ No Cookies File")
            embed.description = "No `cookies.txt` file found in bot directory.\nCreate one with YouTube cookies for age-restricted content."
            await ctx.send(embed=embed)
            return

        if os.path.getsize(cookies_file) == 0:
            embed = discord.Embed(color=0xE74C3C)
            embed.set_author(name="❌ Empty Cookies")
            embed.description = "`cookies.txt` is empty. Please add valid YouTube cookies."
            await ctx.send(embed=embed)
            return

        ydl_opts = get_ytdl_opts()
        if "cookiefile" in ydl_opts:
            embed = discord.Embed(color=0x2ECC71)
            embed.set_author(name="✅ Cookies Refreshed")
            embed.description = "yt-dlp cookies have been **refreshed** and are active.\n\nAge-restricted content should now work."
            await ctx.send(embed=embed)
        else:
            embed = discord.Embed(color=0xF39C12)
            embed.set_author(name="⚠️ Cookies Not Active")
            embed.description = "Cookies file exists but is not being used.\nPlease check the file format."
            await ctx.send(embed=embed)

    @refresh.error
    async def refresh_error(self, ctx: commands.Context, error) -> None:
        if isinstance(error, commands.MissingPermissions):
            embed = self._make_embed("❌ Permission Denied", 0xE74C3C, "You need **Administrator** permission.")
            await ctx.send(embed=embed)

    @commands.command(name="slowed")
    async def slowed(self, ctx: commands.Context) -> None:
        """Toggle slowed + reverb effect. Usage: alpha slowed"""
        if not ctx.voice_client or not (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            embed = self._make_embed("❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing")
            await ctx.send(embed=embed)
            return

        player = self._get_player(ctx.guild.id)
        player.slowed = not player.slowed
        state = "**enabled**" if player.slowed else "**disabled**"
        embed = self._make_embed("🐌 Slowed + Reverb", 0x9B59B6, f"Slowed effect {state}")
        await ctx.send(embed=embed)

    @app_commands.command(name="slowed", description="Toggle slowed + reverb effect")
    async def slash_slowed(self, interaction: discord.Interaction) -> None:
        """Slash command for slowed effect."""
        if not interaction.guild or not interaction.guild.voice_client:
            await interaction.response.send_message(
                embed=self._make_embed("❌ Not in VC", 0xE74C3C, "Bot is not in a voice channel"),
                ephemeral=True
            )
            return
        if not (interaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
            await interaction.response.send_message(
                embed=self._make_embed("❌ Nothing Playing", 0xE74C3C, "Nothing is currently playing"),
                ephemeral=True
            )
            return

        player = self._get_player(interaction.guild_id)
        player.slowed = not player.slowed
        state = "**enabled**" if player.slowed else "**disabled**"
        await interaction.response.send_message(
            embed=self._make_embed("🐌 Slowed + Reverb", 0x9B59B6, f"Slowed effect {state}")
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Music(bot))

# ====================== KEEP ALIVE (for hosting platforms) ======================
app = Flask("")

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
    keep_alive()									                                     
    bot.run("MTU0ODY1MjUwNDY1NTMzMTQwOQ.GqD8h1.6W1LyIbWtzjDY_wZ7Fh2nvyBnQ1qp5qp4Cdn7Q")	 
													
