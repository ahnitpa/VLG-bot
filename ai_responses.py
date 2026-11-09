"""Gemini-backed Discord message replies."""

import logging
import os
import re

import aiohttp
import discord

logger = logging.getLogger("vlg_bot.ai")
DEFAULT_MODEL = "gemini-3.1-flash-lite"


async def _is_reply_to_bot(bot: discord.Client, message: discord.Message) -> bool:
    reference = message.reference
    if reference is None or bot.user is None:
        return False

    resolved = reference.resolved
    if isinstance(resolved, discord.Message):
        return resolved.author.id == bot.user.id

    # Discord may omit the referenced message from the event payload. Fetch it
    # when possible so replies still trigger reliably after a restart/cache miss.
    if reference.message_id is None:
        return False
    try:
        original = await message.channel.fetch_message(reference.message_id)
        return original.author.id == bot.user.id
    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
        return False


def _get_prompt(message: discord.Message, bot: discord.Client) -> str:
    content = message.content or ""
    if bot.user is not None:
        content = re.sub(rf"<@!?{bot.user.id}>", "", content)
    content = re.sub(r"<@&\d+>", "", content)
    content = content.strip()
    return content or "Say hello and ask what you can help me with."


async def _generate(prompt: str, api_key: str, model: str) -> str:
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    payload = {
        "systemInstruction": {
            "parts": [{"text": "You are a helpful Discord assistant. Be friendly, concise, and useful."}]
        },
        "contents": [{"role": "user", "parts": [{"text": prompt[:4000]}]}],
        "generationConfig": {"maxOutputTokens": 700, "temperature": 0.7},
    }
    timeout = aiohttp.ClientTimeout(total=40)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(
            url,
            headers={"x-goog-api-key": api_key},
            json=payload,
        ) as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                error = data.get("error", {}) if isinstance(data, dict) else {}
                logger.error("Gemini API returned HTTP %s: %s", response.status, error.get("message", "unknown error"))
                raise RuntimeError(f"Gemini API HTTP {response.status}")

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError, AttributeError):
        logger.error("Gemini response did not contain text: %r", data)
        raise RuntimeError("Gemini returned no text")
    if not text:
        raise RuntimeError("Gemini returned an empty response")
    return text


async def handle_ai_reply(bot: discord.Client, message: discord.Message) -> bool:
    """Respond to a bot mention or a reply directly to one of its messages."""
    if message.guild is None or message.author.bot or bot.user is None:
        return False

    mentioned = any(user.id == bot.user.id for user in message.mentions)
    replied = await _is_reply_to_bot(bot, message)
    if not (mentioned or replied):
        return False

    # Avoid the legacy "Hi" path in bot.py after the AI response is handled.
    if mentioned:
        message.mentions = [user for user in message.mentions if user.id != bot.user.id]

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("AI trigger received, but GEMINI_API_KEY is not configured in the deployment environment")
        await message.reply(
            "AI replies aren't configured yet. Add `GEMINI_API_KEY` to the bot's deployment environment.",
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
        return True

    model = os.environ.get("GEMINI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    try:
        response_text = await _generate(_get_prompt(message, bot), api_key, model)
    except (aiohttp.ClientError, TimeoutError, RuntimeError, ValueError) as exc:
        logger.exception("Gemini response generation failed")
        response_text = "I couldn't get an AI response just now. Check the deployment logs and Gemini API key/model settings."
    except Exception:
        logger.exception("Unexpected error while generating Gemini response")
        response_text = "I couldn't get an AI response just now. Please try again in a moment."

    try:
        await message.reply(
            response_text[:2000],
            mention_author=False,
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        logger.exception("Discord failed to deliver the Gemini reply")
    return True
