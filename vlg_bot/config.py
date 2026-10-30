"""Shared configuration for the VLG Bot."""

import os

TRUSTED_DEV_IDS = [
    1151184036681752576,
    1373999565312888842,
    1325908309534048318,
]

LOG_CHANNEL_NAMES = ("bot-logs",)

PORT = int(os.environ.get("PORT", 8080))
TOKEN = os.environ.get("TOKEN")
