"""
fun_core.py - config, SQLite database helpers, small helpers and chat XP for the fun module.
Used by fun.py and fun_games.py.
"""
import asyncio
import os
import random
import sqlite3
import time
from typing import Optional

import aiohttp
import discord

# ====================== CONFIG ======================
DB_PATH = os.environ.get("DB_PATH", "bot.db")
COIN = "🪙"

# Filled in by setup(); lets the !v prefix handler reuse the slash command code
_commands: dict = {}

DAILY_COOLDOWN = 86400
WORK_COOLDOWN = 3600
STEAL_COOLDOWN = 600
XP_COOLDOWN = 60
MAX_BET = 10000

SHOP = {
    "padlock": {"name": "Padlock", "emoji": "🔒", "price": 500,
                "desc": "Automatically blocks the next steal attempt against you."},
    "lockpick": {"name": "Lockpick", "emoji": "🗝️", "price": 750,
                 "desc": "Used automatically on your next steal: success chance 40% -> 65%."},
    "xp_boost": {"name": "XP Boost", "emoji": "⚡", "price": 1500,
                 "desc": "Use it for 2x chat XP for one hour."},
    "mystery_box": {"name": "Mystery Box", "emoji": "🎁", "price": 400,
                    "desc": "Use it to win between 100 and 2,500 coins."},
}

JOBS = [
    "You delivered pizzas on a scooter with questionable brakes and earned **{amount}** coins.",
    "You debugged a stranger's code and they paid you **{amount}** coins.",
    "You walked a pack of very confused dogs and earned **{amount}** coins.",
    "You streamed to 3 viewers (one was your mom) and got **{amount}** coins in donations.",
    "You sold lemonade at an unreasonable markup and made **{amount}** coins.",
    "You mowed a lawn that turned out to be a golf course. They still paid you **{amount}** coins.",
    "You won a hot-dog eating contest and pocketed **{amount}** coins.",
]

FALLBACK_TRIVIA = [
    {"q": "What is the capital of Denmark?", "a": "Copenhagen", "w": ["Aarhus", "Odense", "Aalborg"], "d": "easy", "c": "Geography"},
    {"q": "How many players are on the field for one soccer team?", "a": "11", "w": ["9", "10", "12"], "d": "easy", "c": "Sports"},
    {"q": "What planet is known as the Red Planet?", "a": "Mars", "w": ["Venus", "Jupiter", "Mercury"], "d": "easy", "c": "Science"},
    {"q": "In computing, what does 'HTTP' stand for?", "a": "HyperText Transfer Protocol",
     "w": ["High Transfer Text Protocol", "HyperText Transmission Process", "Host Transfer Terminal Protocol"], "d": "medium", "c": "Computers"},
    {"q": "Which element has the chemical symbol 'Au'?", "a": "Gold", "w": ["Silver", "Argon", "Aluminium"], "d": "medium", "c": "Science"},
]

# ====================== DATABASE ======================
db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
db.executescript("""
CREATE TABLE IF NOT EXISTS users (
    guild_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    coins INTEGER NOT NULL DEFAULT 0,
    bank INTEGER NOT NULL DEFAULT 0,
    xp INTEGER NOT NULL DEFAULT 0,
    last_daily REAL NOT NULL DEFAULT 0,
    daily_streak INTEGER NOT NULL DEFAULT 0,
    last_work REAL NOT NULL DEFAULT 0,
    last_steal REAL NOT NULL DEFAULT 0,
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
CREATE TABLE IF NOT EXISTS level_roles (
    guild_id INTEGER NOT NULL,
    level INTEGER NOT NULL,
    role_id INTEGER NOT NULL,
    PRIMARY KEY (guild_id, level)
);
""")
db.commit()

_SETTABLE = {"last_daily", "daily_streak", "last_work", "last_steal", "last_msg", "boost_until"}


def get_user(guild_id: int, user_id: int) -> sqlite3.Row:
    db.execute("INSERT OR IGNORE INTO users (guild_id, user_id) VALUES (?, ?)", (guild_id, user_id))
    return db.execute("SELECT * FROM users WHERE guild_id=? AND user_id=?", (guild_id, user_id)).fetchone()


def add_coins(guild_id: int, user_id: int, amount: int) -> None:
    get_user(guild_id, user_id)
    db.execute("UPDATE users SET coins = MAX(0, coins + ?) WHERE guild_id=? AND user_id=?",
               (amount, guild_id, user_id))
    db.commit()


def take_coins(guild_id: int, user_id: int, amount: int) -> bool:
    """Atomically removes coins. Returns False if the wallet can't cover it."""
    if amount <= 0:
        return False
    get_user(guild_id, user_id)
    cur = db.execute("UPDATE users SET coins = coins - ? WHERE guild_id=? AND user_id=? AND coins >= ?",
                     (amount, guild_id, user_id, amount))
    db.commit()
    return cur.rowcount == 1


