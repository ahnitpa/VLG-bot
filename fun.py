"""
fun.py - Fun & engagement module (economy, leveling, shop, gambling, mini-games, content).

Hook it into your main file with:
    import fun
    fun.setup(bot, tree)                # right after music.setup(bot, tree)
and, inside your on_message (after the bot/guild guard):
    await fun.on_message(message)       # gives XP for chatting

Data is stored in SQLite (default file: bot.db, override with the DB_PATH env var).
"""
import asyncio
import hashlib
import os
import random
import sqlite3
import time
from typing import Optional
from urllib.parse import unquote

import aiohttp
import discord
from discord import app_commands

# ====================== CONFIG ======================
DB_PATH = os.environ.get("DB_PATH", "bot.db")
COIN = "🪙"

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


# ====================== BLACKJACK ======================
SUITS = ["♠", "♥", "♦", "♣"]
RANKS = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]


def card_value(rank: str) -> int:
    if rank == "A":
        return 11
    if rank in ("J", "Q", "K"):
        return 10
    return int(rank)


def hand_value(hand) -> int:
    total = sum(card_value(r) for r, _ in hand)
    aces = sum(1 for r, _ in hand if r == "A")
    while total > 21 and aces:
        total -= 10
        aces -= 1
    return total


def fmt_hand(hand) -> str:
    return " ".join(f"`{r}{s}`" for r, s in hand)


BJ_RESULTS = {
    "blackjack": ("Blackjack! 🎉", discord.Color.gold()),
    "win": ("You win!", discord.Color.green()),
    "push": ("Push - your bet is returned.", discord.Color.light_grey()),
    "lose": ("Dealer wins.", discord.Color.red()),
    "bust": ("Bust!", discord.Color.red()),
    "timeout": ("Timed out - bet forfeited.", discord.Color.dark_grey()),
}


