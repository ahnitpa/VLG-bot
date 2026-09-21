import random
import discord
from discord import app_commands
from threading import Thread
from flask import Flask
from datetime import timedelta

# --- 1. THE WEB SERVER (RENDER FREE TIER TRICK) ---
app = Flask('')

@app.route('/')
def home():
    return "Bot is online and active!"

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# --- 2. BOT CONFIGURATION VARIABLES ---
# ⚠️ REPLACE THE ENTIRE LINE BELOW WITH YOUR REAL BOT TOKEN SITUATED INSIDE SINGLE QUOTES
TOKEN = 'MTU0ODY1MjUwNDY1NTMzMTQwOQ.GqD8h1.6W1LyIbWtzjDY_wZ7Fh2nvyBnQ1qp5qp4Cdn7Q.'


SERVER_ID = 1478447010284568781
ROLE_ID = 1535617025744048268
CUSTOM_EMOJI_ID = 1548670697486688358

MY_SERVER = discord.Object(id=1478447010284568781)

# --- 3. CUSTOM BOT CLASS ---
class CustomBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        self.tree.copy_global_to(guild=MY_SERVER)
        await self.tree.sync(guild=MY_SERVER)
        print("Slash commands completely synced to your server!")

bot = CustomBot()

# --- 4. ALL SLASH COMMANDS ---

@bot.tree.command(name="gamble", description="Take a 1-in-5 chance to win a special role!")
@app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.user.id))
async def gamble(interaction: discord.Interaction):
    member = interaction.user
    guild = interaction.guild
    role = guild.get_role(1535617025744048268)

    if not role:
        await interaction.response.send_message("❌ Error: The target role was not found.", ephemeral=True)
        return

    if role in member.roles:
        await interaction.response.send_message("You already have this role!", ephemeral=True)
        return

    roll = random.randint(1, 5)

    if roll == 1:
        try:
            await member.add_roles(role)
            await interaction.response.send_message(f"🎉 **Lucky!** You rolled a {roll}/5 and won the **{role.name}** role!")
        except discord.Forbidden:
            await interaction.response.send_message("❌ Error: I don't have permission. Drag my bot role ABOVE the target role!", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ **Unlucky!** You rolled a {roll}/5. Try again next time!", ephemeral=True)

@gamble.error
async def gamble_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        await interaction.response.send_message(f"⏳ Slow down! You can try again in **{error.retry_after:.1f}** seconds.", ephemeral=True)
    else:
        raise error

@bot.tree.command(name="say", description="Make the bot repeat a message for you.")
@app_commands.describe(message="The text you want the bot to say")
@app_commands.checks.has_permissions(administrator=True) # 🔒 ONLY ADMINS CAN USE THIS NOW
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Sending message...", ephemeral=True)
    await interaction.channel.send(message)

# Handle the error smoothly if a regular user tries to sneakily bypass and use it
@say.error
async def say_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.MissingPermissions):
        await interaction.response.send_message("**Access Denied!:** You need `Administrator` permissions to make me speak!", ephemeral=True)
    else:
        raise error

@bot.tree.command(name="coinflip", description="Flip a coin. Heads you win, Tails you get timed out for 1 minute!")
async def coinflip(interaction: discord.Interaction):
    result = random.choice(["Heads", "Tails"])
    if result == "Heads":
        await interaction.response.send_message("🪙 **Heads!** You lucked out. You survive... for now.")
    else:
        try:
            duration = timedelta(seconds=60)
            await interaction.user.timeout(duration, reason="Lost the coinflip game.")
            await interaction.response.send_message("🪙 **Tails!** Oof, bad luck. Enjoy your **1-minute timeout**! :D")
        except discord.Forbidden:
            await interaction.response.send_message("🪙 **Tails!** You should be timed out right now, but your Admin powers protected you ._.")

