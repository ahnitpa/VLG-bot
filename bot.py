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

# ============================================================
# MUSIC SECTION: replaces your old music settings, YTDLSource,
# play_next, /play, /skip, /stop and /leave.
# Keep your existing /join command as it is.
# ============================================================

# ---- 1) Put these imports at the TOP of your file ----
import asyncio
import os
from typing import Optional   # also needed by your /qna command

import yt_dlp
import discord

# Optional: bundled ffmpeg binary (pip install imageio-ffmpeg).
# Useful on Render, where ffmpeg is not installed by default.
try:
    import imageio_ffmpeg
    FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
except ImportError:
    FFMPEG_PATH = "ffmpeg"

# ---- 2) Music settings (replace your old ytdl / ffmpeg options) ----
yt_dlp.utils.bug_reports_message = lambda *a, **k: ''

ytdl_format_options = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',   # plain text -> YouTube search
    'source_address': '0.0.0.0',
}

# If YouTube blocks your host, export cookies from a browser and
# upload the file as cookies.txt next to your bot (see notes).
if os.path.exists("cookies.txt"):
    ytdl_format_options['cookiefile'] = 'cookies.txt'

ytdl = yt_dlp.YoutubeDL(ytdl_format_options)

ffmpeg_options = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
    'executable': FFMPEG_PATH,
}

# Per-guild state
queues = {}          # guild_id -> list of song dicts
now_playing = {}     # guild_id -> song dict currently playing
text_channels = {}   # guild_id -> channel to announce songs in


# ---- 3) Helpers ----
async def fetch_song(query: str) -> dict:
    """Look up a URL or search term and return the song info (no download)."""
    loop = asyncio.get_running_loop()
    data = await loop.run_in_executor(
        None, lambda: ytdl.extract_info(query, download=False)
    )
    if data is None:
        raise ValueError("Nothing found.")
    if 'entries' in data:                      # search results
        entries = [e for e in data['entries'] if e]
        if not entries:
            raise ValueError("No results found.")
        data = entries[0]
    return {
        'title': data.get('title', 'Unknown title'),
        'stream_url': data['url'],
        'page_url': data.get('webpage_url', query),
    }


async def play_next(guild: discord.Guild):
    """Start the next song in the queue, if there is one."""
    voice_client = guild.voice_client
    if voice_client is None or not voice_client.is_connected():
        return

    queue = queues.get(guild.id)
    if not queue:
        now_playing.pop(guild.id, None)
        return

    song = queue.pop(0)
    now_playing[guild.id] = song

    def after(error):
        if error:
            print(f"Player error: {error}")
        asyncio.run_coroutine_threadsafe(play_next(guild), bot.loop)

    try:
        audio = discord.FFmpegPCMAudio(song['stream_url'], **ffmpeg_options)
        voice_client.play(discord.PCMVolumeTransformer(audio, volume=0.5), after=after)
    except Exception as e:
        print(f"Could not play {song['title']}: {e}")
        await play_next(guild)   # skip the broken song
        return

    channel = text_channels.get(guild.id)
    if channel:
        try:
            await channel.send(f"▶️ **Now playing:** [{song['title']}]({song['page_url']})")
        except discord.HTTPException:
            pass

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


@tree.command(name="join", description="Make the bot join your current voice channel")
async def join(interaction: discord.Interaction):
    # Check if the user is in a voice channel
    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.response.send_message(
            "❌ You need to be in a voice channel first!",
            ephemeral=True
        )
        return

    channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    try:
        if voice_client is None:
            # Bot is not connected anywhere → join
            await channel.connect()
            await interaction.response.send_message(f"✅ Joined **{channel.name}**")
        elif voice_client.channel == channel:
            # Already in the same channel
            await interaction.response.send_message(
                "I'm already in your voice channel!",
                ephemeral=True
            )
        else:
            # Bot is in another channel → move
            await voice_client.move_to(channel)
            await interaction.response.send_message(f"Moved to **{channel.name}**")
    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to join that voice channel.\n"
            "Make sure I have **Connect** and **Speak** permissions.",
            ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            f"Failed to join: `{e}` (most likely code error)",
            ephemeral=True
        )

# ---- 4) Commands ----
@tree.command(name="play", description="Play a song from YouTube (URL or search)")
@app_commands.describe(query="YouTube URL or search term")
async def play(interaction: discord.Interaction, query: str):
    await interaction.response.defer()

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.followup.send("❌ You need to be in a voice channel!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    voice_client = interaction.guild.voice_client

    try:
        if voice_client is None:
            voice_client = await channel.connect()
        elif voice_client.channel != channel:
            await voice_client.move_to(channel)
    except Exception as e:
        await interaction.followup.send(f"❌ Could not join voice channel: `{e}`")
        return

    try:
        song = await fetch_song(query)
    except Exception as e:
        await interaction.followup.send(f"❌ Couldn't get that song: `{e}`")
        return

    guild_id = interaction.guild.id
    queues.setdefault(guild_id, []).append(song)
    text_channels[guild_id] = interaction.channel

    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(
            f"✅ Added to queue (#{len(queues[guild_id])}): **{song['title']}**"
        )
    else:
        await interaction.followup.send(f"🔎 Found **{song['title']}**")
        await play_next(interaction.guild)


@tree.command(name="skip", description="Skip the current song")
async def skip(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client is None or not (voice_client.is_playing() or voice_client.is_paused()):
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)
        return

    voice_client.stop()   # triggers play_next through the after callback
    await interaction.response.send_message("⏭️ Skipped!")


@tree.command(name="pause", description="Pause the current song")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.pause()
        await interaction.response.send_message("⏸️ Paused.")
    else:
        await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)


@tree.command(name="resume", description="Resume the paused song")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client and voice_client.is_paused():
        voice_client.resume()
        await interaction.response.send_message("▶️ Resumed.")
    else:
        await interaction.response.send_message("Nothing is paused.", ephemeral=True)


@tree.command(name="queue", description="Show the current queue")
async def show_queue(interaction: discord.Interaction):
    current = now_playing.get(interaction.guild.id)
    upcoming = queues.get(interaction.guild.id, [])

    if not current and not upcoming:
        await interaction.response.send_message("The queue is empty.", ephemeral=True)
        return

    lines = []
    if current:
        lines.append(f"**Now playing:** {current['title']}")
    for i, song in enumerate(upcoming[:10], start=1):
        lines.append(f"`{i}.` {song['title']}")
    if len(upcoming) > 10:
        lines.append(f"...and {len(upcoming) - 10} more")

    await interaction.response.send_message("\n".join(lines))


@tree.command(name="stop", description="Stop playing and clear the queue")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client is None:
        await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
        return

    queues.pop(interaction.guild.id, None)
    now_playing.pop(interaction.guild.id, None)
    voice_client.stop()
    await interaction.response.send_message("⏹️ Stopped and cleared the queue.")


@tree.command(name="leave", description="Make the bot leave the voice channel")
async def leave(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    if voice_client is None:
        await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)
        return

    queues.pop(interaction.guild.id, None)
    now_playing.pop(interaction.guild.id, None)
    await voice_client.disconnect()
    await interaction.response.send_message("Left the voice channel.")


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
													
