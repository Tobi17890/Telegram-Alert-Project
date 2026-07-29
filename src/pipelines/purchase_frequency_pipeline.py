"""Run the Phase 2 TPP customer-frequency Telegram pipeline."""

from src.analytics.purchase_frequency import (
    enrich_customer_frequency_summary,
)
from src.config import (
    PROJECT_ROOT,
    get_telegram_settings,
)
from src.database import get_database_connection
from src.notifications.telegram_message import (
    build_province_alert_messages,
)
from src.notifications.telegram_service import (
    send_province_alert_messages,
)
from src.query_service import fetch_dataframe


OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "outputs"
    / "purchase_frequency"
)

EXPORT_GAP_DETAIL = False

# Keep False while reviewing the new bordered message.
# Change to True after checking the generated preview file.
SEND_TELEGRAM = True

MINIMUM_ALERT_PROBABILITY = 80.0
MAX_ROWS_PER_MESSAGE = 15


def run_purchase_frequency_pipeline() -> None:
    """
    Fetch one SQL summary row per customer, enrich the result,
    export CSV output, prepare Telegram alerts, and optionally send.
    """

    connection = get_database_connection()
    purchase_gap_detail = None

    try:
        print(
            "\nFetching Phase 2 TPP customer summary "
            "(one row per customer)..."
        )

        customer_summary_base = fetch_dataframe(
            connection=connection,
            sql_filename=(
                "analytics/"
                "tpp_customer_frequency_summary.sql"
            ),
        )

        if EXPORT_GAP_DETAIL:
            print(
                "\nFetching optional purchase-gap detail..."
            )

            purchase_gap_detail = fetch_dataframe(
                connection=connection,
                sql_filename=(
                    "analytics/"
                    "tpp_purchase_gap_detail.sql"
                ),
            )

    finally:
        connection.close()
        print("\nDatabase connection closed.")

    print(
        "\nCustomer summary rows fetched: "
        f"{len(customer_summary_base):,}"
    )

    print(
        "Customer summary columns fetched: "
        f"{len(customer_summary_base.columns):,}"
    )

    customer_summary = enrich_customer_frequency_summary(
        customer_summary_dataframe=customer_summary_base,
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    summary_output_path = (
        OUTPUT_DIRECTORY
        / "tpp_customer_frequency_summary.csv"
    )

    customer_summary.to_csv(
        summary_output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print("\nFiles created:")
    print(summary_output_path)

    if purchase_gap_detail is not None:
        gap_output_path = (
            OUTPUT_DIRECTORY
            / "tpp_purchase_gap_detail.csv"
        )

        purchase_gap_detail.to_csv(
            gap_output_path,
            index=False,
            encoding="utf-8-sig",
        )

        print(gap_output_path)

    telegram_messages = build_province_alert_messages(
        customer_summary=customer_summary,
        max_rows_per_message=MAX_ROWS_PER_MESSAGE,
        minimum_probability=MINIMUM_ALERT_PROBABILITY,
    )

    active_alerts = customer_summary[
        (customer_summary["customer_status"] == "Active")
        & (
            customer_summary[
                "purchase_probability_percent"
            ]
            >= MINIMUM_ALERT_PROBABILITY
        )
    ]

    inactive_alerts = customer_summary[
        (customer_summary["customer_status"] == "Inactive")
        & (
            customer_summary[
                "purchase_probability_percent"
            ]
            >= MINIMUM_ALERT_PROBABILITY
        )
    ]

    print("\nTelegram alert results:")
    print(
        "Active due customers: "
        f"{len(active_alerts):,}"
    )
    print(
        "Inactive re-engagement customers: "
        f"{len(inactive_alerts):,}"
    )
    print(
        "Telegram messages prepared: "
        f"{len(telegram_messages):,}"
    )

    preview_output_path = (
        OUTPUT_DIRECTORY
        / "telegram_alert_preview.txt"
    )

    preview_text = (
        "\n\n"
        + ("=" * 80)
        + "\n\n"
    ).join(
        str(message["plain_text"])
        for message in telegram_messages
    )

    preview_output_path.write_text(
        preview_text,
        encoding="utf-8",
    )

    print(preview_output_path)

    if not SEND_TELEGRAM:
        print(
            "\nTelegram sending is disabled. "
            "Review telegram_alert_preview.txt, "
            "then set SEND_TELEGRAM = True."
        )
        return

    bot_token, chat_id = get_telegram_settings()

    print("\nSending real Telegram alerts...")

    sent_messages = send_province_alert_messages(
        messages=telegram_messages,
        bot_token=bot_token,
        chat_id=chat_id,
    )

    print("\nTelegram alert process completed.")

    print(
        "Messages sent successfully: "
        f"{len(sent_messages):,}"
    )