@bot.tree.command(name="steal", description="Attempt to steal imaginary coins from a server member!")
@app_commands.describe(target="The server member you want to rob")
async def steal(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message("You tried robbing yourself. How does it feel?.", ephemeral=True)
        return
    if target == bot.user:
        await interaction.response.send_message("Firewall completely vaporized your wallet.", ephemeral=True)
        return

    outcome = random.choice(["success", "fail"])
    if outcome == "success":
        stolen_amount = random.randint(100, 1000)
        await interaction.response.send_message(f"💰 **Success!** {interaction.user.mention} stole **{stolen_amount} coins** from {target.mention}!")
    else:
        await interaction.response.send_message(f"🚨 **BUSTED!** {interaction.user.mention} tried to rob {target.mention} but got thrown into imaginary jail! 👮‍♂️")

@bot.tree.command(name="rate", description="Have the bot judge and rate anything out of 10!")
@app_commands.describe(thing="The object, person, or idea you want rated")
async def rate(interaction: discord.Interaction, thing: str):
    score = random.randint(0, 10)
    if score <= 3:
        comments = ["Absolutely tragic. Delete this.", "This is so bad it almost crashed my servers."]
    elif score <= 7:
        comments = ["Perfectly mid. Neither impressive nor disappointing.", "Decent effort."]
    else:
        comments = ["Magnificent! I'm impressed", "100% cloud-approved excellence."]
    
    await interaction.response.send_message(f"**Judgement Time!**\n**Thing:** {thing}\n**Rating:** `{score}/10`\n💬 *\"{random.choice(comments)}\"*")

@bot.tree.command(name="8ball", description="Ask the Magic 8-Ball a question.")
@app_commands.describe(question="The question you want the oracle to answer")
async def eightball(interaction: discord.Interaction, question: str):
    responses = ["🟢 Absolutely yes.", "🟢 Signs point to yes.", "💡 Try again later.", "🔴 Don't count on it.", "🔴 Don't do it!."]
    await interaction.response.send_message(f"🔮 **The Magic 8-Ball**\n❓ **Question:** {question}\n💬 **Answer:** {random.choice(responses)}")

@bot.tree.command(name="slap", description="Slap a server member with a random object!")
@app_commands.describe(target="The server member you want to slap")
async def slap(interaction: discord.Interaction, target: discord.Member):
    if target == interaction.user:
        await interaction.response.send_message(f"🤕 {interaction.user.mention} tried to slap themselves but missed.")
        return
    items = ["a giant, wet trout 🐟", "a broken keyboard ⌨️", "a stale baguette 🥖", "a comically large rubber duck 🦆"]
    await interaction.response.send_message(f"💥 **WHACK!** {interaction.user.mention} slaps {target.mention} with {random.choice(items)}!")

# --- BONUS COMMAND 6: THE MILD ROAST GENERATOR ---
@bot.tree.command(name="roast", description="Hit a fellow server member with a funny, harmless burn!")
@app_commands.describe(target="The server member you want to roast")
async def roast(interaction: discord.Interaction, target: discord.Member):
    # Prevent users from roasting themselves
    if target == interaction.user:
        await interaction.response.send_message(f"🥺 {interaction.user.mention}, you can't roast yourself! Self-love only in this server.", ephemeral=True)
        return

    # Prevent users from trying to roast the bot
    if target == bot.user:
        await interaction.response.send_message("Back off. You can't roast bots..", ephemeral=True)
        return

    roasts = [
        "is the type of person who pushes a door that clearly says 'Pull'.",
        "looks like a person who claps when the airplane lands. ✈️",
        "probably types with their two index fingers while looking directly at the keyboard.",
        "has the emotional stability of an expired carton of milk. 🥛",
        "is the human equivalent of a participation trophy.",
        "looks like they remind the teacher to assign homework right before the bell rings. 🔔",
        "probably puts milk in the bowl before the cereal. Absolutely criminal.",
        "is like software update notifications—annoying, easily ignored, and always showing up at the worst time."
    ]
    
    chosen_roast = random.choice(roasts)
    
    # Broadcast the roast into the public channel
    await interaction.response.send_message(f"🔥 **BOOM!** {target.mention}, {chosen_roast}")

@bot.tree.command(name="avatar", description="Fetch user's profile picture")
@app_commands.describe(target="The server member you want to snatch")
async def avatar(interaction: discord.Interaction, target: discord.Member = None):
    # If no target is specified, default to the user who ran the command
    if target is None:
        target = interaction.user

    # Create a clean Discord Embed
    embed = discord.Embed(
        title=f"Avatar of {target.display_name}",
        color=target.color if target.color else discord.Color.blue()
    )
    
    # Set the main image to the user's avatar URL
    embed.set_image(url=target.display_name if not target.avatar else target.avatar.url)
    
    # Provide a clickable download link in the description
    if target.avatar:
        embed.description = f"[Click here to open original image]({target.avatar.url})"
    else:
        embed.description = "This user is using a default Discord avatar."

    # Send the embed response
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="whois", description="View detailed profile and account information for a server member.")
@app_commands.describe(target="The server member you want to inspect")
async def whois(interaction: discord.Interaction, target: discord.Member = None):
    # If no target is specified, default to the user who ran the command
    if target is None:
        target = interaction.user

    # Format dates cleanly into Day-Month-Year format
    account_created = target.created_at.strftime("%d %b %Y")
    server_joined = target.joined_at.strftime("%d %b %Y") if target.joined_at else "Unknown"

    # Filter out the default @everyone role and limit display to avoid messy walls of text
    roles = [role.mention for role in target.roles if role.name != "@everyone"]
    roles_display = " ".join(roles) if roles else "No special roles"

    # Determine key account permissions to feature
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

    # Assemble the profile embed card
    embed = discord.Embed(
        title=f"User Info - {target.name}#{target.discriminator if target.discriminator != '0' else ''}",
        color=target.color if target.color else discord.Color.blue()
    )
    
    # Add data fields
    embed.set_thumbnail(url=target.avatar.url if target.avatar else target.default_avatar.url)
    embed.add_field(name="Display Name", value=target.mention, inline=True)
    embed.add_field(name="Account ID", value=f"`{target.id}`", inline=True)
    embed.add_field(name="Server Status", value=status_display, inline=True)
    embed.add_field(name="Created On", value=account_created, inline=True)
    embed.add_field(name="Joined Server", value=server_joined, inline=True)
    embed.add_field(name=f"Roles ({len(roles)})", value=roles_display, inline=False)
    
    embed.set_footer(text=f"Requested by {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)


# --- 5. CHAT TEXT EVENT TRIGGERS (!forcesync and emoji reactions) ---
# --- 5. CHAT TEXT EVENT TRIGGERS ---
@bot.event
# --- 5. CHAT TEXT EVENT TRIGGERS ---
@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    # Trigger force-sync when YOU type !forcesync in chat
    if message.content.lower() == "!forcesync":
        if message.author.id != message.guild.owner_id:
            await message.channel.send("❌ **Access Denied:** Server Owner only.")
            return
        
        status = await message.channel.send("🔄 *Forcing direct tree sync...*")
        bot.tree.copy_global_to(guild=MY_SERVER)
        await bot.tree.sync(guild=MY_SERVER)
        await status.edit(content="✅ **API Force-Sync Complete!** All commands refreshed.")
        return

    # --- NEW FEATURE: THE INSTANT @PING RESPONSE ---
    # Checks if the bot's user account was mentioned in the message
    if bot.user.mentioned_in(message) and not message.mention_everyone:
        ping_responses = [
            "Haiiii :3",
        ]
        try:
            await message.reply(random.choice(ping_responses))
            return # Stop processing the rest of the file so it doesn't double-reply!
        except discord.Forbidden:
            pass

   
    # --- NEW FEATURE: THE RANDOM INTERRUPTER (5% CHANCE) ---
    # random.random() picks a float between 0.0 and 1.0. 
    # 0.05 equals a 5% chance. If you want it more active, change 0.05 to 0.10 (10%).
    if random.random() < 0.10:
        funny_responses = [
            "UHM. no.",
            "Yeah",
            "silly.",
            "Sir, this is a Wendy's.",
            "what",
            "funny one. ",
            "idk.",
            "why."
        ]
        try:
            # The bot will reply directly to the random message
            await message.reply(random.choice(funny_responses))
        except discord.Forbidden:
            pass

    # React to the word gamble
    if "gamble" in message.content.lower():
        try:
            custom_emoji = bot.get_emoji(1548670697486688358)
            if custom_emoji:
                await message.add_reaction(1548670697486688358)
            else:
                await message.add_reaction("❤️")
        except discord.Forbidden:
            pass

# --- 6. START UP THE BOT ENGINES ---
keep_alive()
bot.run('MTU0ODY1MjUwNDY1NTMzMTQwOQ.GqD8h1.6W1LyIbWtzjDY_wZ7Fh2nvyBnQ1qp5qp4Cdn7Q')
