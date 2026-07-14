"""Application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Extracting Data/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Extracting Data/.env
ENV_FILE = PROJECT_ROOT / ".env"

# Extracting Data/sql/
SQL_DIRECTORY = PROJECT_ROOT / "sql"

# Load environment variables
load_dotenv(ENV_FILE)

# SQL_CONNECTION_STRING = os.getenv("SQL_CONNECTION_STRING")

# if not SQL_CONNECTION_STRING:
#     raise RuntimeError(
#         "SQL_CONNECTION_STRING was not found.\n"
#         f"Check the environment file: {ENV_FILE}"
#     )

SQL_CONNECTION_STRING = os.getenv(
    "SQL_CONNECTION_STRING"
)

TELEGRAM_BOT_TOKEN = os.getenv(
    "TELEGRAM_BOT_TOKEN"
)

TELEGRAM_CHAT_ID = os.getenv(
    "TELEGRAM_CHAT_ID"
)


if not SQL_CONNECTION_STRING:
    raise RuntimeError(
        "SQL_CONNECTION_STRING is missing from .env."
    )


def get_telegram_settings() -> tuple[str, str]:
    """
    Return the Telegram bot token and destination chat ID.
    """

    missing_settings = []

    if not TELEGRAM_BOT_TOKEN:
        missing_settings.append(
            "TELEGRAM_BOT_TOKEN"
        )

    if not TELEGRAM_CHAT_ID:
        missing_settings.append(
            "TELEGRAM_CHAT_ID"
        )

    if missing_settings:
        raise RuntimeError(
            "The following Telegram settings are missing "
            "from .env:\n"
            + "\n".join(
                f" - {setting}"
                for setting in missing_settings
            )
        )

    return (
        TELEGRAM_BOT_TOKEN,
        TELEGRAM_CHAT_ID,
    )