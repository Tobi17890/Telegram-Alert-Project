"""Run the Phase 2 TPP customer-frequency Telegram pipeline."""

from src.analytics.tpp_purchase_frequency import (
    enrich_customer_frequency_summary,
)

from src.config import (
    PROJECT_ROOT,
    get_telegram_settings,
)

from src.database import (
    get_database_connection,
)

from src.notifications.telegram_message import (
    build_province_alert_messages,
)

from src.notifications.telegram_service import (
    send_province_alert_messages,
)

from src.notifications.telegram_routes import (
    get_telegram_route,
)

from src.query_service import (
    fetch_dataframe,
)


# ============================================
# OUTPUT SETTINGS
# ============================================

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "outputs"
    / "purchase_frequency"
)


# ============================================
# PIPELINE SETTINGS
# ============================================

EXPORT_GAP_DETAIL = False


# Keep False while testing.
# Change to True only when ready
# to send real Telegram alerts.
SEND_TELEGRAM = True


# Current alert rule.
MINIMUM_ALERT_PROBABILITY = 60.0


# Maximum customers in
# one Telegram message.
MAX_ROWS_PER_MESSAGE = 15


# ============================================
# MAIN PIPELINE
# ============================================


def tpp_run_purchase_frequency_pipeline() -> None:
    """
    Run the TPP purchase-frequency pipeline.

    Steps:
    1. Fetch SQL customer summary.
    2. Apply Python business rules.
    3. Export CSV.
    4. Create Telegram messages.
    5. Route each province to the correct
       Telegram group/topic.
    6. Create preview.
    7. Optionally send real Telegram alerts.
    """

    # ========================================
    # DATABASE EXTRACTION
    # ========================================

    connection = (
        get_database_connection()
    )

    purchase_gap_detail = None

    try:

        print(
            "\nFetching Phase 2 TPP "
            "customer summary "
            "(one row per customer)..."
        )

        customer_summary_base = (
            fetch_dataframe(
                connection=connection,
                sql_filename=(
                    "analytics/"
                    "tpp_customer_frequency_summary.sql"
                ),
            )
        )

        if EXPORT_GAP_DETAIL:

            print(
                "\nFetching optional "
                "purchase-gap detail..."
            )

            purchase_gap_detail = (
                fetch_dataframe(
                    connection=connection,
                    sql_filename=(
                        "analytics/"
                        "tpp_purchase_gap_detail.sql"
                    ),
                )
            )

    finally:

        connection.close()

        print(
            "\nDatabase connection closed."
        )


    # ========================================
    # SQL RESULT INFORMATION
    # ========================================

    print(
        "\nCustomer summary rows fetched: "
        f"{len(customer_summary_base):,}"
    )

    print(
        "Customer summary columns fetched: "
        f"{len(customer_summary_base.columns):,}"
    )


    # ========================================
    # APPLY BUSINESS RULES
    # ========================================

    customer_summary = (
        enrich_customer_frequency_summary(
            customer_summary_dataframe=(
                customer_summary_base
            ),
        )
    )


    # ========================================
    # OUTPUT DIRECTORY
    # ========================================

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


    # ========================================
    # SAVE CUSTOMER SUMMARY
    # ========================================

    summary_output_path = (
        OUTPUT_DIRECTORY
        / "tpp_customer_frequency_summary.csv"
    )

    customer_summary.to_csv(
        summary_output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\nFiles created:"
    )

    print(
        summary_output_path
    )


    # ========================================
    # OPTIONAL GAP DETAIL
    # ========================================

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

        print(
            gap_output_path
        )


    # ========================================
    # BUILD TELEGRAM MESSAGES
    # ========================================

    telegram_messages = (
        build_province_alert_messages(
            customer_summary=(
                customer_summary
            ),
            max_rows_per_message=(
                MAX_ROWS_PER_MESSAGE
            ),
            minimum_probability=(
                MINIMUM_ALERT_PROBABILITY
            ),
        )
    )


    print(
        "\nTelegram messages generated "
        "before routing: "
        f"{len(telegram_messages):,}"
    )


    # ========================================
    # ROUTE TPP MESSAGES
    # ========================================
    #
    # Example:
    #
    # Phnom Penh + TPP
    # -> R1
    # -> Group -1004389670593
    # -> Topic 9
    #
    # Kandal + TPP
    # -> R1
    # -> Group -1004389670593
    # -> Topic 5
    #
    # Provinces not configured yet
    # will be skipped safely.
    # ========================================

    routed_messages = []

    skipped_messages = []

    for message in telegram_messages:

        province = str(
            message["province"]
        ).strip()

        try:

            route = (
                get_telegram_route(
                    product="TPP",
                    province=province,
                )
            )

        except KeyError:

            print(
                "Skipping Telegram route: "
                f"TPP / {province}"
            )

            skipped_messages.append(
                message
            )

            continue


        # Make a copy so the original
        # message dictionary stays untouched.
        routed_message = (
            message.copy()
        )


        # Add routing information.
        routed_message["region"] = (
            route["region"]
        )

        routed_message["chat_id"] = (
            route["chat_id"]
        )

        routed_message[
            "message_thread_id"
        ] = route[
            "message_thread_id"
        ]


        routed_messages.append(
            routed_message
        )


    # ========================================
    # ALERT STATISTICS
    # ========================================

    active_alerts = customer_summary[
        (
            customer_summary[
                "customer_status"
            ]
            == "Active"
        )
        &
        (
            customer_summary[
                "purchase_probability_percent"
            ]
            >= MINIMUM_ALERT_PROBABILITY
        )
    ]


    inactive_alerts = customer_summary[
        (
            customer_summary[
                "customer_status"
            ]
            == "Inactive"
        )
        &
        (
            customer_summary[
                "purchase_probability_percent"
            ]
            >= MINIMUM_ALERT_PROBABILITY
        )
    ]


    print(
        "\nTelegram alert results:"
    )

    print(
        "Active due customers: "
        f"{len(active_alerts):,}"
    )

    print(
        "Inactive re-engagement customers: "
        f"{len(inactive_alerts):,}"
    )

    print(
        "Messages generated: "
        f"{len(telegram_messages):,}"
    )

    print(
        "Messages with valid Telegram routes: "
        f"{len(routed_messages):,}"
    )

    print(
        "Messages skipped because "
        "route is not configured: "
        f"{len(skipped_messages):,}"
    )


    # ========================================
    # SHOW ROUTING INFORMATION
    # ========================================

    print(
        "\nTelegram routing:"
    )

    for message in routed_messages:

        print(
            f"TPP | "
            f"{message['province']} "
            f"-> {message['region']} "
            f"| Chat: "
            f"{message['chat_id']} "
            f"| Topic: "
            f"{message['message_thread_id']}"
        )


    # ========================================
    # CREATE TELEGRAM PREVIEW
    # ========================================

    preview_output_path = (
        OUTPUT_DIRECTORY
        / "telegram_alert_preview.txt"
    )


    if routed_messages:

        preview_text = (
            "\n\n"
            + ("=" * 60)
            + "\n\n"
        ).join(
            str(
                message[
                    "plain_text"
                ]
            )
            for message
            in routed_messages
        )

    else:

        preview_text = (
            "No Telegram messages "
            "have valid routes."
        )


    preview_output_path.write_text(
        preview_text,
        encoding="utf-8",
    )


    print(
        "\nTelegram preview created:"
    )

    print(
        preview_output_path
    )


    # ========================================
    # TEST MODE
    # ========================================

    if not SEND_TELEGRAM:

        print(
            "\nTelegram sending is disabled."
        )

        print(
            "Review "
            "telegram_alert_preview.txt."
        )

        print(
            "When ready, change:"
        )

        print(
            "SEND_TELEGRAM = True"
        )

        return


    # ========================================
    # NOTHING TO SEND
    # ========================================

    if not routed_messages:

        print(
            "\nNo routed Telegram messages "
            "to send."
        )

        return


    # ========================================
    # GET BOT TOKEN
    # ========================================


    # ========================================
    # SEND REAL TELEGRAM ALERTS
    # ========================================

    print(
        "\nSending real Telegram alerts..."
    )


    sent_messages = (
        send_province_alert_messages(
            messages=routed_messages,
        )
    )


    # ========================================
    # COMPLETED
    # ========================================

    print(
        "\nTelegram alert process completed."
    )

    print(
        "Messages sent successfully: "
        f"{len(sent_messages):,}"
    )