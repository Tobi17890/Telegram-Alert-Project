"""Display Telegram chats that have recently contacted the bot."""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parent.parent

load_dotenv(PROJECT_ROOT / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError(
        "TELEGRAM_BOT_TOKEN is missing from the .env file."
    )


def main() -> None:
    """Retrieve recent bot updates and print their chat IDs."""

    url = (
        f"https://api.telegram.org/"
        f"bot{BOT_TOKEN}/getUpdates"
    )

    response = requests.get(
        url,
        timeout=30,
    )

    response.raise_for_status()

    response_data = response.json()

    if not response_data.get("ok"):
        raise RuntimeError(
            response_data.get(
                "description",
                "Telegram rejected the request.",
            )
        )

    updates = response_data.get("result", [])

    if not updates:
        print(
            "No messages were found.\n"
            "Send /start to the bot first, then run this file again."
        )
        return

    discovered_chats: dict[str, dict] = {}

    for update in updates:
        message = (
            update.get("message")
            or update.get("channel_post")
            or update.get("edited_message")
        )

        if not message:
            continue

        chat = message.get("chat")

        if not chat:
            continue

        chat_id = str(chat.get("id"))

        discovered_chats[chat_id] = chat

    if not discovered_chats:
        print("No usable Telegram chats were found.")
        return

    print("\nTelegram chats found:\n")

    for chat_id, chat in discovered_chats.items():
        chat_type = chat.get("type", "")
        title = (
            chat.get("title")
            or chat.get("username")
            or chat.get("first_name")
            or ""
        )

        print(f"Chat ID: {chat_id}")
        print(f"Name: {title}")
        print(f"Type: {chat_type}")
        print("-" * 40)


if __name__ == "__main__":
    main()