class BlackjackView(discord.ui.View):
    def __init__(self, user: discord.abc.User, guild_id: int, bet: int):
        super().__init__(timeout=90)
        self.user = user
        self.guild_id = guild_id
        self.bet = bet
        self.deck = [(r, s) for r in RANKS for s in SUITS] * 2
        random.shuffle(self.deck)
        self.player = [self.deck.pop(), self.deck.pop()]
        self.dealer = [self.deck.pop(), self.deck.pop()]
        self.done = False
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    def embed(self, reveal: bool = False, footer: Optional[str] = None,
              color: Optional[discord.Color] = None) -> discord.Embed:
        e = discord.Embed(title="🃏 Blackjack", color=color or discord.Color.blurple())
        e.add_field(name=f"Your hand ({hand_value(self.player)})", value=fmt_hand(self.player), inline=False)
        if reveal:
            e.add_field(name=f"Dealer ({hand_value(self.dealer)})", value=fmt_hand(self.dealer), inline=False)
        else:
            r, s = self.dealer[0]
            e.add_field(name="Dealer", value=f"`{r}{s}` `??`", inline=False)
        e.set_footer(text=footer or f"Bet: {self.bet:,} coins")
        return e

    def finish(self, outcome: str) -> discord.Embed:
        self.done = True
        for child in self.children:
            child.disabled = True
        payout = {
            "blackjack": int(self.bet * 2.5), "win": self.bet * 2, "push": self.bet,
            "lose": 0, "bust": 0, "timeout": 0,
        }[outcome]
        if payout:
            add_coins(self.guild_id, self.user.id, payout)
        text, color = BJ_RESULTS[outcome]
        return self.embed(reveal=True, footer=f"{text} ({payout - self.bet:+,} coins)", color=color)

    def dealer_outcome(self) -> str:
        player_total = hand_value(self.player)
        while hand_value(self.dealer) < 17:
            self.dealer.append(self.deck.pop())
        dealer_total = hand_value(self.dealer)
        if dealer_total > 21 or player_total > dealer_total:
            return "win"
        return "push" if player_total == dealer_total else "lose"

    async def _stand(self, interaction: discord.Interaction) -> None:
        await interaction.response.edit_message(embed=self.finish(self.dealer_outcome()), view=self)
        self.stop()

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.green, emoji="➕")
    async def hit(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.append(self.deck.pop())
        total = hand_value(self.player)
        if total > 21:
            await interaction.response.edit_message(embed=self.finish("bust"), view=self)
            self.stop()
        elif total == 21:
            await self._stand(interaction)
        else:
            await interaction.response.edit_message(embed=self.embed(), view=self)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.blurple, emoji="✋")
    async def stand(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._stand(interaction)

    async def on_timeout(self) -> None:
        if self.done or not self.message:
            return
        try:
            await self.message.edit(embed=self.finish("timeout"), view=self)
        except discord.HTTPException:
            pass


# ====================== ROCK PAPER SCISSORS ======================
RPS_EMOJI = {"rock": "🪨", "paper": "📄", "scissors": "✂️"}
RPS_BEATS = {"rock": "scissors", "paper": "rock", "scissors": "paper"}


class RPSView(discord.ui.View):
    def __init__(self, user: discord.abc.User, guild_id: int, bet: int):
        super().__init__(timeout=30)
        self.user = user
        self.guild_id = guild_id
        self.bet = bet
        self.done = False
        self.message: Optional[discord.Message] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("This isn't your game!", ephemeral=True)
            return False
        return True

    async def play(self, interaction: discord.Interaction, choice: str) -> None:
        self.done = True
        bot_choice = random.choice(list(RPS_BEATS))
        line = f"You: {RPS_EMOJI[choice]} **{choice}**  vs  Me: {RPS_EMOJI[bot_choice]} **{bot_choice}**\n"
        if choice == bot_choice:
            result = "It's a tie!"
            if self.bet:
                add_coins(self.guild_id, self.user.id, self.bet)
                result += " Bet returned."
        elif RPS_BEATS[choice] == bot_choice:
            result = "You win! 🎉"
            if self.bet:
                add_coins(self.guild_id, self.user.id, self.bet * 2)
                result += f" (+{self.bet:,} {COIN})"
        else:
            result = "I win! 😎"
            if self.bet:
                result += f" (-{self.bet:,} {COIN})"
        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(content=line + result, view=self)
        self.stop()

    @discord.ui.button(label="Rock", emoji="🪨", style=discord.ButtonStyle.secondary)
    async def rock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "rock")

    @discord.ui.button(label="Paper", emoji="📄", style=discord.ButtonStyle.secondary)
    async def paper(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "paper")

    @discord.ui.button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.secondary)
    async def scissors(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.play(interaction, "scissors")

    async def on_timeout(self) -> None:
        if self.done:
            return
        if self.bet:
            add_coins(self.guild_id, self.user.id, self.bet)  # never played, refund
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⌛ You took too long. Bet refunded.", view=self)
            except discord.HTTPException:
                pass


# ====================== TIC-TAC-TOE ======================
class TTTButton(discord.ui.Button):
    def __init__(self, x: int, y: int):
        super().__init__(style=discord.ButtonStyle.secondary, label="\u200b", row=y)
        self.x = x
        self.y = y

    async def callback(self, interaction: discord.Interaction):
        await self.view.handle(interaction, self)


class TicTacToeView(discord.ui.View):
    def __init__(self, p1: discord.Member, p2: discord.Member):
        super().__init__(timeout=120)
        self.p1, self.p2 = p1, p2
        self.current = p1
        self.board = [[None] * 3 for _ in range(3)]
        self.message: Optional[discord.Message] = None
        for y in range(3):
            for x in range(3):
                self.add_item(TTTButton(x, y))

    def symbol(self, user: discord.abc.User) -> str:
        return "X" if user.id == self.p1.id else "O"

    def winner(self) -> Optional[str]:
        b = self.board
        lines = [*b, *[[b[r][c] for r in range(3)] for c in range(3)],
                 [b[i][i] for i in range(3)], [b[i][2 - i] for i in range(3)]]
        for line in lines:
            if line[0] and line[0] == line[1] == line[2]:
                return line[0]
        return None

    def end(self) -> None:
        for child in self.children:
            child.disabled = True
        self.stop()

    async def handle(self, interaction: discord.Interaction, button: TTTButton) -> None:
        if interaction.user.id not in (self.p1.id, self.p2.id):
            return await interaction.response.send_message("You're not in this game.", ephemeral=True)
        if interaction.user.id != self.current.id:
            return await interaction.response.send_message("It's not your turn!", ephemeral=True)

        mark = self.symbol(interaction.user)
        self.board[button.y][button.x] = mark
        button.label = mark
        button.style = discord.ButtonStyle.danger if mark == "X" else discord.ButtonStyle.success
        button.disabled = True

        if self.winner():
            self.end()
            content = f"🎉 {interaction.user.mention} wins!"
        elif all(cell for row in self.board for cell in row):
            self.end()
            content = "🤝 It's a draw!"
        else:
            self.current = self.p2 if self.current.id == self.p1.id else self.p1
            content = f"{self.current.mention}'s turn ({self.symbol(self.current)})"
        await interaction.response.edit_message(content=content, view=self)

    async def on_timeout(self) -> None:
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(content="⌛ Game timed out.", view=self)
            except discord.HTTPException:
                pass


# ====================== TRIVIA ======================
class TriviaButton(discord.ui.Button):
    def __init__(self, answer: str):
        super().__init__(label=answer[:80], style=discord.ButtonStyle.secondary)
        self.answer = answer

    async def callback(self, interaction: discord.Interaction):
        await self.view.pick(interaction, self)


class TriviaView(discord.ui.View):
    def __init__(self, guild_id: int, correct: str, answers: list, reward: int):
        super().__init__(timeout=20)
        self.guild_id = guild_id
        self.correct = correct
        self.reward = reward
        self.guessed = set()
        self.done = False
        self.message: Optional[discord.Message] = None
        for answer in answers:
            self.add_item(TriviaButton(answer))

    def reveal(self) -> None:
        for child in self.children:
            child.disabled = True
            if getattr(child, "answer", None) == self.correct:
                child.style = discord.ButtonStyle.success

    async def pick(self, interaction: discord.Interaction, button: TriviaButton) -> None:
        if interaction.user.id in self.guessed:
            return await interaction.response.send_message("You already guessed!", ephemeral=True)
        self.guessed.add(interaction.user.id)
        if button.answer != self.correct:
            return await interaction.response.send_message("❌ Nope, you're out for this round!", ephemeral=True)

        self.done = True
        add_coins(self.guild_id, interaction.user.id, self.reward)
        self.reveal()
        await interaction.response.edit_message(
            content=f"✅ {interaction.user.mention} got it! The answer was **{self.correct}** "
                    f"(+{self.reward:,} {COIN})",
            view=self)
        self.stop()

    async def on_timeout(self) -> None:
        if self.done:
            return
        self.reveal()
        if self.message:
            try:
                await self.message.edit(content=f"⌛ Time's up! The answer was **{self.correct}**.", view=self)
            except discord.HTTPException:
                pass


# ====================== SLASH COMMANDS ======================
def setup(bot: discord.Client, tree: app_commands.CommandTree) -> None:
    def slash(name: str, description: str):
        def deco(fn):
            fn = app_commands.guild_only()(fn)
            cmd = tree.command(name=name, description=description)(fn)
            _commands[name] = cmd  # lets the !v prefix handler reuse the same code
            return cmd
        return deco

    def item_choices(only: Optional[list] = None):
        return [app_commands.Choice(name=f"{v['emoji']} {v['name']}", value=k)
                for k, v in SHOP.items() if only is None or k in only]

    # ---------------- ECONOMY ----------------
    @slash("balance", "Check your coins (or someone else's)")
    @app_commands.describe(member="Whose balance to view (leave empty for yourself)")
    async def balance(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        row = get_user(interaction.guild.id, target.id)
        level, _ = level_from_xp(row["xp"])
        e = discord.Embed(title=f"{target.display_name}'s balance", color=discord.Color.gold())
        e.set_thumbnail(url=target.display_avatar.url)
        e.add_field(name="Wallet", value=f"{COIN} {row['coins']:,}")
        e.add_field(name="Bank", value=f"🏦 {row['bank']:,}")
        e.add_field(name="Net worth", value=f"💰 {row['coins'] + row['bank']:,}")
        e.set_footer(text=f"Level {level}")
        await interaction.response.send_message(embed=e)

    @slash("daily", "Claim your daily coins (streaks give bonuses!)")
    async def daily(interaction: discord.Interaction):
        gid, uid = interaction.guild.id, interaction.user.id
        row = get_user(gid, uid)
        now = time.time()
        elapsed = now - row["last_daily"]
        if elapsed < DAILY_COOLDOWN:
            return await reply_error(
                interaction, f"⏳ You already claimed today. Come back in **{fmt_duration(DAILY_COOLDOWN - elapsed)}**.")
        streak = row["daily_streak"] + 1 if elapsed < DAILY_COOLDOWN * 2 else 1
        reward = 200 + min(streak, 30) * 25
        add_coins(gid, uid, reward)
        set_field(gid, uid, last_daily=now, daily_streak=streak)
        await interaction.response.send_message(
            f"📅 You claimed **{reward:,}** {COIN}! Streak: **{streak}** day(s) 🔥")

    @slash("work", "Do a job for some coins (1 hour cooldown)")
    async def work(interaction: discord.Interaction):
        gid, uid = interaction.guild.id, interaction.user.id
        row = get_user(gid, uid)
        now = time.time()
        elapsed = now - row["last_work"]
        if elapsed < WORK_COOLDOWN:
            return await reply_error(
                interaction, f"⏳ You're tired. Work again in **{fmt_duration(WORK_COOLDOWN - elapsed)}**.")
        amount = random.randint(50, 250)
        add_coins(gid, uid, amount)
        set_field(gid, uid, last_work=now)
        await interaction.response.send_message(random.choice(JOBS).format(amount=f"{amount:,}") + f" {COIN}")

    @slash("pay", "Give some of your coins to another member")
    @app_commands.describe(member="Who gets the coins", amount="How many coins to send")
    async def pay(interaction: discord.Interaction, member: discord.Member, amount: app_commands.Range[int, 1]):
        if member.bot or member.id == interaction.user.id:
            return await reply_error(interaction, "❌ Pick another (non-bot) member.")
        gid = interaction.guild.id
        if not take_coins(gid, interaction.user.id, amount):
            return await reply_error(interaction, "❌ You don't have that many coins in your wallet.")
        add_coins(gid, member.id, amount)
        await interaction.response.send_message(f"💸 {interaction.user.mention} sent **{amount:,}** {COIN} to {member.mention}!")

    @slash("deposit", "Move coins into your bank (safe from stealing)")
    @app_commands.describe(amount="A number, 'half' or 'all'")
    async def deposit(interaction: discord.Interaction, amount: str):
        gid, uid = interaction.guild.id, interaction.user.id
        n = parse_amount(amount, get_user(gid, uid)["coins"])
        if n is None or not move_money(gid, uid, n, to_bank=True):
            return await reply_error(interaction, "❌ Invalid amount or not enough coins in your wallet.")
        await interaction.response.send_message(f"🏦 Deposited **{n:,}** {COIN}.")

    @slash("withdraw", "Take coins out of your bank")
    @app_commands.describe(amount="A number, 'half' or 'all'")
    async def withdraw(interaction: discord.Interaction, amount: str):
        gid, uid = interaction.guild.id, interaction.user.id
        n = parse_amount(amount, get_user(gid, uid)["bank"])
        if n is None or not move_money(gid, uid, n, to_bank=False):
            return await reply_error(interaction, "❌ Invalid amount or not enough coins in your bank.")
        await interaction.response.send_message(f"💵 Withdrew **{n:,}** {COIN}.")

    @slash("steal", "Try to steal coins from someone's wallet (risky!)")
    @app_commands.describe(target="The member you want to rob")
    async def steal(interaction: discord.Interaction, target: discord.Member):
        gid, thief = interaction.guild.id, interaction.user
        if target.bot or target.id == thief.id:
            return await reply_error(interaction, "❌ Pick another (non-bot) member.")

        thief_row = get_user(gid, thief.id)
        now = time.time()
        elapsed = now - thief_row["last_steal"]
        if elapsed < STEAL_COOLDOWN:
            return await reply_error(
                interaction, f"⏳ Lay low for **{fmt_duration(STEAL_COOLDOWN - elapsed)}** before your next heist.")
        if thief_row["coins"] < 50:
            return await reply_error(interaction, "❌ You need at least **50** coins in your wallet to cover the fine if you get caught.")
        victim_row = get_user(gid, target.id)
        if victim_row["coins"] < 100:
            return await reply_error(interaction, f"❌ {target.display_name} has less than 100 coins in their wallet. Not worth it.")

        set_field(gid, thief.id, last_steal=now)

        if inv_take(gid, target.id, "padlock"):
            return await interaction.response.send_message(
                f"🔒 {thief.mention} tried to rob {target.mention}, but their **padlock** snapped shut. The padlock is now broken.")

        chance = 0.65 if inv_take(gid, thief.id, "lockpick") else 0.40
        if random.random() < chance:
            victim_coins = get_user(gid, target.id)["coins"]
            amount = max(1, int(victim_coins * random.uniform(0.10, 0.30)))
            if take_coins(gid, target.id, amount):
                add_coins(gid, thief.id, amount)
                return await interaction.response.send_message(
                    f"🦹 **Success!** {thief.mention} stole **{amount:,}** {COIN} from {target.mention}!")
            return await interaction.response.send_message(f"{target.mention} spent their coins just in time. Heist failed!")

        fine = min(get_user(gid, thief.id)["coins"], random.randint(50, 200))
        take_coins(gid, thief.id, fine)
        add_coins(gid, target.id, fine)
        await interaction.response.send_message(
            f"🚔 **Caught!** {thief.mention} was fined **{fine:,}** {COIN}, paid to {target.mention}.")

    @slash("leaderboard", "See the richest or highest-level members")
    @app_commands.describe(kind="What to rank by")
    @app_commands.choices(kind=[app_commands.Choice(name="Net worth", value="coins"),
                                app_commands.Choice(name="Level / XP", value="xp")])
    async def leaderboard(interaction: discord.Interaction, kind: Optional[app_commands.Choice[str]] = None):
        mode = kind.value if kind else "coins"
        if mode == "xp":
            rows = db.execute("SELECT user_id, xp AS score FROM users WHERE guild_id=? AND xp>0 "
                              "ORDER BY xp DESC LIMIT 10", (interaction.guild.id,)).fetchall()
            title = "🏆 Level leaderboard"
        else:
            rows = db.execute("SELECT user_id, coins+bank AS score FROM users WHERE guild_id=? AND coins+bank>0 "
                              "ORDER BY score DESC LIMIT 10", (interaction.guild.id,)).fetchall()
            title = "💰 Richest members"
        if not rows:
            return await reply_error(interaction, "Nobody is on the leaderboard yet. Start chatting and use `/daily`!")
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, r in enumerate(rows):
            prefix = medals[i] if i < 3 else f"`{i + 1}.`"
            value = f"Level {level_from_xp(r['score'])[0]} ({r['score']:,} XP)" if mode == "xp" else f"{COIN} {r['score']:,}"
            lines.append(f"{prefix} <@{r['user_id']}> - {value}")
        await interaction.response.send_message(
            embed=discord.Embed(title=title, description="\n".join(lines), color=discord.Color.gold()))

    # ---------------- LEVELING ----------------
    @slash("rank", "Show your level and XP progress")
    @app_commands.describe(member="Whose rank to view (leave empty for yourself)")
    async def rank(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        row = get_user(interaction.guild.id, target.id)
        level, into = level_from_xp(row["xp"])
        need = xp_needed(level)
        position = db.execute("SELECT COUNT(*)+1 AS p FROM users WHERE guild_id=? AND xp>?",
                              (interaction.guild.id, row["xp"])).fetchone()["p"]
        e = discord.Embed(title=f"{target.display_name}'s rank", color=target.color if target.color.value else discord.Color.blurple())
        e.set_thumbnail(url=target.display_avatar.url)
        e.add_field(name="Level", value=str(level))
        e.add_field(name="Server rank", value=f"#{position}")
        e.add_field(name="Total XP", value=f"{row['xp']:,}")
        e.add_field(name="Progress", value=f"`{progress_bar(into, need)}` {into:,}/{need:,} XP", inline=False)
        if row["boost_until"] > time.time():
            e.set_footer(text=f"⚡ 2x XP boost active for {fmt_duration(row['boost_until'] - time.time())}")
        await interaction.response.send_message(embed=e)

    levelrole = app_commands.Group(
        name="levelrole", description="Manage roles given at certain levels",
        guild_only=True, default_permissions=discord.Permissions(manage_guild=True))

    @levelrole.command(name="add", description="Give a role to members who reach a level")
    @app_commands.describe(level="The level that unlocks the role", role="The role to give")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def levelrole_add(interaction: discord.Interaction, level: app_commands.Range[int, 1, 500], role: discord.Role):
        if role >= interaction.guild.me.top_role or role.is_default():
            return await reply_error(interaction, "❌ I can't hand out that role (it's higher than my top role).")
        db.execute("INSERT OR REPLACE INTO level_roles (guild_id, level, role_id) VALUES (?, ?, ?)",
                   (interaction.guild.id, level, role.id))
        db.commit()
        await interaction.response.send_message(f"✅ Members reaching **level {level}** will get {role.mention}.",
                                                allowed_mentions=discord.AllowedMentions.none())

    @levelrole.command(name="remove", description="Remove a level reward")
    @app_commands.describe(level="The level to clear")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def levelrole_remove(interaction: discord.Interaction, level: app_commands.Range[int, 1, 500]):
        cur = db.execute("DELETE FROM level_roles WHERE guild_id=? AND level=?", (interaction.guild.id, level))
        db.commit()
        msg = f"🗑️ Removed the reward for level {level}." if cur.rowcount else "❌ No reward set for that level."
        await interaction.response.send_message(msg, ephemeral=True)

    @levelrole.command(name="list", description="Show all level rewards")
    async def levelrole_list(interaction: discord.Interaction):
        rows = db.execute("SELECT level, role_id FROM level_roles WHERE guild_id=? ORDER BY level",
                          (interaction.guild.id,)).fetchall()
        if not rows:
            return await reply_error(interaction, "No level rewards set. Admins can add some with `/levelrole add`.")
        await interaction.response.send_message(
            "\n".join(f"Level **{r['level']}** -> <@&{r['role_id']}>" for r in rows),
            allowed_mentions=discord.AllowedMentions.none())

    tree.add_command(levelrole)
    _commands["levelrole add"] = levelrole_add
    _commands["levelrole remove"] = levelrole_remove
    _commands["levelrole list"] = levelrole_list

    @slash("addcoins", "Admin: add or remove coins from a member")
    @app_commands.describe(member="The member", amount="Positive to add, negative to remove")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def addcoins(interaction: discord.Interaction, member: discord.Member,
                       amount: app_commands.Range[int, -1000000, 1000000]):
        add_coins(interaction.guild.id, member.id, amount)
        await interaction.response.send_message(f"✅ Adjusted {member.display_name}'s wallet by **{amount:+,}** {COIN}.",
                                                ephemeral=True)

    # ---------------- SHOP ----------------
    @slash("shop", "Browse items you can buy with coins")
    async def shop(interaction: discord.Interaction):
        e = discord.Embed(title="🛒 Shop", description="Buy with `/buy`.", color=discord.Color.blurple())
        for key, item in SHOP.items():
            e.add_field(name=f"{item['emoji']} {item['name']} - {item['price']:,} {COIN}", value=item["desc"], inline=False)
        await interaction.response.send_message(embed=e)

    @slash("buy", "Buy an item from the shop")
    @app_commands.describe(item="What to buy", quantity="How many (default 1)")
    @app_commands.choices(item=item_choices())
    async def buy(interaction: discord.Interaction, item: app_commands.Choice[str],
                  quantity: app_commands.Range[int, 1, 20] = 1):
        info = SHOP[item.value]
        cost = info["price"] * quantity
        if not take_coins(interaction.guild.id, interaction.user.id, cost):
            return await reply_error(interaction, f"❌ You need **{cost:,}** {COIN} in your wallet for that.")
        inv_add(interaction.guild.id, interaction.user.id, item.value, quantity)
        await interaction.response.send_message(
            f"✅ Bought **{quantity}x {info['emoji']} {info['name']}** for **{cost:,}** {COIN}.")

    @slash("inventory", "See the items you own")
    @app_commands.describe(member="Whose inventory to view (leave empty for yourself)")
    async def inventory(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        rows = db.execute("SELECT item, qty FROM inventory WHERE guild_id=? AND user_id=? AND qty>0",
                          (interaction.guild.id, target.id)).fetchall()
        if not rows:
            return await interaction.response.send_message(f"{target.display_name} owns nothing yet. Try `/shop`!")
        lines = [f"{SHOP[r['item']]['emoji']} **{SHOP[r['item']]['name']}** x{r['qty']}" for r in rows if r["item"] in SHOP]
        await interaction.response.send_message(
            embed=discord.Embed(title=f"🎒 {target.display_name}'s inventory", description="\n".join(lines),
                                color=discord.Color.blurple()))

    @slash("use", "Use an item from your inventory")
    @app_commands.describe(item="The item to use")
    @app_commands.choices(item=item_choices(["xp_boost", "mystery_box"]))
    async def use(interaction: discord.Interaction, item: app_commands.Choice[str]):
        gid, uid = interaction.guild.id, interaction.user.id
        if not inv_take(gid, uid, item.value):
            return await reply_error(interaction, "❌ You don't own that item. Check `/shop`.")
        if item.value == "xp_boost":
            start = max(time.time(), get_user(gid, uid)["boost_until"])
            set_field(gid, uid, boost_until=start + 3600)
            return await interaction.response.send_message(
                "⚡ **XP Boost activated!** You earn double chat XP for the next hour (stacks if you use more).")
        prize = random.choices([100, 200, 300, 500, 1000, 2500], weights=[30, 25, 20, 13, 9, 3])[0]
        add_coins(gid, uid, prize)
        await interaction.response.send_message(f"🎁 You opened the Mystery Box and found **{prize:,}** {COIN}!")

    # ---------------- GAMBLING ----------------
    slot_symbols = ["🍒", "🍋", "🍇", "🔔", "💎", "7️⃣"]
    slot_payout = {"🍒": 3, "🍋": 4, "🍇": 5, "🔔": 8, "💎": 15, "7️⃣": 25}

    @slash("slots", "Spin the slot machine")
    @app_commands.describe(bet=f"Coins to bet (10-{MAX_BET:,})")
    async def slots(interaction: discord.Interaction, bet: app_commands.Range[int, 10, MAX_BET]):
        gid, uid = interaction.guild.id, interaction.user.id
        if not take_coins(gid, uid, bet):
            return await reply_error(interaction, "❌ You don't have enough coins in your wallet.")

        await interaction.response.send_message("🎰 **Spinning...**\n`[ 🎰 | 🎰 | 🎰 ]`")
        await asyncio.sleep(1.2)

        reels = [random.choice(slot_symbols) for _ in range(3)]
        display = f"`[ {' | '.join(reels)} ]`"
        if len(set(reels)) == 1:
            payout = bet * slot_payout[reels[0]]
            result = f"🎉 **JACKPOT!** x{slot_payout[reels[0]]}"
        elif len(set(reels)) == 2:
            payout = int(bet * 1.5)
            result = "✨ Two of a kind! x1.5"
        else:
            payout = 0
            result = "💀 No match."
        if payout:
            add_coins(gid, uid, payout)
        await interaction.edit_original_response(
            content=f"🎰 **Slots**\n{display}\n{result} ({payout - bet:+,} {COIN})")

    @slash("betflip", "Bet coins on a coin flip (50/50)")
    @app_commands.describe(bet=f"Coins to bet (10-{MAX_BET:,})", side="Heads or tails?")
    @app_commands.choices(side=[app_commands.Choice(name="Heads", value="heads"),
                                app_commands.Choice(name="Tails", value="tails")])
    async def betflip(interaction: discord.Interaction, bet: app_commands.Range[int, 10, MAX_BET],
                      side: app_commands.Choice[str]):
        gid, uid = interaction.guild.id, interaction.user.id
        if not take_coins(gid, uid, bet):
            return await reply_error(interaction, "❌ You don't have enough coins in your wallet.")
        result = random.choice(["heads", "tails"])
        if result == side.value:
            add_coins(gid, uid, bet * 2)
            await interaction.response.send_message(f"🪙 It landed on **{result}**! You won **{bet:,}** {COIN}!")
        else:
            await interaction.response.send_message(f"🪙 It landed on **{result}**. You lost **{bet:,}** {COIN}.")

    @slash("blackjack", "Play blackjack against the dealer")
    @app_commands.describe(bet=f"Coins to bet (10-{MAX_BET:,})")
    async def blackjack(interaction: discord.Interaction, bet: app_commands.Range[int, 10, MAX_BET]):
        gid = interaction.guild.id
        if not take_coins(gid, interaction.user.id, bet):
            return await reply_error(interaction, "❌ You don't have enough coins in your wallet.")
        view = BlackjackView(interaction.user, gid, bet)
        if hand_value(view.player) == 21:
            outcome = "push" if hand_value(view.dealer) == 21 else "blackjack"
            return await interaction.response.send_message(embed=view.finish(outcome))
        await interaction.response.send_message(embed=view.embed(), view=view)
        view.message = await interaction.original_response()

    # ---------------- MINI-GAMES ----------------
    @slash("rps", "Play rock-paper-scissors against the bot")
    @app_commands.describe(bet="Optional coins to bet (win = double, tie = refund)")
    async def rps(interaction: discord.Interaction, bet: app_commands.Range[int, 0, MAX_BET] = 0):
        gid = interaction.guild.id
        if bet and not take_coins(gid, interaction.user.id, bet):
            return await reply_error(interaction, "❌ You don't have enough coins in your wallet.")
        view = RPSView(interaction.user, gid, bet)
        suffix = f" (bet: {bet:,} {COIN})" if bet else ""
        await interaction.response.send_message(f"✊ Pick your move!{suffix}", view=view)
        view.message = await interaction.original_response()

    @slash("tictactoe", "Challenge a member to tic-tac-toe")
    @app_commands.describe(opponent="Who you want to play against")
    async def tictactoe(interaction: discord.Interaction, opponent: discord.Member):
        if opponent.bot or opponent.id == interaction.user.id:
            return await reply_error(interaction, "❌ Pick another (non-bot) member.")
        view = TicTacToeView(interaction.user, opponent)
        await interaction.response.send_message(
            f"❌ {interaction.user.mention} vs ⭕ {opponent.mention}\n{interaction.user.mention} goes first (X)!",
            view=view)
        view.message = await interaction.original_response()

    @slash("trivia", "Answer a trivia question - first correct answer wins coins")
    async def trivia(interaction: discord.Interaction):
        await interaction.response.defer()
        data = await fetch_json("https://opentdb.com/api.php", amount=1, type="multiple", encode="url3986")
        question = None
        if data and data.get("results"):
            r = data["results"][0]
            question = {
                "q": unquote(r["question"]), "a": unquote(r["correct_answer"]),
                "w": [unquote(x) for x in r["incorrect_answers"]],
                "d": r["difficulty"], "c": unquote(r["category"]),
            }
        if question is None:
            question = random.choice(FALLBACK_TRIVIA)

        reward = {"easy": 50, "medium": 100, "hard": 150}.get(question["d"], 75)
        answers = [question["a"], *question["w"]]
        random.shuffle(answers)
        e = discord.Embed(title="🧠 Trivia", description=question["q"], color=discord.Color.random())
        e.add_field(name="Category", value=question["c"])
        e.add_field(name="Difficulty", value=question["d"].title())
        e.set_footer(text=f"First correct answer wins {reward} coins - 20 seconds!")
        view = TriviaView(interaction.guild.id, question["a"], answers, reward)
        view.message = await interaction.followup.send(embed=e, view=view, wait=True)

    # ---------------- RANDOM CONTENT ----------------
    @slash("cat", "Get a random cat picture")
    async def cat(interaction: discord.Interaction):
        await interaction.response.defer()
        data = await fetch_json("https://api.thecatapi.com/v1/images/search")
        if not data:
            return await interaction.followup.send("😿 The cat service is napping. Try again in a moment.")
        e = discord.Embed(title="🐱 Meow!", color=discord.Color.orange())
        e.set_image(url=data[0]["url"])
        await interaction.followup.send(embed=e)

    @slash("dog", "Get a random dog picture")
    async def dog(interaction: discord.Interaction):
        await interaction.response.defer()
        data = await fetch_json("https://dog.ceo/api/breeds/image/random")
        if not data or "message" not in data:
            return await interaction.followup.send("🐶 The dog service is out for a walk. Try again in a moment.")
        e = discord.Embed(title="🐶 Woof!", color=discord.Color.orange())
        e.set_image(url=data["message"])
        await interaction.followup.send(embed=e)

    @slash("meme", "Get a random meme from Reddit")
    async def meme(interaction: discord.Interaction):
        await interaction.response.defer()
        for _ in range(3):
            data = await fetch_json("https://meme-api.com/gimme")
            if data and data.get("url") and not data.get("nsfw") and not data.get("spoiler"):
                e = discord.Embed(title=data.get("title", "Meme")[:250], url=data.get("postLink"),
                                  color=discord.Color.random())
                e.set_image(url=data["url"])
                e.set_footer(text=f"r/{data.get('subreddit', 'memes')}")
                return await interaction.followup.send(embed=e)
        await interaction.followup.send("😵 Couldn't fetch a meme right now. Try again in a moment.")

    @slash("joke", "Get a random joke")
    async def joke(interaction: discord.Interaction):
        await interaction.response.defer()
        data = await fetch_json("https://official-joke-api.appspot.com/random_joke")
        if not data or "setup" not in data:
            return await interaction.followup.send("🤡 I forgot the joke. Try again in a moment.")
        await interaction.followup.send(f"**{data['setup']}**\n||{data['punchline']}||")

    @slash("fact", "Get a random useless fact")
    async def fact(interaction: discord.Interaction):
        await interaction.response.defer()
        data = await fetch_json("https://uselessfacts.jsph.pl/api/v2/facts/random", language="en")
        if not data or "text" not in data:
            return await interaction.followup.send("📚 My fact book is closed right now. Try again in a moment.")
        await interaction.followup.send(f"📚 **Did you know?**\n{data['text']}")

    @slash("ship", "Check how compatible two members are")
    @app_commands.describe(first="The first member", second="The second member (leave empty for yourself)")
    async def ship(interaction: discord.Interaction, first: discord.Member, second: Optional[discord.Member] = None):
        other = second or interaction.user
        a, b = sorted((first.id, other.id))
        pct = int(hashlib.md5(f"{a}-{b}".encode()).hexdigest()[:6], 16) % 101
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
        e = discord.Embed(
            title=f"💞 {n1} x {n2}",
            description=f"**Ship name:** {ship_name}\n`{progress_bar(pct, 100, 20)}` **{pct}%**\n{verdict}",
            color=discord.Color.magenta())
        await interaction.response.send_message(embed=e)

    @slash("choose", "Let the bot pick between options")
    @app_commands.describe(options="Separate options with commas, e.g. pizza, sushi, tacos")
    async def choose(interaction: discord.Interaction, options: str):
        parts = [p.strip() for p in options.replace(" or ", ",").split(",") if p.strip()]
        if len(parts) < 2:
            return await reply_error(interaction, "❌ Give me at least two options separated by commas.")
        await interaction.response.send_message(
            f"🤔 I choose... **{random.choice(parts)}**!", allowed_mentions=discord.AllowedMentions.none())
