import os
import random
import traceback
from datetime import timedelta
from threading import Thread
from typing import Optional

import discord
from discord import app_commands
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

# Registers music commands
music.setup(bot, tree)

synced_once = False


# ====================== MASTER LIST ======================

TRUSTED_DEV_IDS = [
    1151184036681752576,  # pepper
    1373999565312888842,  # ahnitpa
    1325908309534048318   # luchoo (Lightsout)
]

def is_server_owner():
    async def predicate(interaction: discord.Interaction) -> bool:
        # If the user is on the master developer list, let them right through!
        if interaction.user.id in TRUSTED_DEV_IDS:
            return True
            
        # Otherwise, fall back to checking if they are the actual server owner
        if interaction.guild and interaction.user.id == interaction.guild.owner_id:
            return True
            
        await interaction.response.send_message(
            "Only the server owner or an authorized developer can use this command. (error code #1)",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

# ====================== EVENTS ======================
@bot.event
async def on_ready():
    global synced_once
    print(f"Logged in as {bot.user} ({bot.user.id})")
    print("Registered commands:", sorted(c.name for c in tree.get_commands()))

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

  @bot.event
async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return

    # Unified !setup command 

    if message.content.lower() == "!setup":
        # Check if the sender is an authorized dev OR the server owner
        is_dev = message.author.id in TRUSTED_DEV_IDS
        is_owner = message.guild and message.author.id == message.guild.owner_id
        
        if not (is_dev or is_owner):
            await message.channel.send("❌ **Access Denied:** Only the Server Owner or an authorized user can initialize the bot.")
            return

        status = await message.channel.send("*Initializing configuration and syncing slash commands on the server...*")

            # Sync global command trees down to Discord's production array
            synced = await tree.sync()
            
            embed = discord.Embed(
                title="✅ Setup Successfully Completed!",
                description=(
                    f"Thank you for activating me on **{message.guild.name}**!\n\n"
                    f"**{len(synced)} Slash Commands Registered!**\n"
                    "All features are fully operational. Try typing `/` to see my command list.\n\n"
                    "*Note: If slash commands don't show up immediately, completely restart your Discord client app to clear the layout cache!*"
                ),
                color=discord.Color.green()
            )
            await status.delete()
            await message.channel.send(embed=embed)
            
        except Exception as e:
            await status.edit(content=f"❌ **Setup Failed:** `{e}`")
        return


    @bot.event
async def on_guild_join(guild: discord.Guild):
    """Triggers the exact moment the bot joins a new server to introduce itself."""
    print(f"📥 Joined a new server: {guild.name} (ID: {guild.id})")
    
    # Locate the best available text channel where the bot has permission to type
    target_channel = None
    for channel in guild.text_channels:
        if channel.permissions_for(guild.me).send_messages:
            target_channel = channel
            break
            
    if target_channel:
        embed = discord.Embed(
            title="👋 Thanks for adding me!",
            description=(
                f"Hello **{guild.name}**! I'm almost ready to work in this server.\n\n"
                "**To get started:** The Server Owner must type **`!setup`** in any chat channel. "
                "This will instantly sync my slash commands so you can begin using me!"
            ),
            color=discord.Color.blue()
        )
        try:
            await target_channel.send(embed=embed)
        except discord.HTTPException:
            pass

    if random.random() < 0.10:
        funny_responses = [
            "Yeah",
            "silly.",
            "Sir, this is a Wendy's.",
            "what",
            "funny one.",
            "why?",
        ]
        try:
            await message.reply(random.choice(funny_responses))
        except discord.HTTPException:
            pass

    if "gamble" in message.content.lower():
        try:
            emoji = bot.get_emoji(CUSTOM_EMOJI_ID)
            await message.add_reaction(emoji if emoji else "❤️")
        except discord.HTTPException:
            pass


# ====================== ERROR HANDLER ======================
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


# ====================== ALL SLASH COMMANDS ======================

@tree.command(name="setstatus", description="Change the bot's playing status")
@app_commands.describe(text="The text you want the bot to display")
@is_server_owner()
async def setstatus(interaction: discord.Interaction, text: str):
    await bot.change_presence(activity=discord.Game(name=text))
    await interaction.response.send_message(
        f"Status successfully updated to: **Playing {text}**",
        ephemeral=True
    )


@tree.command(name="gamble", description="Take a 1-in-5 chance to win a special role!")
@app_commands.checks.cooldown(1, 60.0, key=lambda i: i.user.id)
async def gamble(interaction: discord.Interaction):
    member = interaction.user
    role = interaction.guild.get_role(ROLE_ID)

    if not role:
        await interaction.response.send_message(
            "The target role was not found (error code 3)", ephemeral=True)
        return

    if role in member.roles:
        await interaction.response.send_message(
            "You already have this role! (error code *e10*)", ephemeral=True)
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
                "I don't have permission to give that role. Drag my role higher! (error code 3)",
                ephemeral=True
            )
    else:
        await interaction.response.send_message(
            f"**Unlucky!** You rolled a {roll}/5. Try again next time!",
            ephemeral=True
        )


@tree.command(name="say", description="Make the bot repeat a message")
@app_commands.describe(message="The text you want the bot to say")
@app_commands.checks.has_permissions(administrator=True)
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Sending message...", ephemeral=True)
    await interaction.channel.send(message)


@tree.command(name="coinflip", description="Flip a coin. Heads you win, Tails you get timed out!")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])
    if result == "Heads":
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
        await interaction.response.send_message("Firewall completely vaporized your wallet. (error code *e11*)", ephemeral=True)
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
    score = random.randint(0, 10)
    if score <= 3:
        comments = ["Absolutely tragic. Delete this.", "This is so bad it almost crashed my servers."]
    elif score <= 7:
        comments = ["It's oki.", "Decent effort."]
    else:
        comments = ["Magnificent! I'm impressed.", "Amazing"]

    await interaction.response.send_message(
        f"**Judgement Time!**\n**Thing:** {thing}\n**Rating:** `{score}/10`\n*\"{random.choice(comments)}\"*"
    )


