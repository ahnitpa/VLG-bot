"""
music.py: YouTube music for your Discord bot (slash commands, yt-dlp + FFmpeg).

Adapted from an open-source prefix-command cog so it works with your
`discord.Client` + `CommandTree` setup. Everything it needs is in this file.

How to use it in bot.py (right AFTER `tree = app_commands.CommandTree(bot)`):

    import music
    music.setup(bot, tree)

requirements.txt:
    discord.py[voice]
    yt-dlp
    imageio-ffmpeg
    flask
"""

import asyncio
import math
import os
import random
import shutil
import time
import traceback
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import discord
import yt_dlp
from discord import app_commands

# ============================================================
# SETTINGS
# ============================================================

# Bundled ffmpeg binary (from imageio-ffmpeg) so Render needs no Dockerfile.
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = "ffmpeg"

yt_dlp.utils.bug_reports_message = lambda *a, **k: ""

YTDL_OPTIONS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "source_address": "0.0.0.0",
}

# Cookies: Render Secret Files live in /etc/secrets (read-only), so copy the
# file somewhere writable first. A local cookies.txt also works.
COOKIE_SRC = "/etc/secrets/cookies.txt"
COOKIE_DST = "/tmp/cookies.txt"
if os.path.exists(COOKIE_SRC):
    shutil.copy(COOKIE_SRC, COOKIE_DST)
    YTDL_OPTIONS["cookiefile"] = COOKIE_DST
elif os.path.exists("cookies.txt"):
    YTDL_OPTIONS["cookiefile"] = "cookies.txt"


FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -filter:a asetrate=48000",
    "executable": FFMPEG_PATH,
}


# YouTube stream links expire; refresh them if a song waited this long (seconds).
STREAM_MAX_AGE = 300

LOOP_LABELS = {"off": "Off", "single": "Current track", "queue": "Whole queue"}

client: Optional[discord.Client] = None   # set by setup()


# ============================================================
# DATA MODELS
# ============================================================

@dataclass
class Track:
    title: str
    page_url: str
    stream_url: str
    duration: int
    requester: discord.Member
    fetched_at: float = field(default_factory=time.time)

    def fmt_duration(self) -> str:
        if not self.duration:
            return "Live / unknown"
        minutes, seconds = divmod(int(self.duration), 60)
        hours, minutes = divmod(minutes, 60)
        if hours:
            return f"{hours}:{minutes:02}:{seconds:02}"
        return f"{minutes}:{seconds:02}"


@dataclass
class GuildPlayer:
    queue: deque = field(default_factory=deque)
    current: Optional[Track] = None
    loop: str = "off"                      # "off" | "single" | "queue"
    volume: float = 0.5
    text_channel: Optional[discord.abc.Messageable] = None
    skip_votes: set = field(default_factory=set)
    skip_flag: bool = False                # True while a skip/replay is in progress
    auto_paused: bool = False              # True if we paused because the channel emptied

    def reset(self) -> None:
        self.queue.clear()
        self.current = None
        self.loop = "off"
        self.skip_votes.clear()
        self.skip_flag = False
        self.auto_paused = False


players: dict[int, GuildPlayer] = {}


def get_player(guild_id: int) -> GuildPlayer:
    if guild_id not in players:
        players[guild_id] = GuildPlayer()
    return players[guild_id]


# ============================================================
# HELPERS
# ============================================================

def make_embed(title: str, color: int, description: str = "") -> discord.Embed:
    embed = discord.Embed(color=color)
    embed.set_author(name=title)
    if description:
        embed.description = description
    return embed


def now_playing_embed(track: Track, player: GuildPlayer) -> discord.Embed:
    embed = discord.Embed(color=0x1DB954)
    embed.set_author(name="Now Playing")
    embed.description = f"[{track.title}]({track.page_url})"
    embed.add_field(name="Duration", value=track.fmt_duration(), inline=True)
    embed.add_field(name="Requested by", value=track.requester.mention, inline=True)
    embed.add_field(name="Loop", value=LOOP_LABELS[player.loop], inline=True)
    embed.add_field(name="Volume", value=f"{int(player.volume * 100)}%", inline=True)
    return embed


def friendly_error(error: Exception) -> str:
    text = str(error)
    low = text.lower()
    if "sign in to confirm" in low or "not a bot" in low:
        return ("YouTube is asking for a sign-in. Refresh the cookies "
                "(fresh export from an incognito window) and update yt-dlp.")
    if "page needs to be reloaded" in low:
        return ("YouTube rejected the session. Update yt-dlp and re-export "
                "fresh cookies.")
    if "private video" in low:
        return "That video is private."
    if "video unavailable" in low or "not available" in low:
        return "That video is unavailable."
    if "age" in low and "restrict" in low:
        return "That video is age-restricted and needs valid cookies."
    if "unsupported url" in low:
        return "I can only play YouTube links or search terms."
    return text.replace("ERROR: ", "")[:300]


