"""Application bootstrap for the VLG Discord bot."""

import os
import traceback
from threading import Thread

import discord
from discord import app_commands
from flask import Flask

from vlg_bot.config import PORT, TOKEN, TRUSTED_DEV_IDS
from vlg_bot.moderation import ModerationManager
from vlg_bot.music import MusicManager


intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True
intents.voice_states = True

bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

music_manager = MusicManager(bot)
moderation_manager = ModerationManager(bot)

music_manager.setup(tree)
moderation_manager.setup(tree)

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot is online and active!"


def keep_alive() -> None:
    thread = Thread(target=lambda: app.run(host="0.0.0.0", port=PORT), daemon=True)
    thread.start()


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await tree.sync()
        print(f"Synced {len(synced)} commands.")
    except Exception:
        traceback.print_exc()


@bot.event
async def on_voice_state_update(member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
    await music_manager.on_voice_state_update(member, before, after)


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return
    if message.content.strip().lower() == "!help":
        await message.channel.send(
            "**VLG Bot Commands**\n"
            "`/play`, `/queue`, `/skip`, `/pause`, `/resume`, `/warn`, `/warnings`, `/timeout`, `/ban`"
        )


@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    print(f"App command error: {error}")
    try:
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ Something went wrong: `{error}`", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ Something went wrong: `{error}`", ephemeral=True)
    except Exception:
        pass


def main() -> None:
    token = TOKEN or os.environ.get("TOKEN")
    if not token:
        raise SystemExit("TOKEN environment variable is not set.")
    keep_alive()
    bot.run(token)


__all__ = ["main", "bot", "tree", "music_manager", "moderation_manager"]
