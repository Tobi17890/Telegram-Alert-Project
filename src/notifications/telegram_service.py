"""Send customer alerts using personal Telegram account."""

import asyncio

from telethon import TelegramClient
from telethon.errors import FloodWaitError


# ============================================
# TELEGRAM ACCOUNT SETTINGS
# ============================================

# Keep your existing API ID here.
API_ID = 20722579

# Keep your existing API HASH here.
API_HASH = "45fb209e7760bb6f4dae0a3d1983a5c2"


SESSION_NAME = (
    "notebooks/my_telegram_session"
)


# ============================================
# SENDING SETTINGS
# ============================================

# Normal delay between successful messages.
MESSAGE_DELAY_SECONDS = 3

# Extra safety time after Telegram's
# required FloodWait duration.
FLOOD_WAIT_BUFFER_SECONDS = 5


# ============================================
# SEND ONE TELEGRAM MESSAGE
# ============================================

async def send_telegram_message(
    client: TelegramClient,
    chat_id: int,
    message_thread_id: int,
    telegram_html: str,
) -> int:
    """
    Send one message to a specific Telegram forum topic
    using the logged-in personal Telegram account.

    If Telegram applies a FloodWait,
    automatically wait and retry the same message.
    """

    if not telegram_html.strip():
        raise ValueError(
            "Telegram message cannot be empty."
        )

    while True:

        try:

            sent_message = await client.send_message(
                entity=chat_id,
                message=telegram_html,
                parse_mode="html",
                reply_to=message_thread_id,
            )

            return int(
                sent_message.id
            )

        except FloodWaitError as error:

            wait_seconds = int(
                error.seconds
            )

            print(
                "\n========================================"
            )

            print(
                "TELEGRAM RATE LIMIT DETECTED"
            )

            print(
                "========================================"
            )

            print(
                "Telegram requires a wait of "
                f"{wait_seconds} second(s)."
            )

            print(
                "The program will wait automatically."
            )

            print(
                "Do NOT restart the program."
            )

            print(
                "========================================"
            )

            await asyncio.sleep(
                wait_seconds
                + FLOOD_WAIT_BUFFER_SECONDS
            )

            print(
                "\nFloodWait finished."
            )

            print(
                "Retrying the same message..."
            )


# ============================================
# SEND ALL ROUTED MESSAGES
# ============================================

async def _send_all_messages(
    messages: list[dict[str, object]],
) -> list[dict[str, object]]:
    """
    Send all prepared Telegram messages
    using one personal Telegram session.
    """

    sent_results = []

    async with TelegramClient(
        SESSION_NAME,
        API_ID,
        API_HASH,
    ) as client:

        total_messages = len(
            messages
        )

        print(
            "\n========================================"
        )

        print(
            "TELEGRAM SENDING STARTED"
        )

        print(
            "========================================"
        )

        print(
            "Total messages to send: "
            f"{total_messages:,}"
        )


        for index, message in enumerate(
            messages,
            start=1,
        ):

            # ==================================
            # MESSAGE INFORMATION
            # ==================================

            province = str(
                message["province"]
            )

            region = str(
                message["region"]
            )

            section = str(
                message.get(
                    "section",
                    "Customer Info",
                )
            )

            chat_id = int(
                message["chat_id"]
            )

            message_thread_id = int(
                message[
                    "message_thread_id"
                ]
            )

            part_number = int(
                message.get(
                    "part_number",
                    1,
                )
            )

            total_parts = int(
                message.get(
                    "total_parts",
                    1,
                )
            )


            # ==================================
            # CONSOLE INFORMATION
            # ==================================

            print(
                "\n----------------------------------------"
            )

            print(
                f"Sending message "
                f"{index}/{total_messages}"
            )

            print(
                f"Region: {region}"
            )

            print(
                f"Province: {province}"
            )

            print(
                f"Section: {section}"
            )

            print(
                f"Chat ID: {chat_id}"
            )

            print(
                "Topic ID: "
                f"{message_thread_id}"
            )

            print(
                f"Part: "
                f"{part_number}/"
                f"{total_parts}"
            )


            # ==================================
            # SEND
            # ==================================

            message_id = (
                await send_telegram_message(
                    client=client,
                    chat_id=chat_id,
                    message_thread_id=(
                        message_thread_id
                    ),
                    telegram_html=str(
                        message[
                            "telegram_html"
                        ]
                    ),
                )
            )


            # ==================================
            # STORE RESULT
            # ==================================

            sent_results.append(
                {
                    "region": region,
                    "province": province,
                    "section": section,
                    "chat_id": chat_id,
                    "message_thread_id": (
                        message_thread_id
                    ),
                    "part_number": (
                        part_number
                    ),
                    "total_parts": (
                        total_parts
                    ),
                    "message_id": (
                        message_id
                    ),
                }
            )


            print(
                "Sent successfully."
            )

            print(
                "Telegram Message ID: "
                f"{message_id}"
            )


            # ==================================
            # NORMAL MESSAGE DELAY
            # ==================================
            #
            # Do not send messages too rapidly
            # from the personal Telegram account.
            # ==================================

            if index < total_messages:

                print(
                    "Waiting "
                    f"{MESSAGE_DELAY_SECONDS} "
                    "second(s) before next message..."
                )

                await asyncio.sleep(
                    MESSAGE_DELAY_SECONDS
                )


    print(
        "\n========================================"
    )

    print(
        "TELEGRAM SENDING COMPLETED"
    )

    print(
        "========================================"
    )

    print(
        "Messages successfully sent: "
        f"{len(sent_results):,}"
    )

    return sent_results


# ============================================
# SYNCHRONOUS PIPELINE WRAPPER
# ============================================

def send_province_alert_messages(
    messages: list[dict[str, object]],
) -> list[dict[str, object]]:
    """
    Synchronous wrapper used by
    purchase_frequency_pipeline.py.
    """

    if not messages:

        print(
            "No Telegram messages "
            "were generated."
        )

        return []

    return asyncio.run(
        _send_all_messages(
            messages=messages,
        )
    )