# VLG Bot

Lightweight Discord bot with moderation, utility, music, and Gemini AI replies.

## Gemini AI replies and server memory

The bot replies when a member mentions it or directly replies to one of its messages. It keeps a **small, server-wide conversation context** so it can follow up on recent AI conversations and associate each AI question with the member's Discord display name, username, and ID.

Memory scope and safeguards:

- Context is isolated by Discord server and shared across that server's channels; it is never shared with another server.
- Only messages that explicitly mention/reply to the bot are retained. The bot does not ingest ordinary server chat or fetch profile details.
- The database keeps at most the latest 20 AI exchanges per server, for up to 30 days.
- Conversation text is sent to Gemini for inference to answer the request. This is contextual recall, not model training or fine-tuning.
- Members can run `/ai-memory-forget` to delete their saved AI exchanges in that server.
- A member with Manage Server can run `/ai-memory-clear` to clear the server's saved AI exchanges.

Because memory is shared within a server, let members know before enabling it. For persistence across host restarts, configure `DB_PATH` to a persistent disk/location supported by your host; a temporary filesystem may lose memory on redeploy.

## Configuration

Set these environment variables in the deployment service:

- `TOKEN`: Discord bot token
- `GEMINI_API_KEY`: Gemini API key (keep it secret; never commit it)
- `GEMINI_MODEL`: optional model ID (defaults to `gemini-3.1-flash-lite`)
- `DB_PATH`: optional SQLite file path; use persistent storage if memory should survive restarts

In the Discord Developer Portal, enable **Message Content Intent**. The bot also needs permission to view and send messages in the relevant channels.

Install dependencies with `pip install -r requirements.txt` and start with `python bot.py`.
