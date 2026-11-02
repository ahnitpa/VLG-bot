# VLG Bot

A lightweight Discord bot for server management, entertainment, moderation, and music playback.

This project is a personal hobby project written in Python. It is designed to run as a single-service Discord bot with a small set of core features, simple configuration, and minimal deployment overhead.

## Overview

VLG Bot provides:

- Discord moderation tools
- basic server utility commands
- AFK tracking and inactivity handling
- music playback support
- fun and social commands
- simple SQLite-backed user statistics

The bot supports both slash commands and a prefix-based command system using `!v`.

## Features

### Moderation and server management

- kick members
- ban members
- timeout members
- role assignment and removal
- create categories and channels
- move channels up or down

### Utility and social features

- custom status updates
- ping and latency checks
- AFK status management
- user profile and avatar commands
- random fun commands and mini-game interactions

### Music

- music playback via Discord voice channels
- FFmpeg integration for audio processing
- YouTube media playback through `yt-dlp`

### Persistence

- SQLite database for user data and inventory-like records
- optional environment-based configuration

## Project structure

```text
.
├── bot.py               # Main bot entry point and command registration
├── afk.py               # AFK tracking logic
├── fun.py               # Fun and utility commands
├── music.py             # Music commands and playback logic
├── shared.py             # Shared helpers and common bot logic
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker image definition
├── scripts/
│   └── init_db.py      # Initializes the SQLite database
├── bot.db              # Generated SQLite database at runtime
├── README.md           # Project documentation
└── .env.example        # Optional local config file if added later
```

## Requirements

- Python 3.11+
- FFmpeg installed and available on PATH
- A Discord bot token

## Installation

Clone the repository:

```bash
git clone https://github.com/ahnitpa/VLG-bot.git
cd VLG-bot
```

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Initialize the database:

```bash
python scripts/init_db.py
```

## Configuration

Set the required environment variable before starting the bot:

```bash
export TOKEN="your_discord_bot_token"
```

Optional environment variables:

```bash
export PORT=8080
export DB_PATH="/absolute/path/to/bot.db"
```

## Running the bot

```bash
python bot.py
```

The bot starts by launching the Discord client and a small Flask keep-alive endpoint for hosted environments.

## Docker

Build the image:

```bash
docker build -t vlg-bot .
```

Run the container:

```bash
docker run --rm -e TOKEN="your_discord_bot_token" -p 8080:8080 vlg-bot
```

## Command usage

The bot supports both slash commands and the `!v` prefix.

Examples:

```text
!v help
!v ping
!v afk
!v afklist
!v rate something
!v 8ball question
```

Slash command examples:

```text
/setstatus
/coinflip
/slap
/roast
/createchannel
/createvoice
/movechannel
```

## Database

The project uses SQLite for user data and basic economy-style tracking. The database is created automatically by `scripts/init_db.py` unless a custom path is provided through `DB_PATH` or `BOT_DB_PATH`.

## Notes

- This is a hobby project and not a large-scale production bot framework.
- The codebase is intentionally compact and easy to extend.
- Some files may be legacy or duplicate remnants from earlier development iterations.

## License

This project does not currently include a dedicated license file. If you intend to reuse or redistribute the code, verify the repository owner’s licensing terms before doing so.
