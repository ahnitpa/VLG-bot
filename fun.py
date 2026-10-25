import random
from typing import Optional

import discord
from discord import app_commands

# No SQLite or persistence layer remains here.
# All commands in this module are non-economic and ephemeral-only.

_COMMANDS = {}

PREFIX_HELP = (
    "**🎮 Fun & utility (`!v`)**\n"
    "**Random:** `cat`, `dog`, `meme`, `joke`, `fact`, `ship @a [@b]`, `choose a, b, c`\n"
    "**Info:** `help`"
)


def setup(bot: discord.Client, tree: app_commands.CommandTree):
    def slash(name: str, description: str):
        if name in _COMMANDS:
            raise RuntimeError(f"Duplicate slash command name registered: {name}")

        def deco(fn):
            fn = app_commands.guild_only()(fn)
            cmd = tree.command(name=name, description=description)(fn)
            _COMMANDS[name] = cmd
            return cmd

        return deco

    @slash("cat", "Get a random cat picture")
    async def cat(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://api.thecatapi.com/v1/images/search") as resp:
                    data = await resp.json() if resp.status == 200 else None
        except Exception:
            data = None
        if not data:
            return await interaction.followup.send("😿 The cat service is napping. Try again in a moment.")
        e = discord.Embed(title="🐱 Meow!", color=discord.Color.orange())
        e.set_image(url=data[0]["url"])
        await interaction.followup.send(embed=e)

    @slash("dog", "Get a random dog picture")
    async def dog(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://dog.ceo/api/breeds/image/random") as resp:
                    data = await resp.json() if resp.status == 200 else None
        except Exception:
            data = None
        if not data or "message" not in data:
            return await interaction.followup.send("🐶 The dog service is out for a walk. Try again in a moment.")
        e = discord.Embed(title="🐶 Woof!", color=discord.Color.orange())
        e.set_image(url=data["message"])
        await interaction.followup.send(embed=e)

    @slash("meme", "Get a random meme")
    async def meme(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://meme-api.com/gimme") as resp:
                    data = await resp.json() if resp.status == 200 else None
        except Exception:
            data = None
        if not data or not data.get("url") or data.get("nsfw") or data.get("spoiler"):
            return await interaction.followup.send("😵 Couldn't fetch a meme right now.")
        e = discord.Embed(title=data.get("title", "Meme")[:250], url=data.get("postLink"), color=discord.Color.random())
        e.set_image(url=data["url"])
        e.set_footer(text=f"r/{data.get('subreddit', 'memes')}")
        await interaction.followup.send(embed=e)

    @slash("joke", "Get a random joke")
    async def joke(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://official-joke-api.appspot.com/random_joke") as resp:
                    data = await resp.json() if resp.status == 200 else None
        except Exception:
            data = None
        if not data or "setup" not in data:
            return await interaction.followup.send("🤡 I forgot the joke. Try again in a moment.")
        await interaction.followup.send(f"**{data['setup']}**\n||{data['punchline']}||")

    @slash("fact", "Get a random fact")
    async def fact(interaction: discord.Interaction):
        await interaction.response.defer()
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get("https://uselessfacts.jsph.pl/api/v2/facts/random", params={"language": "en"}) as resp:
                    data = await resp.json() if resp.status == 200 else None
        except Exception:
            data = None
        if not data or "text" not in data:
            return await interaction.followup.send("📚 My fact book is closed right now. Try again in a moment.")
        await interaction.followup.send(f"📚 **Did you know?**\n{data['text']}")

    @slash("ship", "Check how compatible two members are")
    @app_commands.describe(first="The first member", second="The second member (leave empty for yourself)")
    async def ship(interaction: discord.Interaction, first: discord.Member, second: Optional[discord.Member] = None):
        other = second or interaction.user
        a, b = sorted((first.id, other.id))
        pct = int(__import__("hashlib").md5(f"{a}-{b}".encode()).hexdigest()[:6], 16) % 101
        verdict = "Better as strangers. 💔"
        if pct < 25:
            verdict = "Better as strangers. 💔"
        elif pct < 50:
            verdict = "Just friends... maybe. 🤝"
        elif pct < 75:
            verdict = "There's a spark! ✨"
        elif pct < 90:
            verdict = "A great match! 💕"
        else:
            verdict = "Soulmates! 💘"
        n1, n2 = first.display_name, other.display_name
        ship_name = n1[:max(1, len(n1) // 2)] + n2[len(n2) // 2:]
        embed = discord.Embed(
            title=f"💞 {n1} x {n2}",
            description=f"**Ship name:** {ship_name}\n`{'█' * int(20 * pct / 100) + '░' * (20 - int(20 * pct / 100))}` **{pct}%**\n{verdict}",
            color=discord.Color.magenta(),
        )
        await interaction.response.send_message(embed=embed)

    @slash("choose", "Let the bot pick between options")
    @app_commands.describe(options="Separate options with commas, e.g. pizza, sushi, tacos")
    async def choose(interaction: discord.Interaction, options: str):
        parts = [p.strip() for p in options.replace(" or ", ",").split(",") if p.strip()]
        if len(parts) < 2:
            return await interaction.response.send_message("❌ Give me at least two options separated by commas.", ephemeral=True)
        await interaction.response.send_message(f"🤔 I choose... **{random.choice(parts)}**!", allowed_mentions=discord.AllowedMentions.none())


class _PrefixResponse:
    def __init__(self, ctx: "PrefixContext"):
        self.ctx = ctx
        self._done = False

    def is_done(self):
        return self._done

    async def defer(self, **_):
        self._done = True

    async def send_message(self, content=None, *, embed=None, view=None, ephemeral=False, allowed_mentions=None, **_):
        kwargs = {k: v for k, v in (("content", content), ("embed", embed), ("view", view), ("allowed_mentions", allowed_mentions)) if v is not None}
        sent = await self.ctx.channel.send(**kwargs)
        self.ctx.sent = sent
        self._done = True


class _PrefixFollowup:
    def __init__(self, ctx: "PrefixContext"):
        self.ctx = ctx

    async def send(self, content=None, *, embed=None, view=None, wait=False, ephemeral=False, allowed_mentions=None, **_):
        kwargs = {k: v for k, v in (("content", content), ("embed", embed), ("view", view), ("allowed_mentions", allowed_mentions)) if v is not None}
        sent = await self.ctx.channel.send(**kwargs)
        self.ctx.sent = sent
        return sent


class PrefixContext:
    def __init__(self, message: discord.Message):
        self.message = message
        self.guild = message.guild
        self.channel = message.channel
        self.user = message.author
        self.sent = None
        self.response = _PrefixResponse(self)
        self.followup = _PrefixFollowup(self)

    async def original_response(self):
        return self.sent

    async def edit_original_response(self, **kwargs):
        if self.sent:
            await self.sent.edit(**kwargs)


_ALIASES = {"ship": "ship", "choose": "choose", "cat": "cat", "dog": "dog", "meme": "meme", "joke": "joke", "fact": "fact"}


async def on_message(message: discord.Message):
    # Intentionally left blank: no persistent economy/leveling state.
    return None


async def handle_prefix(message: discord.Message, command: str, args: list, privileged: bool = False) -> bool:
    if message.guild is None:
        return False

    cmd = (_ALIASES.get(command.lower(), command.lower()))
    if cmd not in _COMMANDS:
        return False

    args = list(args)
    try:
        if cmd == "ship":
            if len(args) < 1:
                raise ValueError("Usage: !v ship @member [@member]")
            first = message.guild.get_member(int(args[0].strip("<@!>"))) if args[0].strip("<@!>").isdigit() else None
            second = None
            if len(args) > 1:
                second_id = args[1].strip("<@!>")
                second = message.guild.get_member(int(second_id)) if second_id.isdigit() else None
            if not first:
                raise ValueError("Member not found")
            return await _COMMANDS[cmd].callback(PrefixContext(message), first=first, second=second)

        if cmd == "choose":
            return await _COMMANDS[cmd].callback(PrefixContext(message), options=" ".join(args))

        return await _COMMANDS[cmd].callback(PrefixContext(message))
    except Exception as exc:
        await message.channel.send(f"❌ {exc}")
        return True


async def handle_prefix_command(message: discord.Message, command: str, args: list) -> None:
    await handle_prefix(message, command, args)


def safewin(value: str = "win"):
    """Keep the bot non-gambling and deterministic when a win result is requested."""
    return value if value.lower() in {"win", "winner", "victory"} else value