def _extract_sync(query: str) -> dict:
    with yt_dlp.YoutubeDL(YTDL_OPTIONS) as ydl:
        return ydl.extract_info(query, download=False)


async def extract(query: str) -> dict:
    """Look up a URL or search term without blocking the bot."""
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(None, _extract_sync, query)
    if data is None:
        raise ValueError("Nothing found.")
    if "entries" in data:
        entries = [e for e in data["entries"] if e]
        if not entries:
            raise ValueError("No results found.")
        data = entries[0]
    return data


async def fetch_track(query: str, requester: discord.Member) -> Track:
    search = query if query.startswith("http") else f"ytsearch1:{query}"
    data = await extract(search)
    return Track(
        title=data.get("title", "Unknown title"),
        page_url=data.get("webpage_url") or search,
        stream_url=data["url"],
        duration=data.get("duration") or 0,
        requester=requester,
    )


async def notify(player: GuildPlayer, embed: discord.Embed) -> None:
    """Best-effort status message. Must never break playback."""
    if player.text_channel is None:
        return
    try:
        await player.text_channel.send(embed=embed)
    except Exception as e:
        print(f"Could not post music status: {e}")


# ============================================================
# PLAYBACK ENGINE
# ============================================================

async def play_next(guild_id: int) -> None:
    try:
        await _play_next(guild_id)
    except Exception:
        print(f"Music queue error in guild {guild_id}:")
        traceback.print_exc()


async def _play_next(guild_id: int) -> None:
    player = get_player(guild_id)
    guild = client.get_guild(guild_id)
    vc = guild.voice_client if guild else None

    if vc is None or not vc.is_connected():
        player.reset()
        return
    if vc.is_playing() or vc.is_paused():
        return

    # Handle looping for the track that just finished
    finished = player.current
    if finished and not player.skip_flag:
        if player.loop == "single":
            player.queue.appendleft(finished)
        elif player.loop == "queue":
            player.queue.append(finished)
    player.skip_flag = False
    player.skip_votes.clear()
    player.current = None

    if not player.queue:
        if finished is not None:
            await notify(player, make_embed(
                "🎵 Queue Finished", 0x95A5A6, "No more tracks in the queue."))
        return

    track = player.queue.popleft()
    player.current = track

    # Stream links expire, so refresh the link if this song waited a while
    if time.time() - track.fetched_at > STREAM_MAX_AGE:
        try:
            data = await extract(track.page_url)
            track.stream_url = data["url"]
            track.fetched_at = time.time()
        except Exception as e:
            print(f"Could not refresh stream link for {track.title}: {e}")

    def after(error: Optional[Exception]) -> None:
        if error:
            print(f"Playback error in guild {guild_id}: {error}")
        asyncio.run_coroutine_threadsafe(play_next(guild_id), client.loop)

    try:
        audio = discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTIONS)
        vc.play(discord.PCMVolumeTransformer(audio, volume=player.volume), after=after)
    except Exception as e:
        # Only failing to START a track is handled here; skip to the next one.
        print(f"Could not start {track.title}: {e}")
        player.current = None
        await notify(player, make_embed(
            "❌ Playback Error", 0xE74C3C,
            f"Couldn't play **{track.title}**: `{str(e)[:200]}`. Skipping."))
        await _play_next(guild_id)
        return

    await notify(player, now_playing_embed(track, player))


def do_skip(vc: discord.VoiceClient, player: GuildPlayer) -> None:
    player.skip_flag = True    # stops "loop" from putting the track back
    vc.stop()                  # the after-callback starts the next song


# ============================================================
# STAY IN THE CHANNEL WHEN EMPTY (silent, not leaving)
# ============================================================

async def on_voice_state_update(member: discord.Member,
                                before: discord.VoiceState,
                                after: discord.VoiceState) -> None:
    try:
        # The bot itself was disconnected (kicked, channel deleted...): clear state
        if client.user and member.id == client.user.id:
            if after.channel is None:
                player = players.get(member.guild.id)
                if player:
                    player.reset()
            return

        if member.bot:
            return

        guild = member.guild
        vc = guild.voice_client
        if vc is None:
            return
        player = players.get(guild.id)

        left_bot_channel = before.channel == vc.channel and after.channel != vc.channel
        joined_bot_channel = after.channel == vc.channel and before.channel != vc.channel

        if left_bot_channel:
            if player:
                player.skip_votes.discard(member.id)
            humans = [m for m in vc.channel.members if not m.bot]
            # Nobody left: go silent (pause) but stay connected
            if not humans and player and vc.is_playing():
                vc.pause()
                player.auto_paused = True

        elif joined_bot_channel:
            # Someone came back: continue where we left off
            if player and player.auto_paused and vc.is_paused():
                vc.resume()
            if player:
                player.auto_paused = False
    except Exception:
        traceback.print_exc()


