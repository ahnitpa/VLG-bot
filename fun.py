import os
import random
import sqlite3
import time
from typing import Optional

import discord
from discord import app_commands

DB_PATH = os.environ.get("DB_PATH", "bot.db")
COIN = "🪙"

# SQLite setup
_db = sqlite3.connect(DB_PATH)
_db.row_factory = sqlite3.Row
_db.executescript("""
CREATE TABLE IF NOT EXISTS users (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    coins INTEGER NOT NULL DEFAULT 0,
    bank INTEGER NOT NULL DEFAULT 0,
    xp INTEGER NOT NULL DEFAULT 0,
    last_daily REAL NOT NULL DEFAULT 0,
    daily_streak INTEGER NOT NULL DEFAULT 0,
    last_work REAL NOT NULL DEFAULT 0,
    last_msg REAL NOT NULL DEFAULT 0,
    boost_until REAL NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE TABLE IF NOT EXISTS inventory (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    item TEXT NOT NULL,
    qty INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (guild_id, user_id, item)
);
""")
_db.commit()

_commands = {}
DAILY_COOLDOWN = 86400
WORK_COOLDOWN = 3600
XP_COOLDOWN = 60

SHOP = {
    "xp_boost": {"name": "XP Boost", "emoji": "⚡", "price": 1500, "desc": "Double chat XP for one hour."},
    "mystery_box": {"name": "Mystery Box", "emoji": "🎁", "price": 400, "desc": "Win a safe bonus prize from 100 to 2500 coins."},
}


