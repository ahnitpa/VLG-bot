"""
fun.py - Fun & engagement module (economy, leveling, shop, gambling, mini-games, content).

Files: fun.py (commands), fun_core.py (database, helpers, chat XP), fun_games.py (button games).

Hook it into your main file with:
    import fun
    fun.setup(bot, tree)                                   # registers slash commands
    await fun.on_message(message)                          # chat XP (inside your on_message)
    await fun.handle_prefix(message, command, args, ...)   # `!v` prefix commands

Data is stored in SQLite (default file: bot.db, override with the DB_PATH env var).
"""
import asyncio
import hashlib
import random
import time
from typing import Optional
from urllib.parse import unquote

import discord
from discord import app_commands

from fun_core import *  # noqa: F401,F403  (config, database helpers, chat XP)
from fun_core import _commands
from fun_games import BlackjackView, RPSView, TicTacToeView, TriviaView, hand_value

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


# ====================== PREFIX (!v) SUPPORT ======================
# Every slash command above is also available as `!v <command> ...`. The prefix handler
# builds a small stand-in for the Interaction object and calls the very same command code,
# so both versions always behave identically. Buttons (blackjack, trivia, ...) work as usual.
PREFIX_HELP = (
    "**🎮 Economy & fun (`!v`)**\n"
    "**Economy:** `balance [@m]`, `daily`, `work`, `pay @m <amt>`, `deposit <amt|all>`, "
    "`withdraw <amt|all>`, `steal @m`, `leaderboard [coins|xp]`\n"
    "**Levels:** `rank [@m]`, `levelrole add <level> @role`, `levelrole remove <level>`, `levelrole list`\n"
    "**Shop:** `shop`, `buy <item> [qty]`, `inventory [@m]`, `use <item>`\n"
    "**Games:** `slots <bet>`, `betflip <bet> <heads|tails>`, `blackjack <bet>`, `rps [bet]`, "
    "`tictactoe @m`, `trivia`\n"
    "**Random:** `cat`, `dog`, `meme`, `joke`, `fact`, `ship @a [@b]`, `choose a, b, c`\n"
    "**Admin:** `addcoins @m <amount>`\n"
    "Bets accept `all`. Aliases: `bal`, `lb`, `inv`, `bj`, `ttt`."
)

_ALIASES = {"bal": "balance", "lb": "leaderboard", "top": "leaderboard", "inv": "inventory",
            "bj": "blackjack", "ttt": "tictactoe", "bf": "betflip", "dep": "deposit",
            "with": "withdraw", "lvl": "rank", "level": "rank"}


class _PrefixResponse:
    """Mimics interaction.response for messages sent with the prefix."""

    def __init__(self, ctx: "PrefixContext"):
        self.ctx = ctx
        self._done = False

    def is_done(self) -> bool:
        return self._done

    async def defer(self, **_) -> None:
        self._done = True

    async def send_message(self, content=None, *, embed=None, view=None, ephemeral=False,
                           allowed_mentions=None, **_) -> None:
        kwargs = {k: v for k, v in (("content", content), ("embed", embed), ("view", view),
                                    ("allowed_mentions", allowed_mentions)) if v is not None}
        if ephemeral:  # prefix messages can't be private, so reply quietly instead
            try:
                sent = await self.ctx.message.reply(mention_author=False, **kwargs)
            except discord.HTTPException:
                sent = await self.ctx.channel.send(**kwargs)
        else:
            sent = await self.ctx.channel.send(**kwargs)
        self.ctx.sent = sent
        self._done = True


class _PrefixFollowup:
    def __init__(self, ctx: "PrefixContext"):
        self.ctx = ctx

    async def send(self, content=None, *, embed=None, view=None, wait=False, ephemeral=False,
                   allowed_mentions=None, **_):
        kwargs = {k: v for k, v in (("content", content), ("embed", embed), ("view", view),
                                    ("allowed_mentions", allowed_mentions)) if v is not None}
        sent = await self.ctx.channel.send(**kwargs)
        self.ctx.sent = sent
        return sent


