"""
shared.py - permission helpers, shared fun content, embed builders and prefix-parsing helpers
used by bot.py (moved out of it to keep every file short).
"""
import random
from typing import Optional

import discord
from discord import app_commands

# ====================== MASTER DEV LIST ======================
TRUSTED_DEV_IDS = [
    1151184036681752576,  # pepper
    1273920706584776764,  # ahnitpa
    1325908309534048318,  # luchoo (Lightsout)
]


def build_prefix_help() -> str:
