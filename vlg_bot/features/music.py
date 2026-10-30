"""Music feature module."""

import asyncio
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Optional

import discord
import yt_dlp
from discord import app_commands

YTDL_OPTIONS = {"format": "bestaudio/best", "quiet": True, "no_warnings": True, "source_address": "0.0.0.0"}
FFMPEG_OPTIONS = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5", "options": "-vn"}


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
        total_seconds = int(self.duration)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02}:{seconds:02}"
        return f"{minutes}:{seconds:02}"


@dataclass
class GuildPlayer:
    queue: deque[Track] = field(default_factory=deque)
    current: Optional[Track] = None
    loop: str = "off"
    volume: float = 0.5
    skip_votes: set[int] = field(default_factory=set)
    skip_flag: bool = False
    auto_paused: bool = False
    text_channel: Optional[discord.abc.Messageable] = None

    def reset(self) -> None:
        self.queue.clear()
        self.current = None
        self.loop = "off"
        self.skip_votes.clear()
        self.skip_flag = False
        self.auto_paused = False


class MusicManager:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.players: dict[int, GuildPlayer] = {}

    def get_player(self, guild_id: int) -> GuildPlayer:
        if guild_id not in self.players:
            self.players[guild_id] = GuildPlayer()
        return self.players[guild_id]

    async def extract(self, query: str, allow_playlist: bool = False) -> dict:
        opts = YTDL_OPTIONS.copy()
        if not allow_playlist:
            opts["noplaylist"] = True
        loop = asyncio.get_running_loop()
        with yt_dlp.YoutubeDL(opts) as ydl:
            data = await loop.run_in_executor(None, lambda: ydl.extract_info(query, download=False))
        if data is None:
            raise ValueError("Nothing found.")
        return data

    async def fetch_track(self, query: str, requester: discord.Member) -> Track:
        search = query if query.startswith("http") else f"ytsearch1:{query}"
        data = await self.extract(search, allow_playlist=False)
        if "entries" in data:
            entries = [item for item in data["entries"] if item]
            if not entries:
                raise ValueError("No results found.")
            data = entries[0]
        return Track(
            title=data.get("title", "Unknown title"),
            page_url=data.get("webpage_url") or search,
            stream_url=data["url"],
            duration=data.get("duration") or 0,
            requester=requester,
        )

    def make_embed(self, title: str, description: str = "", color: int = 0x5865F2) -> discord.Embed:
        return discord.Embed(title=title, description=description, color=color)

    async def notify(self, player: GuildPlayer, embed: discord.Embed) -> None:
        if player.text_channel is None:
            return
        try:
            await player.text_channel.send(embed=embed)
        except Exception:
            pass

    def do_skip(self, vc: discord.VoiceClient, player: GuildPlayer) -> None:
        if vc is None or player is None or player.current is None:
            return
        player.skip_flag = True
        player.skip_votes.clear()
        try:
            vc.stop()
        except Exception:
            pass

    async def play_next(self, guild_id: int) -> None:
        player = self.get_player(guild_id)
        guild = self.bot.get_guild(guild_id)
        vc = guild.voice_client if guild else None
        if vc is None or not vc.is_connected():
            player.reset()
            return
        if vc.is_playing() or vc.is_paused():
            return

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
                await self.notify(player, self.make_embed("🎵 Queue Finished", "No more tracks in the queue.", 0x95A5A6))
            return

        track = player.queue.popleft()
        player.current = track
        if time.time() - track.fetched_at > 300:
            try:
                refreshed = await self.extract(track.page_url, allow_playlist=False)
                if "entries" in refreshed:
                    refreshed = refreshed["entries"][0]
                track.stream_url = refreshed["url"]
                track.fetched_at = time.time()
            except Exception:
                pass

        def after(error: Optional[Exception]) -> None:
            if error:
                print(f"Playback error in guild {guild_id}: {error}")
            asyncio.run_coroutine_threadsafe(self.play_next(guild_id), self.bot.loop)

        try:
            source = discord.FFmpegPCMAudio(track.stream_url, **FFMPEG_OPTIONS)
            vc.play(discord.PCMVolumeTransformer(source, volume=player.volume), after=after)
            if vc.channel:
                status = track.title[:45] + ("..." if len(track.title) > 45 else "")
                try:
                    await vc.channel.edit(status=status)
                except Exception:
                    pass
            await self.notify(player, self.make_embed("🎵 Now Playing", f"**{track.title}**\nRequested by {track.requester.mention}\nDuration: {track.fmt_duration()}", 0x1DB954))
        except Exception as exc:
            player.current = None
            await self.notify(player, self.make_embed("❌ Playback Error", f"Couldn't play **{track.title}**: `{exc}`. Skipping.", 0xE74C3C))
            await self.play_next(guild_id)

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        if self.bot.user and member.id == self.bot.user.id:
            if after.channel is None:
                player = self.players.get(member.guild.id)
                if player:
                    player.reset()
            return
        if member.bot:
            return
        guild = member.guild
        vc = guild.voice_client
        if vc is None:
            return
        player = self.players.get(guild.id)
        left_bot_channel = before.channel == vc.channel and after.channel != vc.channel
        joined_bot_channel = after.channel == vc.channel and before.channel != vc.channel
        if left_bot_channel:
            if player:
                player.skip_votes.discard(member.id)
            humans = [m for m in vc.channel.members if not m.bot]
            if not humans and player and vc.is_playing():
                vc.pause()
                player.auto_paused = True
        elif joined_bot_channel:
            if player and player.auto_paused and vc.is_paused():
                vc.resume()
            if player:
                player.auto_paused = False

    def setup(self, tree: app_commands.CommandTree) -> None:
        if getattr(tree, "_vlg_music_setup", False):
            return
        tree._vlg_music_setup = True
        registered_names = set(getattr(tree, "_vlg_registered_command_names", set()))
        tree._vlg_registered_command_names = registered_names

        @tree.command(name="join", description="Join your voice channel")
        async def join(interaction: discord.Interaction):
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.response.send_message("❌ You need to be in a voice channel first.", ephemeral=True)
                return
            channel = interaction.user.voice.channel
            vc = interaction.guild.voice_client
            player = self.get_player(interaction.guild.id)
            player.text_channel = interaction.channel
            try:
                if vc is None:
                    await channel.connect()
                    await interaction.response.send_message(f"✅ Joined **{channel.name}**")
                elif vc.channel == channel:
                    await interaction.response.send_message("Already here.", ephemeral=True)
                else:
                    await vc.move_to(channel)
                    await interaction.response.send_message(f"Moved to **{channel.name}**")
            except discord.Forbidden:
                await interaction.response.send_message("❌ I don't have permission to join that channel.", ephemeral=True)

        @tree.command(name="leave", description="Leave the voice channel")
        async def leave(interaction: discord.Interaction):
            vc = interaction.guild.voice_client
            if vc is None:
                await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
                return
            self.get_player(interaction.guild.id).reset()
            await vc.disconnect()
            await interaction.response.send_message("Left the voice channel.")

        @tree.command(name="play", description="Play a track or search term")
        @app_commands.describe(query="Song title or URL")
        async def play(interaction: discord.Interaction, query: str):
            await interaction.response.defer()
            if not interaction.user.voice or not interaction.user.voice.channel:
                await interaction.followup.send("❌ You need to be in a voice channel first.", ephemeral=True)
                return
            channel = interaction.user.voice.channel
            vc = interaction.guild.voice_client
            try:
                if vc is None:
                    vc = await channel.connect()
                elif vc.channel != channel:
                    await vc.move_to(channel)
            except Exception as exc:
                await interaction.followup.send(f"❌ Failed to join voice: `{exc}`", ephemeral=True)
                return
            player = self.get_player(interaction.guild.id)
            player.text_channel = interaction.channel
            try:
                track = await self.fetch_track(query, interaction.user)
            except Exception as exc:
                await interaction.followup.send(f"❌ Couldn't find that track: `{exc}`", ephemeral=True)
                return
            player.queue.append(track)
            await interaction.followup.send(embed=self.make_embed("➕ Added to Queue", f"**{track.title}**\nQueue position: {len(player.queue)}", 0x1DB954))
            if not vc.is_playing() and not vc.is_paused():
                await self.play_next(interaction.guild.id)

        @tree.command(name="pause", description="Pause the current track")
        async def pause(interaction: discord.Interaction):
            vc = interaction.guild.voice_client
            if vc and vc.is_playing():
                vc.pause()
                await interaction.response.send_message("⏸️ Paused.")
            else:
                await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)

        @tree.command(name="resume", description="Resume playback")
        async def resume(interaction: discord.Interaction):
            vc = interaction.guild.voice_client
            if vc and vc.is_paused():
                vc.resume()
                await interaction.response.send_message("▶️ Resumed.")
            else:
                await interaction.response.send_message("Nothing is paused.", ephemeral=True)

        @tree.command(name="skip", description="Skip the current track")
        async def skip(interaction: discord.Interaction):
            vc = interaction.guild.voice_client
            player = self.get_player(interaction.guild.id)
            if vc is None or not player.current or not (vc.is_playing() or vc.is_paused()):
                await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
                return
            if interaction.user.id == player.current.requester.id or interaction.user.guild_permissions.administrator:
                self.do_skip(vc, player)
                await interaction.response.send_message(f"⏭️ Skipped **{player.current.title}**")
                return
            humans = [m for m in vc.channel.members if not m.bot]
            needed = max(1, math.ceil(len(humans) / 2))
            player.skip_votes.add(interaction.user.id)
            if len(player.skip_votes) >= needed:
                self.do_skip(vc, player)
                await interaction.response.send_message(f"⏭️ Vote passed. Skipped **{player.current.title}**")
            else:
                await interaction.response.send_message(f"🗳️ Skip vote added: {len(player.skip_votes)}/{needed}")

        @tree.command(name="queue", description="Show the current queue")
        async def queue_cmd(interaction: discord.Interaction):
            player = self.get_player(interaction.guild.id)
            if not player.current and not player.queue:
                await interaction.response.send_message("Queue is empty.", ephemeral=True)
                return
            lines = []
            if player.current:
                lines.append(f"Now: **{player.current.title}** [{player.current.fmt_duration()}]")
            for idx, item in enumerate(list(player.queue)[:10], start=1):
                lines.append(f"{idx}. {item.title} [{item.fmt_duration()}]")
            if len(player.queue) > 10:
                lines.append(f"...and {len(player.queue) - 10} more")
            await interaction.response.send_message("\n".join(lines))

        @tree.command(name="nowplaying", description="Show the current track")
        async def nowplaying(interaction: discord.Interaction):
            player = self.get_player(interaction.guild.id)
            if not player.current:
                await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
                return
            await interaction.response.send_message(embed=self.make_embed("🎵 Now Playing", f"**{player.current.title}**\nDuration: {player.current.fmt_duration()}\nRequested by {player.current.requester.mention}", 0x1DB954))

        @tree.command(name="volume", description="Set volume from 0 to 200")
        @app_commands.describe(level="Volume percent")
        async def volume(interaction: discord.Interaction, level: app_commands.Range[int, 0, 200]):
            player = self.get_player(interaction.guild.id)
            player.volume = level / 100
            vc = interaction.guild.voice_client
            if vc and vc.source:
                vc.source.volume = player.volume
            await interaction.response.send_message(f"🔊 Volume set to **{level}%**")

        @tree.command(name="shuffle", description="Shuffle the queue")
        async def shuffle(interaction: discord.Interaction):
            player = self.get_player(interaction.guild.id)
            if len(player.queue) < 2:
                await interaction.response.send_message("Need at least 2 tracks to shuffle.", ephemeral=True)
                return
            items = list(player.queue)
            random.shuffle(items)
            player.queue = deque(items)
            await interaction.response.send_message(f"🔀 Shuffled **{len(items)}** tracks.")

        @tree.command(name="loop", description="Set loop mode")
        @app_commands.choices(mode=[
            app_commands.Choice(name="Off", value="off"),
            app_commands.Choice(name="Current track", value="single"),
            app_commands.Choice(name="Queue", value="queue"),
        ])
        async def loop_cmd(interaction: discord.Interaction, mode: app_commands.Choice[str]):
            player = self.get_player(interaction.guild.id)
            player.loop = mode.value
            await interaction.response.send_message(f"🔁 Loop set to **{mode.name}**")

        @tree.command(name="remove", description="Remove a track from the queue")
        @app_commands.describe(position="Queue position")
        async def remove(interaction: discord.Interaction, position: int):
            player = self.get_player(interaction.guild.id)
            if not 1 <= position <= len(player.queue):
                await interaction.response.send_message("Invalid queue position.", ephemeral=True)
                return
            items = list(player.queue)
            removed = items.pop(position - 1)
            player.queue = deque(items)
            await interaction.response.send_message(f"🗑️ Removed **{removed.title}**")

        @tree.command(name="clear", description="Clear the queue without stopping current song")
        async def clear(interaction: discord.Interaction):
            player = self.get_player(interaction.guild.id)
            count = len(player.queue)
            player.queue.clear()
            await interaction.response.send_message(f"Cleared **{count}** pending track(s).")

        @tree.command(name="replay", description="Replay the current track")
        async def replay(interaction: discord.Interaction):
            vc = interaction.guild.voice_client
            player = self.get_player(interaction.guild.id)
            if vc is None or not player.current or not (vc.is_playing() or vc.is_paused()):
                await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
                return
            player.queue.appendleft(player.current)
            self.do_skip(vc, player)
            await interaction.response.send_message(f"🔄 Replaying **{player.current.title}**")

        for command in (join, leave, play, pause, resume, skip, queue_cmd, nowplaying, volume, shuffle, loop_cmd, remove, clear, replay):
            if command.name in registered_names:
                continue
            tree.add_command(command)
            registered_names.add(command.name)


def create_music_manager(bot: discord.Client) -> MusicManager:
    return MusicManager(bot)


__all__ = ["Track", "GuildPlayer", "MusicManager", "create_music_manager"]
