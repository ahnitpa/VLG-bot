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
bot.run(MTU0ODY1MjUwNDY1NTMzMTQwOQ.GpEBtu.chSEwyo3qNulTI6fEF_2f11ZxcJJe3YZZGBGMc)
