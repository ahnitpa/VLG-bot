"""Centralized, stable error codes for VLG-bot.

Format: VLG-<CATEGORY>-<NUMBER>
Codes are grouped alphabetically by category and numbered in ascending order.
"""


ERROR_CODES = {
    "VLG-AUTH-001": "The requester does not have the required authorization.",
    "VLG-AUTH-002": "A required Discord permission is missing.",
    "VLG-AUTH-003": "The bot cannot perform an action due to role hierarchy.",

    "VLG-AUTO-001": "An inactive voice-channel configuration is invalid.",
    "VLG-AUTO-002": "An inactivity-channel ID could not be found.",

    "VLG-CMD-001": "Command arguments or syntax are invalid.",
    "VLG-CMD-002": "The command is currently on cooldown.",
    "VLG-CMD-003": "An unknown or unsupported command was received.",
    "VLG-CMD-004": "Command setup or global slash-command synchronization failed.",

    "VLG-DATA-001": "The requested target could not be resolved.",
    "VLG-DATA-002": "The supplied ID or numeric value is invalid.",

    "VLG-DISC-001": "Discord denied access to a requested action.",
    "VLG-DISC-002": "Discord could not find the requested resource.",
    "VLG-DISC-003": "A Discord HTTP request failed.",

    "VLG-FUN-001": "A user attempted to use an action against their own account.",
    "VLG-FUN-002": "A bot target is not allowed for this action.",

    "VLG-MOD-001": "A member could not be kicked.",
    "VLG-MOD-002": "A member could not be banned.",
    "VLG-MOD-003": "A member could not be timed out.",
    "VLG-MOD-004": "A timeout could not be removed.",

    "VLG-MUS-001": "The bot could not join or move to a voice channel.",
    "VLG-MUS-002": "The bot cannot play a requested media source.",
    "VLG-MUS-003": "The media source is private or unavailable.",
    "VLG-MUS-004": "The media source requires sign-in or updated cookies.",
    "VLG-MUS-005": "No playable tracks were found.",

    "VLG-RBAC-001": "A role is outside the bot's role hierarchy.",
    "VLG-RBAC-002": "A role is equal to or above the requester's highest role.",

    "VLG-SYS-001": "An unexpected internal error occurred.",
    "VLG-SYS-002": "The keep-alive web server could not start.",
    "VLG-SYS-003": "A required environment variable is missing.",

    "VLG-UTIL-001": "A category or channel could not be created.",
    "VLG-UTIL-002": "A channel could not be moved.",
    "VLG-UTIL-003": "The bot lacks permission to manage channels.",
}


def error(code: str, detail: str = "") -> str:
    """Return a consistent Discord-facing error message."""
    if code not in ERROR_CODES:
        code = "VLG-SYS-001"
    message = detail.strip() if detail else ERROR_CODES[code]
    return f"❌ **Error:** {message} `({code})`"