def set_field(guild_id: int, user_id: int, **fields) -> None:
    get_user(guild_id, user_id)
    cols = [c for c in fields if c in _SETTABLE]
    if not cols:
        return
    sql = "UPDATE users SET " + ", ".join(f"{c}=?" for c in cols) + " WHERE guild_id=? AND user_id=?"
    db.execute(sql, [fields[c] for c in cols] + [guild_id, user_id])
    db.commit()


def inv_qty(guild_id: int, user_id: int, item: str) -> int:
    row = db.execute("SELECT qty FROM inventory WHERE guild_id=? AND user_id=? AND item=?",
                     (guild_id, user_id, item)).fetchone()
    return row["qty"] if row else 0


def inv_add(guild_id: int, user_id: int, item: str, qty: int = 1) -> None:
    db.execute(
        "INSERT INTO inventory (guild_id, user_id, item, qty) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(guild_id, user_id, item) DO UPDATE SET qty = qty + excluded.qty",
        (guild_id, user_id, item, qty))
    db.commit()


def inv_take(guild_id: int, user_id: int, item: str, qty: int = 1) -> bool:
    cur = db.execute(
        "UPDATE inventory SET qty = qty - ? WHERE guild_id=? AND user_id=? AND item=? AND qty >= ?",
        (qty, guild_id, user_id, item, qty))
    ok = cur.rowcount == 1
    if ok:
        db.execute("DELETE FROM inventory WHERE guild_id=? AND user_id=? AND item=? AND qty <= 0",
                   (guild_id, user_id, item))
    db.commit()
    return ok


def move_money(guild_id: int, user_id: int, amount: int, to_bank: bool) -> bool:
    get_user(guild_id, user_id)
    if to_bank:
        sql = "UPDATE users SET coins=coins-?, bank=bank+? WHERE guild_id=? AND user_id=? AND coins>=?"
    else:
        sql = "UPDATE users SET bank=bank-?, coins=coins+? WHERE guild_id=? AND user_id=? AND bank>=?"
    cur = db.execute(sql, (amount, amount, guild_id, user_id, amount))
    db.commit()
    return cur.rowcount == 1


# ====================== SMALL HELPERS ======================
def xp_needed(level: int) -> int:
    """XP required to go from `level` to `level + 1`."""
    return 5 * level ** 2 + 50 * level + 100


def level_from_xp(total_xp: int):
    """Returns (level, xp_into_current_level)."""
    level = 0
    while total_xp >= xp_needed(level):
        total_xp -= xp_needed(level)
        level += 1
    return level, total_xp


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


def parse_amount(text: str, available: int) -> Optional[int]:
    t = text.strip().lower().replace(",", "")
    if t in ("all", "max"):
        return available if available > 0 else None
    if t == "half":
        return (available // 2) or None
    n = int(t) if t.isdigit() else 0
    return n if n > 0 else None


def progress_bar(current: int, total: int, width: int = 12) -> str:
    filled = int(width * current / total) if total else 0
    return "█" * filled + "░" * (width - filled)


async def fetch_json(url: str, **params):
    try:
        timeout = aiohttp.ClientTimeout(total=8)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, params=params or None) as resp:
                if resp.status != 200:
                    return None
                return await resp.json(content_type=None)
    except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
        return None


async def reply_error(interaction: discord.Interaction, text: str) -> None:
    await interaction.response.send_message(text, ephemeral=True)


# ====================== XP FROM CHATTING ======================
async def apply_level_roles(member: discord.Member, level: int) -> None:
    rows = db.execute("SELECT role_id FROM level_roles WHERE guild_id=? AND level<=?",
                      (member.guild.id, level)).fetchall()
    to_add = []
    for row in rows:
        role = member.guild.get_role(row["role_id"])
        if role and role not in member.roles and role < member.guild.me.top_role:
            to_add.append(role)
    if to_add:
        try:
            await member.add_roles(*to_add, reason="Level reward")
        except discord.HTTPException:
            pass


async def on_message(message: discord.Message) -> None:
    """Call this from your bot's on_message to award chat XP."""
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
    db.execute("UPDATE users SET xp = xp + ?, last_msg = ? WHERE guild_id=? AND user_id=?",
               (gain, now, guild_id, user_id))
    db.commit()
    new_level, _ = level_from_xp(row["xp"] + gain)

    if new_level > old_level:
        reward = new_level * 50
        add_coins(guild_id, user_id, reward)
        try:
            await message.channel.send(
                f"🎉 {message.author.mention} reached **level {new_level}**! (+{reward:,} {COIN})")
        except discord.HTTPException:
            pass
        if isinstance(message.author, discord.Member):
            await apply_level_roles(message.author, new_level)


