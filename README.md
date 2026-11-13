# VLG Bot

<img width="234" height="234" alt="VLG Bot logo" src="https://github.com/user-attachments/assets/04928022-0d2c-4d49-882b-1173a4013042" />

A lightweight Discord bot for server management, entertainment, moderation, music playback, and Gemini-powered replies.

This is a personal hobby project written in Python. It is designed to run as a single-service Discord bot with a small set of core features, simple configuration, and minimal deployment overhead.

## Overview

VLG Bot includes:

- Discord moderation tools
- Basic server utility commands
- AFK tracking and inactivity handling
- Music playback support
- Fun and social commands
- SQLite-backed user statistics and economy-like data
- Gemini AI replies with optional per-server memory

The bot supports both slash commands and a prefix command system using `!v`.

## Features

### Moderation and server management

- Kick and ban members
- Timeout members
- Assign and remove roles
- Create categories and channels
- Move channels up or down
- Custom status control

### Utility and social features

- Ping and latency checks
- AFK status management
- User profile and avatar commands
- Random fun commands and mini-game interactions
- Server setup and bot administration commands

### Music

- Play music in Discord voice channels
- FFmpeg integration for audio processing
- YouTube playback via `yt-dlp`

### Persistence

- SQLite database for user data and inventory-like records
- Environment-based configuration
- Optional keep-alive web endpoint for hosted environments

## Gemini AI replies and server memory

The bot can reply when a member mentions it or directly replies to one of its messages. It keeps a small, server-wide conversation context so it can follow up on recent AI conversations within that server.

### Memory behavior

- Context is isolated by Discord server and shared across that server's channels; it is never shared with another server.
- Only messages that explicitly mention or reply to the bot are retained.
- The bot does not ingest ordinary server chat or fetch profile details.
- The database stores at most the latest 20 AI exchanges per server, retained for up to 30 days.
- Conversation text is sent to Gemini for inference to answer the request. This is contextual recall, not model training or fine-tuning.
- Members can run `/ai-memory-forget` to delete their saved AI exchanges in that server.
- A member with Manage Server can run `/ai-memory-clear` to clear the server's saved AI exchanges.

Because memory is shared within a server, let members know before enabling it. For persistence across host restarts, configure `DB_PATH` to a persistent disk location supported by your host.

## Project structure

```text
.
├── .env.example          # Example environment configuration
├── .gitignore           # Git ignore rules
├── Dockerfile            # Docker image definition
├── README.md             # Project documentation
├── afk.py                # AFK tracking logic
├── ai_responses.py       # Gemini reply handling
├── bot.py                # Main bot entry point and command registration
├── fun.py                # Fun and utility commands
├── music.py              # Music commands and playback logic
├── requirements.txt      # Python dependencies
├── scripts/
│   └── init_db.py       # Initializes the SQLite database
├── server_setup.py       # Server setup and config helpers
├── shared.py             # Shared helper functions and permission logic
├── bot.db                # Generated SQLite database at runtime
└── main (1).py           # Legacy or duplicate script kept for reference
```

Note: this repository has some older or duplicate files from earlier development iterations. The active bot entry point is `bot.py`.

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

Set these environment variables in your deployment environment or shell:

- `TOKEN`: Discord bot token
- `GEMINI_API_KEY`: Gemini API key
- `GEMINI_MODEL`: Optional model ID (defaults to `gemini-3.1-flash-lite` in the codebase)
- `DB_PATH`: Optional SQLite database path; use a persistent location if you need data to survive restarts
- `PORT`: Optional port for the keep-alive web endpoint
- `LOG_LEVEL`: Optional logging level, for example `INFO` or `DEBUG`

In the Discord Developer Portal, enable Message Content Intent. The bot also needs permission to view and send messages in the relevant channels.

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

The project uses SQLite for user data and basic economy-style tracking. The database is initialized by `scripts/init_db.py`, and `DB_PATH` can be used to point to a different database file.

The schema includes tables such as:

- `users`
- `inventory`
- `guild_config`

## Notes

- This is a hobby project and not a large-scale production bot framework.
- The codebase is intentionally compact and easy to extend.
- Some files may be legacy or duplicate remnants from earlier development iterations.

## License

This project does not currently include a dedicated license file. If you want to use or redistribute it, you should ask the maintainer for permission or a licensing agreement.

## Data storage policy

VLG Bot stores only the data needed to provide its features. This section describes the bot's own storage; Discord and Gemini may process data under their respective policies.

- **What is stored:** Discord server and user IDs, economy/leveling data (such as coins, XP, inventory, and cooldowns), server settings, and per-server message totals. If AI memory is used, the bot also stores the prompted conversation text, its reply, and the participating member's ID and names.
- **How and where it is stored:** Data is written to a local SQLite database. The default file is `bot.db`; setting `DB_PATH` (or, for some components, `BOT_DB_PATH`) changes its location. On a hosted deployment, the hosting provider's configured disk determines the physical storage and whether the file survives restarts. The project maintainer does not specify a separate cloud database.
- **How long it is kept:** AI conversation memory is limited to the latest 20 exchanges per server and is removed after 30 days. Other saved records, including economy data, settings, and message totals, have no automatic expiry and remain in the database until removed or the database file is deleted.
- **AI processing:** When the AI reply feature is used, the relevant prompt and conversation context are sent to Gemini to generate a response. Avoid sharing sensitive information with the bot.
- **Deletion:** Members can use `/ai-memory-forget` to remove their AI exchanges in a server; a member with Manage Server can use `/ai-memory-clear` to clear that server's AI memory. Other stored records can be removed by deleting the corresponding database data or database file; deleting the file removes all locally stored bot data.
