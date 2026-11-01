# VLG Bot

A hobby Discord bot built in Python for fun, server utilities, moderation helpers, music playback, and small game/economy features.

This repository is a personal project and is intentionally lightweight and easy to extend.

## Features

- Discord bot with both slash commands and `!v` prefix commands
- Server moderation tools:
  - kick
  - ban
  - timeout
  - role assignment/removal
  - channel/category creation and movement
- AFK system and inactivity tracking
- Music playback support with FFmpeg and `yt-dlp`
- Fun commands, coin/game interactions, XP, and user profile utilities
- SQLite-backed user data for economy-style stats
- Basic keep-alive Flask server for hosting environments

## Tech Stack

- Python 3.11+
- discord.py
- Flask
- yt-dlp
- FFmpeg
- SQLite

## Repository Structure

```text
.
├── bot.py                # Main bot entry point and command registration
├── afk.py                # AFK tracking and related logic
├── fun.py                # Fun, economy, game, and utility commands
├── music.py              # Music-related commands and playback logic
├── shared.py              # Shared helpers and bot utilities
├── shared (1).py         # Duplicate/shared helper variant present in repo
├── fun_core (1).py       # Additional fun logic
├── fun_games (1).py      # Game-specific logic
├── main (1).py           # Alternate main entry file present in repo
├── requirements.txt      # Python dependencies
├── Dockerfile            # Container build config
├── scripts/
│   └── init_db.py       # SQLite schema setup
└── README.md             # Project documentation
```

Note: the repository contains a few duplicate or alternate Python files, likely from experimentation or local revisions. `bot.py` is the main runtime file.

## Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/ahnitpa/VLG-bot.git
cd VLG-bot
```

### 2. Create a virtual environment

```bash
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# or
.venv\Scripts\activate      # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Initialize the database

```bash
python scripts/init_db.py
```

This creates a local SQLite database at `bot.db` unless you override it with `DB_PATH` or `BOT_DB_PATH`.

### 5. Set your bot token

```bash
export TOKEN="your_discord_bot_token"
```

Optional environment variables:

```bash
export PORT=8080
export DB_PATH="/absolute/path/to/bot.db"
```

### 6. Run the bot

```bash
python bot.py
```

## Docker

Build and run with Docker:

```bash
docker build -t vlg-bot .
docker run --rm -e TOKEN="your_discord_bot_token" -p 8080:8080 vlg-bot
```

The container installs FFmpeg automatically because the music features depend on it.

## Bot Behavior

The bot is built around a Discord server workflow:

- Slash commands are registered through `discord.py` command trees
- Prefix-based commands are handled via `!v <command>`
- The bot exposes a small "keep alive" web endpoint for hosted environments
- Music commands and playback state are managed in `music.py`
- Fun/game/economy commands are handled in `fun.py`

## Example Commands

Common prefix commands include:

```text
!v help
!v ping
!v afk
!v afklist
!v rate <thing>
!v 8ball <question>
!v slap @user
!v roast @user
```

Slash commands are also exposed for moderation and utility actions, including:

- `/setstatus`
- `/coinflip`
- `/slap`
- `/roast`
- `/createchannel`
- `/createvoice`
- `/movechannel`

## Notes

- This is a hobby project and not a production-grade bot framework.
- The repository contains duplicate or legacy files from development experimentation.
- Some modules may rely on server-specific IDs or custom setup steps.

## License

This project does not currently appear to include an explicit license file. If you plan to reuse or distribute it, check with the repository owner before doing so.

## Contributing

This project is mainly for personal experimentation, but feel free to fork it and adapt it for your own server or bot idea.

```bash
git checkout -b my-feature
git commit -am "Add my feature"
git push origin my-feature
```

## Support

For support or questions, open an issue in the repository or contact the project owner directly.
