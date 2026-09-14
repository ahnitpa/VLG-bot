import random
import discord
from discord import app_commands
from threading import Thread
from flask import Flask

# 1. THE FAKE WEBSITE TRICK FOR RENDER FREE TIER
app = Flask('')

@app.route('/')
def home():
    return "Bot is online!" # Render will read this and stay happy

def run_web_server():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_web_server)
    t.start()

# 2. YOUR ORIGINAL BOT CODE
TOKEN = 'MTU0ODY1MjUwNDY1NTMzMTQwOQ.GpEBtu.chSEwyo3qNulTI6fEF_2f11ZxcJJe3YZZGBGMc'
ROLE_ID = 1535617025744048268
CUSTOM_EMOJI_ID = 1548670697486688358

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.all())
        self.tree = app_commands.CommandTree(self)

    async def on_ready(self):
        print(f'Logged in as {self.user} (ID: {self.user.id})')
        await self.tree.sync()
        print("Slash commands synced successfully!")

bot = MyBot()

@bot.tree.command(name="gamble", description="Take a 1-in-5 chance to win a special role!")
@app_commands.checks.cooldown(1, 60.0, key=lambda i: (i.user.id))
async def gamble(interaction: discord.Interaction):
    member = interaction.user
    guild = interaction.guild
    role = guild.get_role(ROLE_ID)

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
            await interaction.response.send_message("❌ Error: I do not have permission to give you this role. Move my role higher!", ephemeral=True)
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
async def say(interaction: discord.Interaction, message: str):
    await interaction.response.send_message("Sending message...", ephemeral=True)
    await interaction.channel.send(message)

# --- BONUS COMMAND 1: THE TIMEOUT COINFLIP ---
@bot.tree.command(name="coinflip", description="Flip a coin. Heads you win, Tails you get timed out for 1 minute!")
async def coinflip(interaction: discord.Interaction):
    # Determine the coin flip result
    result = random.choice(["Heads", "Tails"])
    
    if result == "Heads":
        await interaction.response.send_message("🪙 **Heads!** You lucked out. You survive... for now.")
    else:
        # Tails means trouble! Attempt to timeout the user for 60 seconds
        try:
            from datetime import timedelta
            duration = timedelta(seconds=60)
            
            # Apply the timeout to the member who ran the command
            await interaction.user.timeout(duration, reason="Lost the chaotic coinflip command.")
            await interaction.response.send_message("🪙 **Tails!** Oof, bad luck. Enjoy your **1-minute timeout**! 🤫")
        except discord.Forbidden:
            # This triggers if the user has higher server permissions (like an Admin/Owner) 
            # because Discord physically blocks bots from timing out server admins.
            await interaction.response.send_message("🪙 **Tails!** You should be timed out right now, but your server powers (Admin status) protected you! Cheat code activated. 🔐")
        except Exception as e:
            await interaction.response.send_message("🪙 **Tails!** I tried to mute you, but an error stopped me.", ephemeral=True)

# --- BONUS COMMAND 2: THE FAKE THIEF ---
@bot.tree.command(name="steal", description="Attempt to steal imaginary coins from a server member!")
@app_commands.describe(target="The server member you want to rob")
async def steal(interaction: discord.Interaction, target: discord.Member):
    # Prevent users from robbing themselves
    if target == interaction.user:
        await interaction.response.send_message("🧠 You tried to rob yourself. You reached into your own pocket and found nothing. Brilliant.", ephemeral=True)
        return

    # Prevent users from trying to rob the bot
    if target == bot.user:
        await interaction.response.send_message("🤖 You cannot rob a cloud-hosted entity. My security firewall completely vaporized your wallet.", ephemeral=True)
        return

    # Roll a 50/50 chance for success or failure
    outcome = random.choice(["success", "fail"])
    
    if outcome == "success":
        stolen_amount = random.randint(100, 1000)
        await interaction.response.send_message(f"💰 **Success!** {interaction.user.mention} stealthily pickpocketed **{stolen_amount} imaginary coins** from {target.mention}!")
    else:
        await interaction.response.send_message(f"🚨 **BUSTED!** {interaction.user.mention} tried to rob {target.mention} but tripped over a wire and got thrown into imaginary jail! 👮‍♂️")

# --- BONUS COMMAND 3: THE TRIVIAL JUDGEMENT ---
@bot.tree.command(name="rate", description="Have the bot judge and rate anything out of 10!")
@app_commands.describe(thing="The object, person, or idea you want rated")
async def rate(interaction: discord.Interaction, thing: str):
    # Generate a random rating from 0 to 10
    score = random.randint(0, 10)
    
    # Funny reactions based on how high or low the score is
    if score <= 3:
        comments = [
            "Honestly, I've seen better data in a corrupted Excel spreadsheet.",
            "Absolutely tragic. Delete this.",
            "This is so bad it almost crashed my servers."
        ]
    elif score <= 7:
        comments = [
            "Perfectly mid. Neither impressive nor disappointing.",
            "It's alright, but it doesn't exactly make my processors whir.",
            "Decent effort, but standard default Discord settings are more exciting."
        ]
    else:
        comments = [
            "Magnificent! I'm thoroughly impressed. :0",
            "100% approved right here.",
            "This deserves to be pinned. Amazing!"
        ]
        
    chosen_comment = random.choice(comments)
    
    await interaction.response.send_message(
        f"🧐 **Judgement Time :3**\n"
        f"**Thing:** {thing}\n"
        f"**Rating:** `{score}/10`\n"
        f"💬 *\"{chosen_comment}\"*")

# --- BONUS COMMAND 4: THE MAGIC ORACLE ---
@bot.tree.command(name="8ball", description="Ask the Magic 8-Ball a question and receive its wisdom.")
@app_commands.describe(question="The question you want the oracle to answer")
async def eightball(interaction: discord.Interaction, question: str):
    responses = [
        # Positive
        "🟢 My husband said yes in the distance.",
        "🟢 Yes.",
        "🟢 100% approved",
        # Neutral
        "🟡 Ask me again next week.",
        "🟡 Try again later.",
        "🟡 Better not tell you now, my servers might break.",
        # Negative
        "🔴 Absolutely Disagree, go do something else.",
        "🔴 Don't count on it.",
        "🔴 No."
    ]
    
    chosen_response = random.choice(responses)
    
    await interaction.response.send_message(
        f"🔮 **The Magic 8-Ball Oracle**\n"
        f"❓ **Question:** {question}\n"
        f"💬 **Answer:** {chosen_response}"
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    if "gamble" in message.content.lower():
        try:
            custom_emoji = bot.get_emoji(CUSTOM_EMOJI_ID)
            if custom_emoji:
                await message.add_reaction(custom_emoji)
            else:
                await message.add_reaction("❤️")
        except discord.Forbidden:
            pass

# Start the web server first, then boot the bot
keep_alive()
bot.run('MTU0ODY1MjUwNDY1NTMzMTQwOQ.GpEBtu.chSEwyo3qNulTI6fEF_2f11ZxcJJe3YZZGBGMc')
