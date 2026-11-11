<img width="234" height="234" alt="202177c614e66ac34ca3324477f4afcd" src="https://github.com/user-attachments/assets/04928022-0d2c-4d49-882b-1173a4013042" />

# VLG Bot

A lightweight Discord bot for server management, entertainment, moderation, music playback, and Gemini AI replies.

This personal hobby project is written in Python and is designed to run as a single-service Discord bot with a small set of core features, simple configuration, and minimal deployment overhead.

## Overview

VLG Bot provides:

- Discord moderation tools
- Basic server utility commands
- AFK tracking and inactivity handling
- Music playback support
- Fun and social commands
- SQLite-backed user statistics
- Gemini AI replies with optional per-server conversation memory

The bot supports both slash commands and a prefix-based command system using `!v`.

## Features

### Moderation and server management

- Kick and ban members
- Timeout members
- Assign and remove roles
- Create categories and channels
- Move channels up or down

### Utility and social features

- Custom status updates
- Ping and latency checks
- AFK status management
- User profile and avatar commands
- Random fun commands and mini-game interactions

### Music

- Music playback via Discord voice channels
- FFmpeg integration for audio processing
- YouTube media playback through `yt-dlp`

### Persistence

- SQLite database for user data and inventory-like records
- Environment-based configuration

## Gemini AI replies and server memory

The bot replies when a member mentions it or directly replies to one of its messages. It keeps a **small, server-wide conversation context** so it can follow up on recent AI conversations and associate replies with their recent context.

Memory scope and safeguards:

- Context is isolated by Discord server and shared across that server's channels; it is never shared with another server.
- Only messages that explicitly mention/reply to the bot are retained. The bot does not ingest ordinary server chat or fetch profile details.
- The database keeps at most the latest 20 AI exchanges per server, for up to 30 days.
- Conversation text is sent to Gemini for inference to answer the request. This is contextual recall, not model training or fine-tuning.
- Members can run `/ai-memory-forget` to delete their saved AI exchanges in that server.
- A member with Manage Server can run `/ai-memory-clear` to clear the server's saved AI exchanges.

Because memory is shared within a server, let members know before enabling it. For persistence across host restarts, configure `DB_PATH` to a persistent disk/location supported by your host; a temporary filesystem may not retain the database after restarts.

## Project structure

```text
.
├── bot.py               # Main bot entry point and command registration
├── afk.py               # AFK tracking logic
├── fun.py               # Fun and utility commands
├── music.py             # Music commands and playback logic
├── shared.py            # Shared helpers and common bot logic
├── requirements.txt     # Python dependencies
├── Dockerfile           # Docker image definition
├── scripts/
│   └── init_db.py       # Initializes the SQLite database
├── bot.db               # Generated SQLite database at runtime
└── README.md            # Project documentation
```

## Requirements

- Python 3.11+
- FFmpeg installed and available on `PATH`
- A Discord bot token
- A Gemini API key for AI replies

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

Initialize the database if needed:

```bash
python scripts/init_db.py
```

## Configuration

Set these environment variables in the deployment service:

- `TOKEN`: Discord bot token
- `GEMINI_API_KEY`: Gemini API key (keep it secret; never commit it)
- `GEMINI_MODEL`: Optional model ID (defaults to `gemini-3.1-flash-lite`)
- `DB_PATH`: Optional SQLite file path; use persistent storage if memory should survive restarts
- `PORT`: Optional port for the keep-alive web endpoint

In the Discord Developer Portal, enable **Message Content Intent**. The bot also needs permission to view and send messages in the relevant channels.

## Running the bot

```bash
python bot.py
```

The bot starts the Discord client and a small Flask keep-alive endpoint for hosted environments.

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

The project uses SQLite for user data and basic economy-style tracking. The database is initialized by `scripts/init_db.py`; `DB_PATH` can be used to select a different database location. AI conversation memory is stored in this database when enabled.

## Notes

- This is a hobby project and not a large-scale production bot framework.
- The codebase is intentionally compact and easy to extend.
- Some files may be legacy or duplicate remnants from earlier development iterations.

## License

This project does not currently include a dedicated license file. That means you will need to ask me for license or a fair agreement.