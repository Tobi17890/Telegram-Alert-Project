"""Extract CRT data and calculate customer purchase frequency."""

from src.analytics.purchase_frequency import (
    calculate_purchase_frequency,
)
from src.config import PROJECT_ROOT
from src.database import get_database_connection
from src.query_service import fetch_dataframe_in_batches
from src.config import (
    PROJECT_ROOT,
    get_telegram_settings,
)

from src.notifications.telegram_message import (
    build_province_alert_messages,
)

from src.notifications.telegram_service import (
    send_province_alert_messages,
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "outputs"
    / "purchase_frequency"
)


# Replace these four values with the exact CRT column names.
CUSTOMER_ID_COLUMN = "Sold-to-party ID"
CUSTOMER_NAME_COLUMN = "Sold-to-party Name"
PROVINCE_COLUMN = "Sales District"
BILLING_DATE_COLUMN = "Billing Date"
DELIVERY_QUANTITY_COLUMN = "Net Amount"


def run_purchase_frequency_pipeline() -> None:
    """
    Fetch the complete CRT table and calculate customer frequency.
    """

    connection = get_database_connection()

    try:
        print("\nFetching the complete CRT table...")

        crt_dataframe = fetch_dataframe_in_batches(
            connection=connection,
            sql_filename="extracts/tpp_all.sql",
            batch_size=20_000
        )

    finally:
        connection.close()
        print("\nDatabase connection closed.")

    print(f"\nCRT rows fetched: {len(crt_dataframe):,}")
    print(f"CRT columns fetched: {len(crt_dataframe.columns):,}")

    print("\nAvailable CRT columns:")
    for column in crt_dataframe.columns:
        print(f" - {column}")

    purchase_gap_detail, customer_summary = (
        calculate_purchase_frequency(
            crt_dataframe=crt_dataframe,
            customer_id_column=CUSTOMER_ID_COLUMN,
            customer_name_column=CUSTOMER_NAME_COLUMN,
            billing_date_column=BILLING_DATE_COLUMN,
            delivery_quantity_column=DELIVERY_QUANTITY_COLUMN,
            province_column=PROVINCE_COLUMN
        )
    )

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    gap_output_path = (
        OUTPUT_DIRECTORY
        / "crt_purchase_gap_detail.csv"
    )

    summary_output_path = (
        OUTPUT_DIRECTORY
        / "crt_customer_frequency_summary.csv"
    )

    purchase_gap_detail.to_csv(
        gap_output_path,
        index=False,
        encoding="utf-8-sig"
    )

    customer_summary.to_csv(
        summary_output_path,
        index=False,
        encoding="utf-8-sig"
    )

    weekly_customers = customer_summary[
        customer_summary["customer_category"]
        == "Weekly Customer"
    ]

    print("\nCustomer-frequency results:")
    print(f"Total customers: {len(customer_summary):,}")
    print(f"Weekly customers: {len(weekly_customers):,}")

    print("\nWeekly customer sample:")

    if weekly_customers.empty:
        print("No weekly customers were identified.")
    else:
        print(
            weekly_customers.head(20).to_string(
                index=False
            )
        )

    print("\nFiles created:")
    print(gap_output_path)
    print(summary_output_path)
    print(
    "\nPreparing Telegram alerts "
    "grouped by province..."
)

    telegram_messages = (
    build_province_alert_messages(
        customer_summary=customer_summary,
        max_rows_per_message=15,
    )
)

    print(
    "Telegram messages prepared: "
    f"{len(telegram_messages):,}"
)

    bot_token, chat_id = (
    get_telegram_settings()
    )

    print(
    "\nSending real Telegram alerts..."
    )

    sent_messages = (
        send_province_alert_messages(
            messages=telegram_messages,
            bot_token=bot_token,
            chat_id=chat_id,
        )
    )

    print(
        "\nTelegram alert process completed."
    )

    print(
        "\nTelegram alert process completed."
    )

    print(
        "Messages sent successfully: "
        f"{len(sent_messages):,}"
    )