# ============================================================
# SLASH COMMANDS
# ============================================================

@app_commands.command(name="join", description="Make the bot join your voice channel")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            "❌ You need to be in a voice channel first!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client
    get_player(interaction.guild.id).text_channel = interaction.channel

    try:
        if vc is None:
            await channel.connect()
            await interaction.response.send_message(f"✅ Joined **{channel.name}**")
        elif vc.channel == channel:
            await interaction.response.send_message(
                "I'm already in your voice channel!", ephemeral=True)
        else:
            await vc.move_to(channel)
            await interaction.response.send_message(f"Moved to **{channel.name}**")
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to join that channel. "
            "I need **Connect** and **Speak**.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"Failed to join: `{e}`", ephemeral=True)


@app_commands.command(name="leave", description="Make the bot leave the voice channel")
async def leave(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(
            "I'm not in a voice channel.", ephemeral=True)
        return

    get_player(interaction.guild.id).reset()
    await vc.disconnect()
    await interaction.response.send_message("Left the voice channel.")


@app_commands.command(name="play", description="Play a song from SoundCloud (URL only)")
@app_commands.describe(query="SoundCloud URL")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send(
            "❌ You need to be in a voice channel!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    vc = interaction.guild.voice_client
    try:
        if vc is None:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)
    except Exception as e:
        await interaction.followup.send(f"❌ Could not join voice channel: `{e}`")
        return

    try:
        track = await fetch_track(query, interaction.user)
    except Exception as e:
        traceback.print_exc()
        await interaction.followup.send(f"❌ Couldn't get that song: `{friendly_error(e)}`")
        return

    player = get_player(interaction.guild.id)
    player.text_channel = interaction.channel
    player.queue.append(track)

    if vc.is_playing() or vc.is_paused():
        embed = discord.Embed(color=0x1DB954)
        embed.set_author(name="➕ Added to Queue")
        embed.description = f"[{track.title}]({track.page_url})"
        embed.add_field(name="Position", value=f"**{len(player.queue)}**", inline=True)
        embed.add_field(name="Duration", value=track.fmt_duration(), inline=True)
        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(f"🔎 Found **{track.title}**")
        await play_next(interaction.guild.id)


@app_commands.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_playing():
        vc.pause()
        get_player(interaction.guild.id).auto_paused = False
        await interaction.response.send_message("⏸️ Paused.")
    else:
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)


@app_commands.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc and vc.is_paused():
        vc.resume()
        get_player(interaction.guild.id).auto_paused = False
        await interaction.response.send_message("▶️ Resumed.")
    else:
        await interaction.response.send_message("Nothing is paused.", ephemeral=True)