def get_user(guild_id: int, user_id: int) -> sqlite3.Row:
    _db.execute("INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
    return _db.execute("SELECT * FROM users WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()


def add_coins(guild_id: int, user_id: int, amount: int):
    get_user(guild_id, user_id)
    _db.execute("UPDATE users SET coins = MAX(0, coins + ?) WHERE guild_id=? AND user_id=?", (amount, guild_id, user_id))
    _db.commit()


def take_coins(guild_id: int, user_id: int, amount: int) -> bool:
    if amount <= 0:
        return False
    get_user(guild_id, user_id)
    cur = _db.execute(
        "UPDATE users SET coins = coins - ? WHERE guild_id=? AND user_id=? AND coins >= ?",
        (amount, guild_id, user_id, amount),
    )
    _db.commit()
    return cur.rowcount == 1


def set_field(guild_id: int, user_id: int, **fields):
    get_user(guild_id, user_id)
    cols = list(fields.keys())
    if not cols:
        return
    sql = "UPDATE users SET " + ", ".join(f"{c}= ?" for c in cols) + " WHERE guild_id=? AND user_id=?"
    _db.execute(sql, list(fields.values()) + [guild_id, user_id])
    _db.commit()


def inv_add(guild_id: int, user_id: int, item: str, qty: int = 1):
    _db.execute(
        "INSERT INTO inventory (guild_id, user_id, item, qty) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(guild_id, user_id, item) DO UPDATE SET qty = qty + excluded.qty",
        (guild_id, user_id, item, qty),
    )
    _db.commit()


def inv_take(guild_id: int, user_id: int, item: str, qty: int = 1) -> bool:
    cur = _db.execute(
        "UPDATE inventory SET qty = qty - ? WHERE guild_id=? AND user_id=? AND item=? AND qty >= ?",
        (qty, guild_id, user_id, item, qty),
    )
    ok = cur.rowcount == 1
    if ok:
        _db.execute("DELETE FROM inventory WHERE guild_id=? AND user_id=? AND item=? AND qty <= 0", (guild_id, user_id, item))
    _db.commit()
    return ok


def move_money(guild_id: int, user_id: int, amount: int, to_bank: bool) -> bool:
    get_user(guild_id, user_id)
    if to_bank:
        sql = "UPDATE users SET coins=coins-?, bank=bank+? WHERE guild_id=? AND user_id=? AND coins>=?"
    else:
        sql = "UPDATE users SET bank=bank-?, coins=coins+? WHERE guild_id=? AND user_id=? AND bank>=?"
    cur = _db.execute(sql, (amount, amount, guild_id, user_id, amount))
    _db.commit()
    return cur.rowcount == 1


def xp_needed(level: int) -> int:
    return 5 * level ** 2 + 50 * level + 100


def level_from_xp(total_xp: int):
    level = 0
    while total_xp >= xp_needed(level):
        total_xp -= xp_needed(level)
        level += 1
    return level, total_xp


def progress_bar(current: int, total: int, width: int = 12) -> str:
    filled = int(width * current / total) if total else 0
    return "█" * filled + "░" * (width - filled)


def fmt_duration(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    parts = []
    if h:
        parts.append(f"{h}h")
    if m:
        parts.append(f"{m}m")
    if s or not parts:
        parts.append(f"{s}s")
    return " ".join(parts)


async def reply_error(interaction: discord.Interaction, text: str):
    await interaction.response.send_message(text, ephemeral=True)


async def apply_level_roles(member: discord.Member, level: int):
    # safe default: no extra role manager in this trimmed build
    return None


async def on_message(message: discord.Message):
    if message.author.bot or message.guild is None:
        return
    guild_id, user_id = message.guild.id, message.author.id
    row = get_user(guild_id, user_id)
    now = time.time()
    if now - row["last_msg"] < XP_COOLDOWN:
        return
    gain = random.randint(15, 25)
    if row["boost_until"] > now:
        gain *= 2
    old_level, _ = level_from_xp(row["xp"])
    _db.execute("UPDATE users SET xp = xp + ?, last_msg = ? WHERE guild_id=? AND user_id=?", (gain, now, guild_id, user_id))
    _db.commit()
    new_level, _ = level_from_xp(row["xp"] + gain)
    if new_level > old_level:
        reward = new_level * 50
        add_coins(guild_id, user_id, reward)
        try:
            await message.channel.send(f"🎉 {message.author.mention} reached **level {new_level}**! (+{reward:,} {COIN})")
        except discord.HTTPException:
            pass


# Safe economy/game commands only; no gambling or betting features

def setup(bot: discord.Client, tree: app_commands.CommandTree):
    def slash(name: str, description: str):
        def deco(fn):
            fn = app_commands.guild_only()(fn)
            cmd = tree.command(name=name, description=description)(fn)
            _commands[name] = cmd
            return cmd
        return deco

    def item_choices(only: Optional[list] = None):
        return [app_commands.Choice(name=f"{v['emoji']} {v['name']}", value=k) for k, v in SHOP.items() if only is None or k in only]

    @slash("balance", "Check your coin balance")
    @app_commands.describe(member="Whose balance to view (leave empty for yourself)")
    async def balance(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        row = get_user(interaction.guild.id, target.id)
        level, _ = level_from_xp(row["xp"])
        embed = discord.Embed(title=f"{target.display_name}'s balance", color=discord.Color.gold())
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Wallet", value=f"{COIN} {row['coins']:,}")
        embed.add_field(name="Bank", value=f"🏦 {row['bank']:,}")
        embed.add_field(name="Net worth", value=f"💰 {row['coins'] + row['bank']:,}")
        embed.set_footer(text=f"Level {level}")
        await interaction.response.send_message(embed=embed)

    @slash("daily", "Claim your daily reward")
    async def daily(interaction: discord.Interaction):
        gid, uid = interaction.guild.id, interaction.user.id
        row = get_user(gid, uid)
        now = time.time()
        elapsed = now - row["last_daily"]
        if elapsed < DAILY_COOLDOWN:
            return await reply_error(interaction, f"⏳ Already claimed today. Back in **{fmt_duration(DAILY_COOLDOWN - elapsed)}**.")
        streak = row["daily_streak"] + 1 if elapsed < DAILY_COOLDOWN * 2 else 1
        reward = 200 + min(streak, 30) * 25
        add_coins(gid, uid, reward)
        set_field(gid, uid, last_daily=now, daily_streak=streak)
        await interaction.response.send_message(f"📅 Claimed **{reward:,}** {COIN}. Streak: **{streak}** 🔥")

    @slash("work", "Do a job for coins")
    async def work(interaction: discord.Interaction):
        gid, uid = interaction.guild.id, interaction.user.id
        row = get_user(gid, uid)
        now = time.time()
        elapsed = now - row["last_work"]
        if elapsed < WORK_COOLDOWN:
            return await reply_error(interaction, f"⏳ Try again in **{fmt_duration(WORK_COOLDOWN - elapsed)}**.")
        amount = random.randint(50, 250)
        add_coins(gid, uid, amount)
        set_field(gid, uid, last_work=now)
        await interaction.response.send_message(f"💼 You worked hard and earned **{amount:,}** {COIN}!")

    @slash("pay", "Send coins to another member")
    @app_commands.describe(member="Who gets the coins", amount="How many coins to send")
    async def pay(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1]):
        if member.bot or member.id == interaction.user.id:
            return await reply_error(interaction, "❌ Pick another non-bot member.")
        gid = interaction.guild.id
        if not take_coins(gid, interaction.user.id, amount):
            return await reply_error(interaction, "❌ Not enough coins in your wallet.")
        add_coins(gid, member.id, amount)
        await interaction.response.send_message(f"💸 {interaction.user.mention} sent **{amount:,}** {COIN} to {member.mention}!")

    @slash("deposit", "Move coins to your bank")
    @app_commands.describe(amount="A number, 'half' or 'all'")
    async def deposit(interaction: discord.Interaction, amount: str):
        gid, uid = interaction.guild.id, interaction.user.id
        wallet = get_user(gid, uid)["coins"]
        t = amount.strip().lower().replace(",", "")
        if t in ("all", "max"):
            n = wallet if wallet > 0 else None
        elif t == "half":
            n = wallet // 2 or None
        else:
            n = int(t) if t.isdigit() and int(t) > 0 else None
        if n is None or not move_money(gid, uid, n, to_bank=True):
            return await reply_error(interaction, "❌ Invalid amount or not enough coins.")
        await interaction.response.send_message(f"🏦 Deposited **{n:,}** {COIN}.")

    @slash("withdraw", "Take coins from your bank")
    @app_commands.describe(amount="A number, 'half' or 'all'")
    async def withdraw(interaction: discord.Interaction, amount: str):
        gid, uid = interaction.guild.id, interaction.user.id
        bank = get_user(gid, uid)["bank"]
        t = amount.strip().lower().replace(",", "")
        if t in ("all", "max"):
            n = bank if bank > 0 else None
        elif t == "half":
            n = bank // 2 or None
        else:
            n = int(t) if t.isdigit() and int(t) > 0 else None
        if n is None or not move_money(gid, uid, n, to_bank=False):
            return await reply_error(interaction, "❌ Invalid amount or not enough coins in your bank.")
        await interaction.response.send_message(f"💵 Withdrew **{n:,}** {COIN}.")

    @slash("rank", "Show your level progress")
    @app_commands.describe(member="Whose rank to view (leave empty for yourself)")
    async def rank(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        row = get_user(interaction.guild.id, target.id)
        level, into = level_from_xp(row["xp"])
        need = xp_needed(level)
        position = _db.execute("SELECT COUNT(*)+1 AS p FROM users WHERE guild_id=? AND xp>?", (interaction.guild.id, row["xp"])).fetchone()["p"]
        embed = discord.Embed(title=f"{target.display_name}'s rank", color=target.color if target.color.value else discord.Color.blurple())
        embed.add_field(name="Level", value=str(level))
        embed.add_field(name="Server rank", value=f"#{position}")
        embed.add_field(name="Total XP", value=f"{row['xp']:,}")
        embed.add_field(name="Progress", value=f"`{progress_bar(into, need)}` {into:,}/{need:,} XP", inline=False)
        if row["boost_until"] > time.time():
            embed.set_footer(text=f"⚡ 2x XP boost active for {fmt_duration(row['boost_until'] - time.time())}")
        await interaction.response.send_message(embed=embed)

    @slash("leaderboard", "See the richest or highest-level members")
    @app_commands.describe(kind="What to rank by")
    @app_commands.choices(kind=[app_commands.Choice(name="Net worth", value="coins"), app_commands.Choice(name="Level / XP", value="xp")])
    async def leaderboard(interaction: discord.Interaction, kind: Optional[app_commands.Choice[str]] = None):
        mode = kind.value if kind else "coins"
        if mode == "xp":
            rows = _db.execute("SELECT user_id, xp AS score FROM users WHERE guild_id=? AND xp>0 ORDER BY xp DESC LIMIT 10", (interaction.guild.id,)).fetchall()
            title = "🏆 Level leaderboard"
        else:
            rows = _db.execute("SELECT user_id, coins+bank AS score FROM users WHERE guild_id=? AND coins+bank>0 ORDER BY score DESC LIMIT 10", (interaction.guild.id,)).fetchall()
            title = "💰 Richest members"
        if not rows:
            return await reply_error(interaction, "Nobody is on the leaderboard yet.")
        lines = []
        for i, r in enumerate(rows):
            prefix = ["🥇", "🥈", "🥉"][i] if i < 3 else f"`{i + 1}.`"
            value = f"Level {level_from_xp(r['score'])[0]} ({r['score']:,} XP)" if mode == "xp" else f"{COIN} {r['score']:,}"
            lines.append(f"{prefix} <@{r['user_id']}> - {value}")
        await interaction.response.send_message(embed=discord.Embed(title=title, description="\n".join(lines), color=discord.Color.gold()))

    @slash("shop", "Browse safe items you can buy")
    async def shop(interaction: discord.Interaction):
        embed = discord.Embed(title="🛒 Shop", description="Buy with `/buy`.", color=discord.Color.blurple())
        for key, item in SHOP.items():
            embed.add_field(name=f"{item['emoji']} {item['name']} - {item['price']:,} {COIN}", value=item["desc"], inline=False)
        await interaction.response.send_message(embed=embed)

    @slash("buy", "Buy an item from the shop")
    @app_commands.describe(item="What to buy", quantity="How many (default 1)")
    @app_commands.choices(item=[app_commands.Choice(name=f"{v['emoji']} {v['name']}", value=k) for k, v in SHOP.items()])
    async def buy(interaction: discord.Interaction, item: app_commands.Choice[str], quantity: app_commands.Range[int, 1, 20] = 1):
        info = SHOP[item.value]
        cost = info["price"] * quantity
        if not take_coins(interaction.guild.id, interaction.user.id, cost):
            return await reply_error(interaction, f"❌ You need **{cost:,}** {COIN}.")
        inv_add(interaction.guild.id, interaction.user.id, item.value, quantity)
        await interaction.response.send_message(f"✅ Bought **{quantity}x {info['emoji']} {info['name']}** for **{cost:,}** {COIN}.")

    @slash("inventory", "See your items")
    @app_commands.describe(member="Whose inventory to view (leave empty for yourself)")
    async def inventory(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        rows = _db.execute("SELECT item, qty FROM inventory WHERE guild_id=? AND user_id=? AND qty>0", (interaction.guild.id, target.id)).fetchall()
        if not rows:
            return await interaction.response.send_message(f"{target.display_name} owns nothing yet. Try `/shop`!")
        lines = [f"{SHOP[r['item']]['emoji']} **{SHOP[r['item']]['name']}** x{r['qty']}" for r in rows if r["item"] in SHOP]
        await interaction.response.send_message(embed=discord.Embed(title=f"🎒 {target.display_name}'s inventory", description="\n".join(lines), color=discord.Color.blurple()))

    @slash("use", "Use a shop item")
    @app_commands.describe(item="The item to use")
    @app_commands.choices(item=[app_commands.Choice(name=f"{v['emoji']} {v['name']}", value=k) for k, v in SHOP.items()])
    async def use(interaction: discord.Interaction, item: app_commands.Choice[str]):
        gid, uid = interaction.guild.id, interaction.user.id
        if not inv_take(gid, uid, item.value):
            return await reply_error(interaction, "❌ You don't own that item.")
        if item.value == "xp_boost":
            start = max(time.time(), get_user(gid, uid)["boost_until"])
            set_field(gid, uid, boost_until=start + 3600)
            return await interaction.response.send_message("⚡ **XP Boost activated!** You earn double chat XP for the next hour.")
        prize = random.choices([100, 200, 300, 500, 1000, 2500], weights=[30, 25, 20, 13, 9, 3])[0]
        add_coins(gid, uid, prize)
        await interaction.response.send_message(f"🎁 You opened the Mystery Box and found **{prize:,}** {COIN}!")

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
        embed = discord.Embed(title=f"💞 {n1} x {n2}", description=f"**Ship name:** {ship_name}\n`{progress_bar(pct, 100, 20)}` **{pct}%**\n{verdict}", color=discord.Color.magenta())
        await interaction.response.send_message(embed=embed)

    @slash("choose", "Let the bot pick between options")
    @app_commands.describe(options="Separate options with commas, e.g. pizza, sushi, tacos")
    async def choose(interaction: discord.Interaction, options: str):
        parts = [p.strip() for p in options.replace(" or ", ",").split(",") if p.strip()]
        if len(parts) < 2:
            return await reply_error(interaction, "❌ Give me at least two options separated by commas.")
        await interaction.response.send_message(f"🤔 I choose... **{random.choice(parts)}**!", allowed_mentions=discord.AllowedMentions.none())

    # safe prefix help
    global PREFIX_HELP
    PREFIX_HELP = (
        "**🎮 Safe economy & fun (`!v`)**\n"
        "**Economy:** `balance [@m]`, `daily`, `work`, `pay @m <amt>`, `deposit <amt|all>`, `withdraw <amt|all>`\n"
        "**Levels:** `rank [@m]`, `leaderboard [coins|xp]`\n"
        "**Shop:** `shop`, `buy <item> [qty]`, `inventory [@m]`, `use <item>`\n"
        "**Random:** `cat`, `dog`, `meme`, `joke`, `fact`, `ship @a [@b]`, `choose a, b, c`\n"
        "Aliases: `bal`, `lb`, `inv`, `lvl`, `level`."
    )


PREFIX_HELP = ""  # gets set in setup()


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


_ALIASES = {"bal": "balance", "lb": "leaderboard", "top": "leaderboard", "inv": "inventory", "lvl": "rank", "level": "rank"}


def _wallet(message: discord.Message) -> int:
    return get_user(message.guild.id, message.author.id)["coins"]


async def handle_prefix(message: discord.Message, command: str, args: list, privileged: bool = False) -> bool:
    if message.guild is None or not _commands:
        return False
    command = command.lower()
    command = _ALIASES.get(command, command)
    if command not in _commands:
        return False

    if command in {"addcoins"} and not (privileged or message.author.guild_permissions.manage_guild):
        await message.channel.send("❌ Access Denied: Manage Server required.")
        return True

    args = list(args)
    try:
        if command == "balance":
            if args:
                target_id = args[0].strip("<@!>")
                target = message.guild.get_member(int(target_id)) if target_id.isdigit() else None
                if target is None:
                    raise ValueError("Member not found")
                return await _commands[command].callback(PrefixContext(message), member=target)
            return await _commands[command].callback(PrefixContext(message))
        if command == "rank":
            if args:
                target_id = args[0].strip("<@!>")
                target = message.guild.get_member(int(target_id)) if target_id.isdigit() else None
                if target is None:
                    raise ValueError("Member not found")
                return await _commands[command].callback(PrefixContext(message), member=target)
            return await _commands[command].callback(PrefixContext(message))
        if command == "inventory":
            if args:
                target_id = args[0].strip("<@!>")
                target = message.guild.get_member(int(target_id)) if target_id.isdigit() else None
                if target is None:
                    raise ValueError("Member not found")
                return await _commands[command].callback(PrefixContext(message), member=target)
            return await _commands[command].callback(PrefixContext(message))
        if command == "ship":
            if len(args) < 1:
                raise ValueError("Usage: !v ship @member [@member]")
            first = message.guild.get_member(int(args[0].strip("<@!>"))) if args[0].strip("<@!>").isdigit() else None
            second = None
            if len(args) > 1:
                second_id = args[1].strip("<@!>")
                second = message.guild.get_member(int(second_id)) if second_id.isdigit() else None
            if not first:
                raise ValueError("Member not found")
            return await _commands[command].callback(PrefixContext(message), first=first, second=second)
        if command == "choose":
            return await _commands[command].callback(PrefixContext(message), options=" ".join(args))
        if command in {"shop", "daily", "work", "leaderboard", "cat", "dog", "meme", "joke", "fact"}:
            return await _commands[command].callback(PrefixContext(message))
        if command == "pay":
            if len(args) < 2:
                raise ValueError("Usage: !v pay @member <amount>")
            target = message.guild.get_member(int(args[0].strip("<@!>"))) if args[0].strip("<@!>").isdigit() else None
            if not target:
                raise ValueError("Member not found")
            return await _commands[command].callback(PrefixContext(message), member=target, amount=int(args[1]))
        if command in {"deposit", "withdraw"}:
            if not args:
                raise ValueError(f"Usage: !v {command} <amount|half|all>")
            return await _commands[command].callback(PrefixContext(message), amount=args[0])
        if command in {"buy", "use"}:
            if not args:
                raise ValueError(f"Usage: !v {command} <item>")
            return await _commands[command].callback(PrefixContext(message), item=app_commands.Choice(name=args[0], value=args[0]), quantity=1)
        raise ValueError(f"Unsupported prefix command: {command}")
    except Exception as exc:
        await message.channel.send(f"❌ {exc}")
        return True


# simple default function for compatibility with `main (1).py`
async def handle_prefix_command(message: discord.Message, command: str, args: list) -> None:
    await handle_prefix(message, command, args)


def safewin(value: str = "win"):
    """Keep the bot non-gambling and deterministic when a win result is requested."""
    return value if value.lower() in {"win", "winner", "victory"} else value
