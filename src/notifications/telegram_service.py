"""Send customer alerts and online follow-up links using personal Telegram account."""

import asyncio
from html import escape
from pathlib import Path

from telethon import TelegramClient
from telethon.errors import FloodWaitError

import os
from dotenv import load_dotenv

load_dotenv(override=True)


# ============================================
# TELEGRAM ACCOUNT SETTINGS
# ============================================

# Keep your EXISTING values here.
API_ID = int(os.getenv("TELEGRAM_API_ID"))
API_HASH = str(os.getenv("TELEGRAM_API_HASH"))


SESSION_NAME = (
    "notebooks/my_telegram_session"
)


# ============================================
# SENDING SETTINGS
# ============================================

# Delay between successful Telegram operations.
MESSAGE_DELAY_SECONDS = 3


# Extra safety time after Telegram FloodWait.
FLOOD_WAIT_BUFFER_SECONDS = 5


# ============================================
# FLOOD WAIT
# ============================================

async def _handle_flood_wait(
    error: FloodWaitError,
) -> None:
    """Wait for Telegram FloodWait and continue."""

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
        "Retrying..."
    )


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
    Send one HTML message to a Telegram forum topic.
    """

    if not telegram_html.strip():

        raise ValueError(
            "Telegram message cannot be empty."
        )


    while True:

        try:

            sent_message = (
                await client.send_message(
                    entity=chat_id,
                    message=telegram_html,
                    parse_mode="html",
                    reply_to=message_thread_id,
                )
            )


            return int(
                sent_message.id
            )


        except FloodWaitError as error:

            await _handle_flood_wait(
                error
            )


# ============================================
# SEND ONE EXCEL FILE
# ============================================

async def send_telegram_excel_file(
    client: TelegramClient,
    chat_id: int,
    message_thread_id: int,
    excel_file_path: Path,
    caption: str,
) -> int:
    """
    Send one Excel workbook to the same
    Telegram forum topic as the alert.
    """

    excel_file_path = Path(
        excel_file_path
    )


    if not excel_file_path.exists():

        raise FileNotFoundError(
            "Excel file does not exist:\n"
            f"{excel_file_path}"
        )


    if (
        excel_file_path.suffix.lower()
        != ".xlsx"
    ):

        raise ValueError(
            "Telegram follow-up file must "
            "be an .xlsx file."
        )


    while True:

        try:

            sent_file = (
                await client.send_file(
                    entity=chat_id,
                    file=str(
                        excel_file_path
                    ),
                    caption=caption,
                    reply_to=(
                        message_thread_id
                    ),
                    force_document=True,
                )
            )


            return int(
                sent_file.id
            )


        except FloodWaitError as error:

            await _handle_flood_wait(
                error
            )


# ============================================
# GROUP MESSAGES BY PROVINCE
# ============================================

def _group_messages_by_province(
    messages: list[
        dict[
            str,
            object,
        ]
    ],
) -> dict[
    str,
    list[
        dict[
            str,
            object,
        ]
    ],
]:
    """
    Group routed messages by province
    while preserving their current order.

    Current Telegram formatter order remains:

    Active
      Weekly
      Bi-Weekly
      Monthly
      Bi-Monthly

    then

    Inactive
      Weekly
      Bi-Weekly
      Monthly
      Bi-Monthly
    """

    grouped_messages = {}


    for message in messages:

        province = str(
            message[
                "province"
            ]
        ).strip()


        if province not in grouped_messages:

            grouped_messages[
                province
            ] = []


        grouped_messages[
            province
        ].append(
            message
        )


    return grouped_messages


# ============================================
# VALIDATE ONLINE FOLLOW-UP LINKS
# ============================================

def _validate_follow_up_links(
    grouped_messages: dict,
    follow_up_links: dict[str, str],
) -> None:
    """Verify every routed province has one usable online link."""

    missing_links = []

    for province in grouped_messages:
        follow_up_url = str(
            follow_up_links.get(province, "")
        ).strip()

        if not follow_up_url:
            missing_links.append(province)
            continue

        if not (
            follow_up_url.startswith("https://")
            or follow_up_url.startswith("http://")
        ):
            raise ValueError(
                f"Invalid follow-up URL for {province}:\n{follow_up_url}"
            )

    if missing_links:
        raise ValueError(
            "Telegram sending cancelled. Missing online follow-up link for: "
            + ", ".join(sorted(missing_links))
        )


# ============================================
# SEND ALL PROVINCE PACKAGES
# ============================================

async def _send_all_province_packages(
    messages: list[
        dict[
            str,
            object,
        ]
    ],
    follow_up_links: dict[
        str,
        str,
    ],
    product: str,
) -> list[
    dict[
        str,
        object,
    ]
]:
    """
    Send Telegram alerts province by province.

    For each province:

    1. Send all Active message parts.
    2. Send all Inactive message parts.
    3. Send ONE matching online follow-up link.
    """

    product = str(
        product
    ).strip().upper()


    # ========================================
    # GROUP BY PROVINCE
    # ========================================

    grouped_messages = (
        _group_messages_by_province(
            messages
        )
    )


    # ========================================
    # SAFETY CHECK
    # ========================================
    #
    # Do this before connecting/sending.
    # We don't want to send Telegram messages
    # and only discover later that Excel
    # is missing.
    #
    # ========================================

    _validate_follow_up_links(
        grouped_messages=(
            grouped_messages
        ),
        follow_up_links=(
            follow_up_links
        ),
    )


    sent_results = []


    # ========================================
    # TELEGRAM SESSION
    # ========================================

    async with TelegramClient(
        SESSION_NAME,
        API_ID,
        API_HASH,
    ) as client:


        total_provinces = len(
            grouped_messages
        )


        print(
            "\n========================================"
        )

        print(
            f"{product} TELEGRAM PACKAGE "
            "SENDING STARTED"
        )

        print(
            "========================================"
        )

        print(
            "Total provinces: "
            f"{total_provinces:,}"
        )


        # ====================================
        # EACH PROVINCE
        # ====================================

        for (
            province_index,
            (
                province,
                province_messages,
            ),
        ) in enumerate(
            grouped_messages.items(),
            start=1,
        ):


            print(
                "\n"
                + "=" * 50
            )

            print(
                f"{product} | "
                f"{province}"
            )

            print(
                "Province "
                f"{province_index}/"
                f"{total_provinces}"
            )

            print(
                "=" * 50
            )


            # =================================
            # ROUTING
            # =================================
            #
            # All messages for a province
            # should have the same destination.
            #
            # =================================

            first_message = (
                province_messages[
                    0
                ]
            )


            region = str(
                first_message[
                    "region"
                ]
            )


            chat_id = int(
                first_message[
                    "chat_id"
                ]
            )


            message_thread_id = int(
                first_message[
                    "message_thread_id"
                ]
            )


            print(
                f"Region: {region}"
            )

            print(
                f"Chat ID: {chat_id}"
            )

            print(
                "Topic ID: "
                f"{message_thread_id}"
            )


            # =================================
            # SEND ALL MESSAGES
            # =================================

            total_messages = len(
                province_messages
            )


            for (
                message_index,
                message,
            ) in enumerate(
                province_messages,
                start=1,
            ):


                section = str(
                    message.get(
                        "section",
                        "Customer Info",
                    )
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


                print(
                    "\n----------------------------------------"
                )

                print(
                    "Sending alert message "
                    f"{message_index}/"
                    f"{total_messages}"
                )

                print(
                    f"Section: {section}"
                )

                print(
                    f"Part: "
                    f"{part_number}/"
                    f"{total_parts}"
                )


                message_id = (
                    await send_telegram_message(
                        client=client,
                        chat_id=int(
                            message[
                                "chat_id"
                            ]
                        ),
                        message_thread_id=int(
                            message[
                                "message_thread_id"
                            ]
                        ),
                        telegram_html=str(
                            message[
                                "telegram_html"
                            ]
                        ),
                    )
                )


                sent_results.append(
                    {
                        "type": (
                            "message"
                        ),
                        "product": (
                            product
                        ),
                        "region": (
                            region
                        ),
                        "province": (
                            province
                        ),
                        "section": (
                            section
                        ),
                        "chat_id": (
                            chat_id
                        ),
                        "message_thread_id": (
                            message_thread_id
                        ),
                        "message_id": (
                            message_id
                        ),
                    }
                )


                print(
                    "Alert sent successfully."
                )

                print(
                    "Telegram Message ID: "
                    f"{message_id}"
                )


                # =============================
                # DELAY
                # =============================

                print(
                    "Waiting "
                    f"{MESSAGE_DELAY_SECONDS} "
                    "second(s)..."
                )


                await asyncio.sleep(
                    MESSAGE_DELAY_SECONDS
                )


            # =================================
            # SEND ONE ONLINE FOLLOW-UP LINK
            # =================================

            follow_up_url = str(
                follow_up_links[
                    province
                ]
            ).strip()

            follow_up_html = (
                f"<b>{escape(product)} Customer Alert Follow-up</b>\n"
                f"Province: {escape(province)}\n\n"
                f'<a href="{escape(follow_up_url, quote=True)}">'
                "Open online follow-up tracker</a>\n\n"
                "Please fill in the <b>Reason</b> column online."
            )

            print(
                "\n----------------------------------------"
            )

            print(
                "Sending province online follow-up link..."
            )

            link_message_id = (
                await send_telegram_message(
                    client=client,
                    chat_id=chat_id,
                    message_thread_id=(
                        message_thread_id
                    ),
                    telegram_html=(
                        follow_up_html
                    ),
                )
            )

            sent_results.append(
                {
                    "type": "follow_up_link",
                    "product": product,
                    "region": region,
                    "province": province,
                    "chat_id": chat_id,
                    "message_thread_id": message_thread_id,
                    "message_id": link_message_id,
                    "follow_up_url": follow_up_url,
                }
            )

            print(
                "Online follow-up link sent successfully."
            )

            print(
                "Telegram Link Message ID: "
                f"{link_message_id}"
            )


            # =================================
            # DELAY BEFORE NEXT PROVINCE
            # =================================

            if (
                province_index
                <
                total_provinces
            ):

                print(
                    "\nWaiting "
                    f"{MESSAGE_DELAY_SECONDS} "
                    "second(s) before "
                    "next province..."
                )


                await asyncio.sleep(
                    MESSAGE_DELAY_SECONDS
                )


    # ========================================
    # FINAL RESULT
    # ========================================

    message_count = sum(
        1
        for result
        in sent_results
        if result[
            "type"
        ]
        == "message"
    )


    follow_up_link_count = sum(
        1
        for result
        in sent_results
        if result[
            "type"
        ]
        == "follow_up_link"
    )


    print(
        "\n========================================"
    )

    print(
        f"{product} TELEGRAM PACKAGE "
        "SENDING COMPLETED"
    )

    print(
        "========================================"
    )

    print(
        "Alert messages sent: "
        f"{message_count:,}"
    )

    print(
        "Online follow-up links sent: "
        f"{follow_up_link_count:,}"
    )


    return sent_results


# ============================================
# NEW SYNCHRONOUS PACKAGE WRAPPER
# ============================================

def send_province_alert_packages(
    messages: list[
        dict[
            str,
            object,
        ]
    ],
    follow_up_links: dict[
        str,
        str,
    ],
    product: str,
) -> list[
    dict[
        str,
        object,
    ]
]:
    """
    Send alert messages plus ONE online follow-up link
    for every province.
    """

    if not messages:

        print(
            "No Telegram messages "
            "were generated."
        )

        return []


    return asyncio.run(
        _send_all_province_packages(
            messages=messages,
            follow_up_links=follow_up_links,
            product=product,
        )
    )


# ============================================
# OLD MESSAGE-ONLY WRAPPER
# ============================================
#
# Kept so older code does not immediately break.
#
# ============================================

def send_province_alert_messages(
    messages: list[
        dict[
            str,
            object,
        ]
    ],
) -> list[
    dict[
        str,
        object,
    ]
]:
    """
    Legacy message-only sender.

    New CRT/TPP pipelines should use:
    send_province_alert_packages()
    """

    if not messages:

        print(
            "No Telegram messages "
            "were generated."
        )

        return []


    return asyncio.run(
        _send_messages_only(
            messages=messages,
        )
    )


# ============================================
# LEGACY MESSAGE-ONLY ASYNC FUNCTION
# ============================================

async def _send_messages_only(
    messages: list[
        dict[
            str,
            object,
        ]
    ],
) -> list[
    dict[
        str,
        object,
    ]
]:
    """Keep old sending behavior available."""

    sent_results = []


    async with TelegramClient(
        SESSION_NAME,
        API_ID,
        API_HASH,
    ) as client:


        total_messages = len(
            messages
        )


        for (
            index,
            message,
        ) in enumerate(
            messages,
            start=1,
        ):


            message_id = (
                await send_telegram_message(
                    client=client,
                    chat_id=int(
                        message[
                            "chat_id"
                        ]
                    ),
                    message_thread_id=int(
                        message[
                            "message_thread_id"
                        ]
                    ),
                    telegram_html=str(
                        message[
                            "telegram_html"
                        ]
                    ),
                )
            )


            sent_results.append(
                {
                    "province": (
                        str(
                            message[
                                "province"
                            ]
                        )
                    ),
                    "message_id": (
                        message_id
                    ),
                }
            )


            print(
                f"Sent message "
                f"{index}/{total_messages}"
            )


            if index < total_messages:

                await asyncio.sleep(
                    MESSAGE_DELAY_SECONDS
                )


    return sent_results