@app_commands.command(name="stop", description="Stop playing and clear the queue")
async def stop(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    if vc is None:
        await interaction.response.send_message(
            "I'm not in a voice channel.", ephemeral=True)
        return

    get_player(interaction.guild.id).reset()
    vc.stop()
    await interaction.response.send_message("⏹️ Stopped and cleared the queue.")


@app_commands.command(name="skip", description="Skip the current song (vote skip)")
async def skip(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    player = get_player(interaction.guild.id)

    if vc is None or not player.current or not (vc.is_playing() or vc.is_paused()):
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
        return

    user_vc = interaction.user.voice
    if not user_vc or user_vc.channel != vc.channel:
        await interaction.response.send_message(
            "❌ You must be in the same voice channel as me.", ephemeral=True)
        return

    track = player.current
    is_admin = interaction.user.guild_permissions.administrator

    # Requester and admins skip instantly
    if interaction.user.id == track.requester.id or is_admin:
        do_skip(vc, player)
        await interaction.response.send_message(f"⏭️ Skipped **{track.title}**")
        return

    # Everyone else: vote skip at 50% of the people listening
    humans = [m for m in vc.channel.members if not m.bot]
    needed = math.ceil(len(humans) / 2)

    if interaction.user.id in player.skip_votes:
        player.skip_votes.discard(interaction.user.id)
        await interaction.response.send_message(
            f"Vote removed. **{len(player.skip_votes)}/{needed}** votes.")
        return

    player.skip_votes.add(interaction.user.id)
    if len(player.skip_votes) >= needed:
        do_skip(vc, player)
        await interaction.response.send_message(
            f"⏭️ Vote passed ({len(player.skip_votes)}/{needed}). Skipped **{track.title}**")
    else:
        await interaction.response.send_message(
            f"🗳️ Vote added: **{len(player.skip_votes)}/{needed}** needed to skip.")


@app_commands.command(name="queue", description="Show the current queue")
async def queue_cmd(interaction: discord.Interaction):
    player = get_player(interaction.guild.id)
    if not player.current and not player.queue:
        await interaction.response.send_message("The queue is empty.", ephemeral=True)
        return

    embed = discord.Embed(color=0x1DB954)
    embed.set_author(name="Music Queue")
    if player.current:
        embed.add_field(
            name="Now Playing",
            value=f"`{player.current.title}` [{player.current.fmt_duration()}] "
                  f"- {player.current.requester.mention}",
            inline=False)
    if player.queue:
        lines = "\n".join(
            f"`{i + 1}.` {t.title} [{t.fmt_duration()}]"
            for i, t in enumerate(list(player.queue)[:10]))
        if len(player.queue) > 10:
            lines += f"\n...and {len(player.queue) - 10} more"
        embed.add_field(name=f"Up next ({len(player.queue)})", value=lines, inline=False)
    embed.add_field(name="Loop", value=LOOP_LABELS[player.loop], inline=True)
    embed.add_field(name="Volume", value=f"{int(player.volume * 100)}%", inline=True)
    await interaction.response.send_message(embed=embed)


@app_commands.command(name="nowplaying", description="Show what's currently playing")
async def nowplaying(interaction: discord.Interaction):
    player = get_player(interaction.guild.id)
    if not player.current:
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
        return
    await interaction.response.send_message(embed=now_playing_embed(player.current, player))


@app_commands.command(name="volume", description="Set the music volume (0-200%)")
@app_commands.describe(level="Volume from 0 to 200 (default is 50)")
async def volume(interaction: discord.Interaction, level: app_commands.Range[int, 0, 200]):
    player = get_player(interaction.guild.id)
    player.volume = level / 100
    vc = interaction.guild.voice_client
    if vc and vc.source:
        vc.source.volume = player.volume
    await interaction.response.send_message(f"🔊 Volume set to **{level}%**")


@app_commands.command(name="shuffle", description="Shuffle the queue")
async def shuffle(interaction: discord.Interaction):
    player = get_player(interaction.guild.id)
    if len(player.queue) < 2:
        await interaction.response.send_message(
            "Not enough tracks in the queue to shuffle.", ephemeral=True)
        return
    items = list(player.queue)
    random.shuffle(items)
    player.queue = deque(items)
    await interaction.response.send_message(f"🔀 Shuffled **{len(items)}** tracks.")


@app_commands.command(name="loop", description="Loop the current track or the whole queue")
@app_commands.describe(mode="What to loop")
@app_commands.choices(mode=[
    app_commands.Choice(name="Off", value="off"),
    app_commands.Choice(name="Current track", value="single"),
    app_commands.Choice(name="Whole queue", value="queue"),
])
async def loop_cmd(interaction: discord.Interaction, mode: app_commands.Choice[str]):
    player = get_player(interaction.guild.id)
    player.loop = mode.value
    await interaction.response.send_message(f"🔁 Loop: **{LOOP_LABELS[mode.value]}**")


@app_commands.command(name="remove", description="Remove a song from the queue")
@app_commands.describe(position="Position in the queue (see /queue)")
async def remove(interaction: discord.Interaction, position: int):
    player = get_player(interaction.guild.id)
    if not 1 <= position <= len(player.queue):
        await interaction.response.send_message("Invalid queue position.", ephemeral=True)
        return
    items = list(player.queue)
    removed = items.pop(position - 1)
    player.queue = deque(items)
    await interaction.response.send_message(f"🗑️ Removed **{removed.title}**")


@app_commands.command(name="clear", description="Clear the queue (keeps the current song)")
async def clear(interaction: discord.Interaction):
    player = get_player(interaction.guild.id)
    count = len(player.queue)
    player.queue.clear()
    await interaction.response.send_message(f"Cleared **{count}** track(s) from the queue.")


@app_commands.command(name="replay", description="Restart the current song")
async def replay(interaction: discord.Interaction):
    vc = interaction.guild.voice_client
    player = get_player(interaction.guild.id)
    if vc is None or not player.current or not (vc.is_playing() or vc.is_paused()):
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
        return

    player.queue.appendleft(player.current)
    do_skip(vc, player)
    await interaction.response.send_message(f"🔄 Replaying **{player.queue[0].title}**")


# ============================================================
# REGISTER EVERYTHING (called from bot.py)
# ============================================================

def setup(bot: discord.Client, tree: app_commands.CommandTree) -> None:
    global client
    client = bot
    bot.event(on_voice_state_update)

    for command in (join, leave, play, pause, resume, stop, skip, queue_cmd,
                    nowplaying, volume, shuffle, loop_cmd, remove, clear, replay):
        tree.add_command(command)
