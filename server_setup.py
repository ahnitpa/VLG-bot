import asyncio
import os
import re
import sqlite3
from typing import Any

import discord
from discord import app_commands

from shared import is_authorized

DB_PATH = os.environ.get("DB_PATH") or os.environ.get("BOT_DB_PATH") or "bot.db"
DEFAULT_PREFIX = "!v"
DEFAULT_WELCOME_MESSAGE = "Welcome {user} to {server}!"


def _connect_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    conn = _connect_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id INTEGER PRIMARY KEY,
            log_channel_id INTEGER,
            moderation_channel_id INTEGER,
            welcome_channel_id INTEGER,
            welcome_enabled INTEGER NOT NULL DEFAULT 1,
            welcome_message TEXT NOT NULL DEFAULT 'Welcome {user} to {server}!',
            prefix TEXT NOT NULL DEFAULT '!v'
        )
        """
    )
    conn.commit()
    conn.close()


def get_server_config(guild_id: int) -> dict[str, Any]:
    ensure_schema()
    with _connect_db() as conn:
        row = conn.execute(
            "SELECT log_channel_id, moderation_channel_id, welcome_channel_id, welcome_enabled, welcome_message, prefix FROM guild_config WHERE guild_id = ?",
            (guild_id,),
        ).fetchone()

    if row is None:
        return {
            "log_channel_id": None,
            "moderation_channel_id": None,
            "welcome_channel_id": None,
            "welcome_enabled": True,
            "welcome_message": DEFAULT_WELCOME_MESSAGE,
            "prefix": DEFAULT_PREFIX,
        }

    return {
        "log_channel_id": row["log_channel_id"],
        "moderation_channel_id": row["moderation_channel_id"],
        "welcome_channel_id": row["welcome_channel_id"],
        "welcome_enabled": bool(row["welcome_enabled"]),
        "welcome_message": row["welcome_message"] or DEFAULT_WELCOME_MESSAGE,
        "prefix": row["prefix"] or DEFAULT_PREFIX,
    }


def update_server_config(guild_id: int, **values: Any) -> None:
    ensure_schema()
    payload = {
        "guild_id": guild_id,
        "log_channel_id": values.get("log_channel_id"),
        "moderation_channel_id": values.get("moderation_channel_id"),
        "welcome_channel_id": values.get("welcome_channel_id"),
        "welcome_enabled": int(bool(values.get("welcome_enabled", True))),
        "welcome_message": values.get("welcome_message") or DEFAULT_WELCOME_MESSAGE,
        "prefix": values.get("prefix") or DEFAULT_PREFIX,
    }

    with _connect_db() as conn:
        conn.execute(
            """
            INSERT INTO guild_config (
                guild_id, log_channel_id, moderation_channel_id, welcome_channel_id,
                welcome_enabled, welcome_message, prefix
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET
                log_channel_id = excluded.log_channel_id,
                moderation_channel_id = excluded.moderation_channel_id,
                welcome_channel_id = excluded.welcome_channel_id,
                welcome_enabled = excluded.welcome_enabled,
                welcome_message = excluded.welcome_message,
                prefix = excluded.prefix
            """,
            (
                payload["guild_id"],
                payload["log_channel_id"],
                payload["moderation_channel_id"],
                payload["welcome_channel_id"],
                payload["welcome_enabled"],
                payload["welcome_message"],
                payload["prefix"],
            ),
        )
        conn.commit()


def _parse_channel_token(guild: discord.Guild, value: str) -> discord.abc.GuildChannel | None:
    text = value.strip()
    if not text or text.lower() in {"skip", "none", "cancel"}:
        return None

    match = re.search(r"<#(\d+)>", text)
    if match:
        channel_id = int(match.group(1))
        return guild.get_channel(channel_id)

    if text.isdigit():
        return guild.get_channel(int(text))

    lowered = text.lower()
    for channel in guild.channels:
        if channel.name.lower() == lowered:
            return channel
    return None


async def _prompt_for_response(bot: discord.Client, channel: discord.abc.Messageable, author_id: int, question: str, timeout: int = 120) -> str | None:
    await channel.send(question)

    def check(message: discord.Message) -> bool:
        return (
            message.author.id == author_id
            and message.channel.id == channel.id
            and message.content.strip() != ""
        )

    try:
        msg = await bot.wait_for("message", check=check, timeout=timeout)
        return msg.content.strip()
    except asyncio.TimeoutError:
        return None


async def handle_member_join(member: discord.Member) -> None:
    config = get_server_config(member.guild.id)
    if not config["welcome_enabled"]:
        return

    channel_id = config["welcome_channel_id"]
    if channel_id is None:
        return

    channel = member.guild.get_channel(channel_id)
    if channel is None:
        return

    message = config["welcome_message"].format(
        user=member.mention,
        member=member.mention,
        server=member.guild.name,
        username=member.name,
        guild=member.guild.name,
    )

    try:
        await channel.send(message)
    except discord.HTTPException:
        pass


async def _run_setup_wizard(interaction: discord.Interaction) -> None:
    if interaction.guild is None or interaction.user is None:
        await interaction.response.send_message("This setup command must be used in a server.", ephemeral=True)
        return

    channel = interaction.channel
    if channel is None:
        await interaction.response.send_message("I need a valid text channel to run the setup wizard.", ephemeral=True)
        return

    await interaction.response.send_message(
        "I’ll ask a few quick questions to set up this server. Reply with `start` to begin or `cancel` to stop.",
        ephemeral=True,
    )

    start_reply = await _prompt_for_response(
        interaction.client,
        channel,
        interaction.user.id,
        "Type `start` to begin your server setup.",
        timeout=60,
    )

    if start_reply is None:
        await channel.send("Setup timed out. Run `/server-setup` again when you’re ready.")
        return

    if start_reply.lower() in {"cancel", "stop", "exit"}:
        await channel.send("Setup cancelled.")
        return

    if start_reply.lower() not in {"start", "begin", "go"}:
        await channel.send("I didn’t receive a valid start command. Setup cancelled.")
        return

    current = get_server_config(interaction.guild.id)

    log_answer = await _prompt_for_response(
        interaction.client,
        channel,
        interaction.user.id,
        "Q1: Which channel should receive bot log messages? Mention the channel, use its ID, or type `skip`.",
        timeout=120,
    )
    if log_answer and log_answer.lower() not in {"skip", "none"}:
        target = _parse_channel_token(interaction.guild, log_answer)
        if target is not None:
            current["log_channel_id"] = target.id

    moderation_answer = await _prompt_for_response(
        interaction.client,
        channel,
        interaction.user.id,
        "Q2: Which channel should receive moderation updates? Mention the channel, use its ID, or type `skip`.",
        timeout=120,
    )
    if moderation_answer and moderation_answer.lower() not in {"skip", "none"}:
        target = _parse_channel_token(interaction.guild, moderation_answer)
        if target is not None:
            current["moderation_channel_id"] = target.id

    welcome_answer = await _prompt_for_response(
        interaction.client,
        channel,
        interaction.user.id,
        "Q3: Which channel should welcome new members? Mention the channel, use its ID, or type `skip`.",
        timeout=120,
    )
    if welcome_answer and welcome_answer.lower() not in {"skip", "none"}:
        target = _parse_channel_token(interaction.guild, welcome_answer)
        if target is not None:
            current["welcome_channel_id"] = target.id

    enable_answer = await _prompt_for_response(
        interaction.client,
        channel,
        interaction.user.id,
        "Q4: Enable welcome messages? Reply with `yes` or `no`.",
        timeout=120,
    )
    if enable_answer is not None:
        clean = enable_answer.lower()
        if clean in {"yes", "y", "enable", "enabled", "on", "true"}:
            current["welcome_enabled"] = True
        elif clean in {"no", "n", "disable", "disabled", "off", "false"}:
            current["welcome_enabled"] = False

    message_answer = await _prompt_for_response(
        interaction.client,
        channel,
        interaction.user.id,
        "Q5: What should the welcome message say? Use {user} and {server}. Type `default` to keep the default value.",
        timeout=120,
    )
    if message_answer is not None and message_answer.lower() not in {"default", "skip", "none"}:
        current["welcome_message"] = message_answer.strip()

    prefix_answer = await _prompt_for_response(
        interaction.client,
        channel,
        interaction.user.id,
        "Q6: What prefix should the bot use for `!v`-style commands? Example: `!`, `?`, or `!v`. Type `default` to keep `!v`.",
        timeout=120,
    )
    if prefix_answer is not None and prefix_answer.lower() not in {"default", "skip", "none"}:
        prefix = prefix_answer.strip()
        if prefix and prefix.strip() != "":
            current["prefix"] = prefix

    update_server_config(
        interaction.guild.id,
        log_channel_id=current["log_channel_id"],
        moderation_channel_id=current["moderation_channel_id"],
        welcome_channel_id=current["welcome_channel_id"],
        welcome_enabled=current["welcome_enabled"],
        welcome_message=current["welcome_message"],
        prefix=current["prefix"],
    )

    embed = discord.Embed(
        title="✅ Server setup saved",
        description="Your server settings are now stored.",
        color=discord.Color.green(),
    )
    embed.add_field(name="Log channel", value=f"<#{current['log_channel_id']}>" if current.get("log_channel_id") else "Not set", inline=True)
    embed.add_field(name="Moderation channel", value=f"<#{current['moderation_channel_id']}>" if current.get("moderation_channel_id") else "Not set", inline=True)
    embed.add_field(name="Welcome channel", value=f"<#{current['welcome_channel_id']}>" if current.get("welcome_channel_id") else "Not set", inline=True)
    embed.add_field(name="Welcome enabled", value="Yes" if current.get("welcome_enabled") else "No", inline=True)
    embed.add_field(name="Prefix", value=current.get("prefix", DEFAULT_PREFIX), inline=True)
    await channel.send(embed=embed)


def setup(bot: discord.Client, tree: app_commands.CommandTree) -> None:
    ensure_schema()

    @tree.command(name="server-setup", description="Run a quick setup wizard for this server")
    @app_commands.guild_only()
    @is_authorized()
    async def server_setup(interaction: discord.Interaction):
        await _run_setup_wizard(interaction)

    bot.server_setup = get_server_config
    return None


__all__ = [
    "DEFAULT_PREFIX",
    "DEFAULT_WELCOME_MESSAGE",
    "ensure_schema",
    "get_server_config",
    "update_server_config",
    "handle_member_join",
    "setup",
]

