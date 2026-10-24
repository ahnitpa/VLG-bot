"""fun_games.py - button-based games: blackjack, rock-paper-scissors, tic-tac-toe, trivia."""
import random
from typing import Optional

import discord

from fun_core import COIN, add_coins

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


