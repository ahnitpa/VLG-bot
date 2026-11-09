# VLG Bot

A lightweight Discord bot for server management, entertainment, moderation, and music playback.

## Gemini AI replies

The bot responds to direct mentions and direct replies to one of its messages. Configure these environment variables in the deployment service:

- `TOKEN`: Discord bot token
- `GEMINI_API_KEY`: Gemini API key (keep this secret; do not commit it)
- `GEMINI_MODEL`: optional Gemini model ID (default: `gemini-3.1-flash-lite`)

In the Discord Developer Portal, enable the **Message Content Intent** for the bot application. The bot also needs permission to view and send messages in the channel.

After adding the environment variables, deploy/restart the service from the repository's `main` branch. Test with `@BotName hello` or reply to a message sent by the bot.

Install dependencies with `pip install -r requirements.txt` and start using `python bot.py`.
