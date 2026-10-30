"""Moderation feature module."""

import datetime

import discord
from discord import app_commands


class ModerationManager:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self.warnings: dict[int, dict[int, list[str]]] = {}

    def add_warning(self, guild_id: int, user_id: int, reason: str) -> list[str]:
        guild_warnings = self.warnings.setdefault(guild_id, {})
        entries = guild_warnings.setdefault(user_id, [])
        entries.append(reason)
        return entries

    def get_warnings(self, guild_id: int, user_id: int) -> list[str]:
        return self.warnings.get(guild_id, {}).get(user_id, [])

    def clear_warnings(self, guild_id: int, user_id: int) -> int:
        guild_warnings = self.warnings.get(guild_id, {})
        removed = len(guild_warnings.pop(user_id, []))
        if not guild_warnings:
            self.warnings.pop(guild_id, None)
        return removed

    async def warn_member(self, interaction: discord.Interaction, member: discord.Member, reason: str) -> None:
        entries = self.add_warning(interaction.guild.id, member.id, reason)
        await interaction.response.send_message(
            f"⚠️ Warned {member.mention} for: **{reason}**\nTotal warnings: **{len(entries)}**",
            allowed_mentions=discord.AllowedMentions.none(),
        )

    async def timeout_member(self, interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str) -> None:
        if interaction.user.id == member.id:
            await interaction.response.send_message("You cannot timeout yourself.", ephemeral=True)
            return
        if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You cannot timeout someone equal to or higher than you.", ephemeral=True)
            return
        try:
            await member.timeout(datetime.timedelta(minutes=minutes), reason=reason)
            await interaction.response.send_message(f"⏱️ Timed out {member.mention} for **{minutes}** minutes.\nReason: **{reason}**")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to timeout that member.", ephemeral=True)

    async def ban_member(self, interaction: discord.Interaction, member: discord.Member, reason: str, delete_days: int = 0) -> None:
        if interaction.user.id == member.id:
            await interaction.response.send_message("You cannot ban yourself.", ephemeral=True)
            return
        if member.top_role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("You cannot ban someone equal to or higher than you.", ephemeral=True)
            return
        try:
            await member.ban(reason=reason, delete_message_days=delete_days)
            await interaction.response.send_message(f"🔨 Banned {member.mention}.\nReason: **{reason}**")
        except discord.Forbidden:
            await interaction.response.send_message("I don't have permission to ban that member.", ephemeral=True)

    def setup(self, tree: app_commands.CommandTree) -> None:
        if getattr(tree, "_vlg_moderation_setup", False):
            return
        tree._vlg_moderation_setup = True

        @tree.command(name="warn", description="Warn a member")
        @app_commands.describe(member="Member to warn", reason="Reason for the warning")
        async def warn(interaction: discord.Interaction, member: discord.Member, reason: str):
            if not interaction.user.guild_permissions.manage_messages and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You need manage messages permission to use this command.", ephemeral=True)
                return
            await self.warn_member(interaction, member, reason)

        @tree.command(name="warnings", description="List warnings for a member")
        @app_commands.describe(member="Member to inspect")
        async def warnings(interaction: discord.Interaction, member: discord.Member):
            if not interaction.user.guild_permissions.manage_messages and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You need manage messages permission to use this command.", ephemeral=True)
                return
            entries = self.get_warnings(interaction.guild.id, member.id)
            if not entries:
                await interaction.response.send_message(f"{member.mention} has no warnings.")
                return
            lines = [f"{index + 1}. {reason}" for index, reason in enumerate(entries)]
            await interaction.response.send_message(f"⚠️ Warnings for {member.mention}:\n" + "\n".join(lines))

        @tree.command(name="clearwarnings", description="Clear all warnings for a member")
        @app_commands.describe(member="Member to clear warnings for")
        async def clearwarnings(interaction: discord.Interaction, member: discord.Member):
            if not interaction.user.guild_permissions.manage_messages and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You need manage messages permission to use this command.", ephemeral=True)
                return
            removed = self.clear_warnings(interaction.guild.id, member.id)
            await interaction.response.send_message(f"Cleared **{removed}** warning(s) for {member.mention}.")

        @tree.command(name="timeout", description="Timeout a member for a number of minutes")
        @app_commands.describe(member="Member to timeout", minutes="How many minutes", reason="Reason")
        async def timeout_cmd(
            interaction: discord.Interaction,
            member: discord.Member,
            minutes: app_commands.Range[int, 1, 10080],
            reason: str = "No reason provided",
        ):
            if not interaction.user.guild_permissions.moderate_members and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You need moderate members permission to use this command.", ephemeral=True)
                return
            await self.timeout_member(interaction, member, minutes, reason)

        @tree.command(name="ban", description="Ban a member")
        @app_commands.describe(member="Member to ban", reason="Reason", delete_days="Delete recent messages in days")
        async def ban_cmd(
            interaction: discord.Interaction,
            member: discord.Member,
            reason: str = "No reason provided",
            delete_days: app_commands.Range[int, 0, 7] = 0,
        ):
            if not interaction.user.guild_permissions.ban_members and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You need ban members permission to use this command.", ephemeral=True)
                return
            await self.ban_member(interaction, member, reason, delete_days)

        @tree.command(name="kick", description="Kick a member")
        @app_commands.describe(member="Member to kick", reason="Reason")
        async def kick_cmd(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
            if not interaction.user.guild_permissions.kick_members and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You need kick members permission to use this command.", ephemeral=True)
                return
            if interaction.user.id == member.id:
                await interaction.response.send_message("You cannot kick yourself.", ephemeral=True)
                return
            try:
                await member.kick(reason=reason)
                await interaction.response.send_message(f"👢 Kicked {member.mention}.\nReason: **{reason}**")
            except discord.Forbidden:
                await interaction.response.send_message("I don't have permission to kick that member.", ephemeral=True)

        @tree.command(name="removetimeout", description="Remove timeout from a member")
        @app_commands.describe(member="Member to untimeout")
        async def removetimeout(interaction: discord.Interaction, member: discord.Member):
            if not interaction.user.guild_permissions.moderate_members and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message("You need moderate members permission to use this command.", ephemeral=True)
                return
            try:
                await member.timeout(None)
                await interaction.response.send_message(f"✅ Removed timeout from {member.mention}.")
            except discord.Forbidden:
                await interaction.response.send_message("I don't have permission to remove that timeout.", ephemeral=True)


def create_moderation_manager(bot: discord.Client) -> "ModerationManager":
    return ModerationManager(bot)


__all__ = ["ModerationManager", "create_moderation_manager"]
