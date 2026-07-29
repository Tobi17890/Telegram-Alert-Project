"""Send formatted customer alerts through Telegram."""

import time

import requests


TELEGRAM_API_BASE_URL = (
    "https://api.telegram.org"
)


class TelegramSendError(
    RuntimeError
):
    """Raised when Telegram cannot send a message."""


def send_telegram_message(
    bot_token: str,
    chat_id: str,
    telegram_html: str,
) -> int:
    """Send one formatted Telegram message."""

    if not telegram_html.strip():
        raise ValueError(
            "Telegram message cannot be empty."
        )

    url = (
        f"{TELEGRAM_API_BASE_URL}"
        f"/bot{bot_token}/sendMessage"
    )

    payload = {
        "chat_id": chat_id,
        "text": telegram_html,
        "parse_mode": "HTML",
    }

    for attempt in range(2):
        try:
            response = requests.post(
                url,
                json=payload,
                timeout=(10, 30),
            )

        except requests.RequestException as error:
            raise TelegramSendError(
                "Could not connect to Telegram."
            ) from error

        try:
            response_data = response.json()

        except ValueError as error:
            raise TelegramSendError(
                "Telegram returned an invalid response.\n"
                f"HTTP status: {response.status_code}\n"
                f"Response: {response.text}"
            ) from error

        if (
            response.status_code == 429
            and attempt == 0
        ):
            retry_after = int(
                response_data
                .get("parameters", {})
                .get("retry_after", 1)
            )

            print(
                "Telegram requested a delay of "
                f"{retry_after} second(s)."
            )

            time.sleep(
                max(retry_after, 1)
            )

            continue

        if (
            not response.ok
            or not response_data.get("ok")
        ):
            description = (
                response_data.get(
                    "description",
                    response.text,
                )
            )

            raise TelegramSendError(
                "Telegram rejected the message.\n"
                f"HTTP status: {response.status_code}\n"
                f"Reason: {description}"
            )

        message_id = (
            response_data
            .get("result", {})
            .get("message_id")
        )

        if message_id is None:
            raise TelegramSendError(
                "Telegram accepted the message "
                "but returned no message ID."
            )

        return int(message_id)

    raise TelegramSendError(
        "Message failed after retrying."
    )


def send_province_alert_messages(
    messages: list[dict[str, object]],
    bot_token: str,
    chat_id: str,
) -> list[dict[str, object]]:
    """Send all prepared province-alert messages."""

    if not messages:
        print(
            "No Telegram messages were generated."
        )
        return []

    sent_results: list[
        dict[str, object]
    ] = []

    total_messages = len(messages)

    for index, message in enumerate(
        messages,
        start=1,
    ):
        province = str(
            message["province"]
        )

        section = str(
            message.get(
                "section",
                "Customer Info",
            )
        )

        part_number = int(
            message["part_number"]
        )

        total_parts = int(
            message["total_parts"]
        )

        print(
            "\nSending message "
            f"{index}/{total_messages}: "
            f"{province}, "
            f"{section}, "
            f"part {part_number}/{total_parts}"
        )

        message_id = send_telegram_message(
            bot_token=bot_token,
            chat_id=chat_id,
            telegram_html=str(
                message["telegram_html"]
            ),
        )

        sent_results.append(
            {
                "province": province,
                "section": section,
                "part_number": part_number,
                "total_parts": total_parts,
                "message_id": message_id,
            }
        )

        print(
            "Sent successfully. "
            f"Message ID: {message_id}"
        )

        time.sleep(0.3)

    return sent_results