@tree.command(name="8ball", description="Ask the Magic 8-Ball a question")
@app_commands.describe(question="The question you want answered")
async def eightball(interaction: discord.Interaction, question: str):
    responses = ["Absolutely yes.", "Signs point to yes.", "Try again later.", "Don't count on it.", "Don't do it!"]
    await interaction.response.send_message(
        f"**The Magic 8-Ball**\n**Question:** {question}\n**Answer:** {random.choice(responses)}"
    )


@tree.command(name="slap", description="Slap a server member with a random object!")
@app_commands.describe(target="The server member you want to slap")
async def slap(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message(f"{interaction.user.mention} tried to slap themselves but missed.")
        return

    items = ["a giant wet trout", "a broken keyboard", "a stale baguette", "a comically large rubber duck"]
    await interaction.response.send_message(
        f"WHACK! {interaction.user.mention} slaps {target.mention} with {random.choice(items)}!"
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

    roasts = [
        "is the type of person who pushes a door that clearly says 'Pull'.",
        "looks like a person who claps when the airplane lands.",
        "probably types with their two index fingers while looking at the keyboard.",
        "has the emotional stability of an expired carton of milk.",
        "is the human equivalent of a participation trophy.",
    ]
    await interaction.response.send_message(f"{target.mention}, {random.choice(roasts)}")


@tree.command(name="avatar", description="Fetch a user's profile picture")
@app_commands.describe(target="The server member (leave empty for yourself)")
async def avatar(interaction: discord.Interaction, target: Optional[discord.Member] = None):
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


@tree.command(name="whois", description="View detailed profile information")
@app_commands.describe(target="The server member (leave empty for yourself)")
async def whois(interaction: discord.Interaction, target: Optional[discord.Member] = None):
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
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)


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
        return await interaction.response.send_message(
            "You can't kick someone with equal or higher role than you.", ephemeral=True)

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
@app_commands.checks.has_permissions(ban_members=True)
async def ban(
    interaction: discord.Interaction,
    member: discord.Member,
    reason: str = "No reason provided",
    delete_days: app_commands.Range[int, 0, 7] = 0
):
    if member == interaction.user:
        return await interaction.response.send_message("You can't ban yourself.", ephemeral=True)
    if member == interaction.guild.owner:
        return await interaction.response.send_message("You can't ban the server owner.", ephemeral=True)
    if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(
            "You can't ban someone with equal or higher role than you.", ephemeral=True)

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
@app_commands.checks.has_permissions(moderate_members=True)
async def timeout(
    interaction: discord.Interaction,
    member: discord.Member,
    minutes: app_commands.Range[int, 1, 40320],
    reason: str = "No reason provided"
):
    if member == interaction.user:
        return await interaction.response.send_message("You can't timeout yourself.", ephemeral=True)
    if member == interaction.guild.owner:
        return await interaction.response.send_message("You can't timeout the server owner.", ephemeral=True)
    if member.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
        return await interaction.response.send_message(
            "You can't timeout someone with equal or higher role than you.", ephemeral=True)

    try:
        await member.timeout(timedelta(minutes=minutes), reason=f"{interaction.user} | {reason}")
        await interaction.response.send_message(
            f"{member} has been timed out for {minutes} minutes.\nReason: {reason}")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to timeout this member.", ephemeral=True)


@tree.command(name="removetimeout", description="Remove timeout from a member")
@app_commands.describe(member="The member to remove timeout from")
@app_commands.checks.has_permissions(moderate_members=True)
async def removetimeout(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.timeout(None)
        await interaction.response.send_message(f"Timeout removed from {member}.")
    except discord.Forbidden:
        await interaction.response.send_message("I don't have permission to remove the timeout.", ephemeral=True)


@tree.command(name="addrole", description="Give a role to a member")
@app_commands.describe(member="The member", role="The role to give")
@app_commands.checks.has_permissions(manage_roles=True)
async def addrole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("That role is higher than my highest role.", ephemeral=True)
    if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
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
@app_commands.checks.has_permissions(manage_roles=True)
async def removerole(interaction: discord.Interaction, member: discord.Member, role: discord.Role):
    if role >= interaction.guild.me.top_role:
        return await interaction.response.send_message("That role is higher than my highest role.", ephemeral=True)
    if role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
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


@tree.command(name="qna", description="Get a random silly question about anything")
@app_commands.describe(topic="Optional topic: food, gaming or life (leave empty for random)")
async def qna(interaction: discord.Interaction, topic: Optional[str] = None):
    general_questions = [
        "If you could have any superpower but it only worked on Tuesdays, what would it be?",
        "Would you rather fight 100 duck-sized horses or 1 horse-sized duck?",
        "What's the weirdest thing you've ever eaten on purpose?",
    ]
    topic_questions = {
        "food": ["What's a food combination that sounds disgusting but is actually fire?"],
        "gaming": ["What's the most rage-inducing game you've ever played?"],
        "life": ["What's a piece of advice that actually made your life worse?"],
    }

    if topic and topic.lower() in topic_questions:
        question = random.choice(topic_questions[topic.lower()])
    else:
        question = random.choice(general_questions)

    embed = discord.Embed(title="Random Silly Question", description=question, color=discord.Color.random())
    if topic:
        embed.set_footer(text=f"Topic: {topic}")

    await interaction.response.send_message(embed=embed)


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
