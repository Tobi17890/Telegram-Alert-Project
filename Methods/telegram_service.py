import requests
import pandas as pd
from html import escape


def format_customer_message(row, fields: list[str] | None = None) -> str:
    if fields is None:
        fields = [
            "Sold-to-party ID",
            "Sold-to-party Name",
            "Ship-to-party ID",
            "Ship-to-party Name",
            "Material Name",
            "Sales Order No",
        ]

    lines = ["<b>Customer Information</b>"]

    for field in fields:
        if field in row.index:
            value = row[field]

            if pd.isna(value):
                value = ""

            lines.append(f"<b>{escape(field)}:</b> {escape(str(value))}")

    return "\n".join(lines)


def send_text_to_telegram(bot_token: str, chat_id: str, message: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    payload = {
        "chat_id": chat_id,
        "message_thread_id": message_thread_id,
        "text": telegram_html,
        "parse_mode": "HTML",
    }

    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()

    return response.json()