class PrefixContext:
    """Stand-in for discord.Interaction, built from a normal message."""

    def __init__(self, message: discord.Message):
        self.message = message
        self.guild = message.guild
        self.channel = message.channel
        self.user = message.author
        self.sent: Optional[discord.Message] = None
        self.response = _PrefixResponse(self)
        self.followup = _PrefixFollowup(self)

    async def original_response(self) -> Optional[discord.Message]:
        return self.sent

    async def edit_original_response(self, **kwargs) -> None:
        if self.sent:
            await self.sent.edit(**kwargs)


class _BadArgs(Exception):
    """Raised by parsers; an empty message means 'show the usage line'."""


def _need(args: list, count: int) -> None:
    if len(args) < count:
        raise _BadArgs()


def _id_from(token: str, chars: str) -> Optional[int]:
    digits = token.strip(chars)
    return int(digits) if digits.isdigit() else None


def _member_arg(message: discord.Message, token: str) -> discord.Member:
    member_id = _id_from(token, "<@!>")
    member = message.guild.get_member(member_id) if member_id else None
    if member is None:
        raise _BadArgs("❌ I couldn't find that member. Mention them or use their ID.")
    return member


def _opt_member(message: discord.Message, args: list, index: int = 0) -> Optional[discord.Member]:
    return _member_arg(message, args[index]) if len(args) > index else None


def _int_arg(token: str, lo: int, hi: int, what: str = "amount") -> int:
    try:
        n = int(token.replace(",", ""))
    except ValueError:
        raise _BadArgs(f"❌ `{token}` isn't a valid {what}.")
    if not lo <= n <= hi:
        raise _BadArgs(f"❌ The {what} must be between {lo:,} and {hi:,}.")
    return n


def _wallet(message: discord.Message) -> int:
    return get_user(message.guild.id, message.author.id)["coins"]


def _amount_arg(message: discord.Message, token: str) -> int:
    if token.lower() in ("all", "max"):
        if _wallet(message) < 1:
            raise _BadArgs("❌ Your wallet is empty.")
        return _wallet(message)
    return _int_arg(token, 1, 10 ** 12)


def _bet_arg(message: discord.Message, token: str, lo: int = 10) -> int:
    if token.lower() in ("all", "max"):
        n = min(_wallet(message), MAX_BET)
        if n < lo:
            raise _BadArgs("❌ You don't have enough coins in your wallet.")
        return n
    return _int_arg(token, lo, MAX_BET, "bet")


def _item_arg(tokens: list, only: Optional[list] = None) -> app_commands.Choice:
    key = "_".join(tokens).lower()
    if key not in SHOP or (only and key not in only):
        raise _BadArgs("❌ Unknown item. Options: " + ", ".join(only or list(SHOP)))
    return app_commands.Choice(name=SHOP[key]["name"], value=key)


def _p_leaderboard(m, a):
    if a and a[0].lower() in ("xp", "level", "levels", "lvl"):
        return {"kind": app_commands.Choice(name="Level / XP", value="xp")}
    return {"kind": None}


def _p_buy(m, a):
    _need(a, 1)
    tokens = list(a)
    quantity = 1
    if len(tokens) > 1 and tokens[-1].isdigit():
        quantity = _int_arg(tokens.pop(), 1, 20, "quantity")
    return {"item": _item_arg(tokens), "quantity": quantity}


def _p_betflip(m, a):
    _need(a, 2)
    side = a[1].lower()
    if side in ("h", "heads"):
        choice = app_commands.Choice(name="Heads", value="heads")
    elif side in ("t", "tails"):
        choice = app_commands.Choice(name="Tails", value="tails")
    else:
        raise _BadArgs()
    return {"bet": _bet_arg(m, a[0]), "side": choice}


def _p_levelrole_add(m, a):
    _need(a, 2)
    role_id = _id_from(a[1], "<@&>")
    role = m.guild.get_role(role_id) if role_id else None
    if role is None:
        raise _BadArgs("❌ I couldn't find that role. Mention it or use its ID.")
    return {"level": _int_arg(a[0], 1, 500, "level"), "role": role}


def _p_pay(m, a):
    _need(a, 2)
    return {"member": _member_arg(m, a[0]), "amount": _amount_arg(m, a[1])}


def _p_ship(m, a):
    _need(a, 1)
    return {"first": _member_arg(m, a[0]), "second": _opt_member(m, a, 1)}


def _p_addcoins(m, a):
    _need(a, 2)
    return {"member": _member_arg(m, a[0]), "amount": _int_arg(a[1], -1_000_000, 1_000_000)}


def _p_choose(m, a):
    _need(a, 1)
    return {"options": " ".join(a)}


def _p_use(m, a):
    _need(a, 1)
    return {"item": _item_arg(a, ["xp_boost", "mystery_box"])}


def _p_deposit(m, a):
    _need(a, 1)
    return {"amount": a[0]}


# command -> (usage, argument parser, admin only)
_PREFIX = {
    "balance": ("balance [@member]", lambda m, a: {"member": _opt_member(m, a)}, False),
    "rank": ("rank [@member]", lambda m, a: {"member": _opt_member(m, a)}, False),
    "inventory": ("inventory [@member]", lambda m, a: {"member": _opt_member(m, a)}, False),
    "daily": ("daily", lambda m, a: {}, False),
    "work": ("work", lambda m, a: {}, False),
    "shop": ("shop", lambda m, a: {}, False),
    "pay": ("pay @member <amount|all>", _p_pay, False),
    "deposit": ("deposit <amount|half|all>", _p_deposit, False),
    "withdraw": ("withdraw <amount|half|all>", _p_deposit, False),
    "steal": ("steal @member", lambda m, a: (_need(a, 1), {"target": _member_arg(m, a[0])})[1], False),
    "leaderboard": ("leaderboard [coins|xp]", _p_leaderboard, False),
    "buy": ("buy <item> [quantity]", _p_buy, False),
    "use": ("use <xp_boost|mystery_box>", _p_use, False),
    "slots": ("slots <bet|all>", lambda m, a: (_need(a, 1), {"bet": _bet_arg(m, a[0])})[1], False),
    "betflip": ("betflip <bet|all> <heads|tails>", _p_betflip, False),
    "blackjack": ("blackjack <bet|all>", lambda m, a: (_need(a, 1), {"bet": _bet_arg(m, a[0])})[1], False),
    "rps": ("rps [bet]", lambda m, a: {"bet": _bet_arg(m, a[0], 0) if a else 0}, False),
    "tictactoe": ("tictactoe @opponent",
                  lambda m, a: (_need(a, 1), {"opponent": _member_arg(m, a[0])})[1], False),
    "trivia": ("trivia", lambda m, a: {}, False),
    "cat": ("cat", lambda m, a: {}, False),
    "dog": ("dog", lambda m, a: {}, False),
    "meme": ("meme", lambda m, a: {}, False),
    "joke": ("joke", lambda m, a: {}, False),
    "fact": ("fact", lambda m, a: {}, False),
    "ship": ("ship @member [@member]", _p_ship, False),
    "choose": ("choose <option, option, ...>", _p_choose, False),
    "addcoins": ("addcoins @member <amount>", _p_addcoins, True),
    "levelrole add": ("levelrole add <level> @role", _p_levelrole_add, True),
    "levelrole remove": ("levelrole remove <level>",
                         lambda m, a: (_need(a, 1), {"level": _int_arg(a[0], 1, 500, "level")})[1], True),
    "levelrole list": ("levelrole list", lambda m, a: {}, False),
}


async def handle_prefix(message: discord.Message, command: str, args: list, privileged: bool = False) -> bool:
    """Call from your `!v` handler. Returns True if the command belonged to this module.

    `privileged` should be True for devs / the owner / admins so they can use admin commands.
    """
    if message.guild is None or not _commands:
        return False

    args = list(args)
    command = command.lower()
    command = _ALIASES.get(command, command)
    if command == "levelrole":
        command = f"levelrole {args.pop(0).lower() if args else 'list'}"

    entry = _PREFIX.get(command)
    if entry is None or command not in _commands:
        return False
    usage, parser, admin_only = entry

    send = message.channel.send
    if admin_only and not (privileged or message.author.guild_permissions.manage_guild):
        await send("❌ **Access Denied:** You need the `Manage Server` permission.")
        return True

    try:
        kwargs = parser(message, args)
    except _BadArgs as e:
        await send(str(e) or f"❌ **Usage:** `!v {usage}`")
        return True

    await _commands[command].callback(PrefixContext(message), **kwargs)
    return True
