"""Run the CRT customer-frequency Telegram pipeline."""

from src.analytics.crt_purchase_frequency import (
    enrich_crt_customer_frequency_summary,
)

from src.config import (
    PROJECT_ROOT,
)

from src.database import (
    get_database_connection,
)

from src.notifications.telegram_message import (
    build_province_alert_messages,
)

from src.notifications.telegram_routes import (
    get_telegram_route,
)

from src.notifications.telegram_service import (
    send_province_alert_messages,
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
    / "crt_purchase_frequency"
)


# ============================================
# PIPELINE SETTINGS
# ============================================

# Optional CRT purchase-event gap detail.
EXPORT_GAP_DETAIL = False


# Keep False during testing.
# Change to True only after checking preview.
SEND_TELEGRAM = True


# Same Telegram alert threshold
# currently used for TPP.
MINIMUM_ALERT_PROBABILITY = 60.0


# Maximum customers shown
# in one Telegram message.
MAX_ROWS_PER_MESSAGE = 15


# ============================================
# CRT PIPELINE
# ============================================

def run_crt_purchase_frequency_pipeline() -> None:
    """
    Run the CRT purchase-frequency pipeline.

    CRT logic:

    1. Fetch one SQL summary row per customer.
    2. SQL has already converted consecutive
       delivery dates into CRT purchase events.
    3. Apply customer type.
    4. Calculate days since last purchase.
    5. Calculate Active / Inactive status.
    6. Calculate purchase probability.
    7. Export CSV.
    8. Build Telegram alerts.
    9. Route CRT alerts to CRT Telegram topics.
    10. Optionally send using personal Telegram account.
    """

    # ========================================
    # DATABASE CONNECTION
    # ========================================

    connection = (
        get_database_connection()
    )

    purchase_gap_detail = None

    try:

        print(
            "\nFetching CRT customer summary "
            "(one row per customer)..."
        )

        # ====================================
        # CRT CUSTOMER SUMMARY
        # ====================================

        customer_summary_base = (
            fetch_dataframe(
                connection=connection,
                sql_filename=(
                    "analytics/"
                    "crt_customer_frequency_summary.sql"
                ),
            )
        )


        # ====================================
        # OPTIONAL CRT GAP DETAIL
        # ====================================

        if EXPORT_GAP_DETAIL:

            print(
                "\nFetching optional "
                "CRT purchase-gap detail..."
            )

            purchase_gap_detail = (
                fetch_dataframe(
                    connection=connection,
                    sql_filename=(
                        "analytics/"
                        "crt_purchase_gap_detail.sql"
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
        "\nCRT customer summary rows fetched: "
        f"{len(customer_summary_base):,}"
    )

    print(
        "CRT customer summary columns fetched: "
        f"{len(customer_summary_base.columns):,}"
    )

    print(
        "\nColumns returned by CRT SQL:"
    )

    for column in (
        customer_summary_base.columns
    ):

        print(
            f" - {column}"
        )


    # ========================================
    # APPLY CRT BUSINESS RULES
    # ========================================

    customer_summary = (
        enrich_crt_customer_frequency_summary(
            customer_summary_dataframe=(
                customer_summary_base
            ),
        )
    )


    # ========================================
    # CREATE OUTPUT DIRECTORY
    # ========================================

    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )


    # ========================================
    # EXPORT CRT SUMMARY
    # ========================================

    summary_output_path = (
        OUTPUT_DIRECTORY
        / "crt_customer_frequency_summary.csv"
    )

    customer_summary.to_csv(
        summary_output_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\nCRT files created:"
    )

    print(
        summary_output_path
    )


    # ========================================
    # OPTIONAL GAP DETAIL EXPORT
    # ========================================

    if purchase_gap_detail is not None:

        gap_output_path = (
            OUTPUT_DIRECTORY
            / "crt_purchase_gap_detail.csv"
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
    # CUSTOMER STATISTICS
    # ========================================

    weekly_customers = customer_summary[
        customer_summary[
            "customer_category"
        ]
        == "Weekly Customer"
    ]

    biweekly_customers = customer_summary[
        customer_summary[
            "customer_category"
        ]
        == "Bi-Weekly Customer"
    ]

    monthly_customers = customer_summary[
        customer_summary[
            "customer_category"
        ]
        == "Monthly Customer"
    ]

    bimonthly_customers = customer_summary[
        customer_summary[
            "customer_category"
        ]
        == "Bi-Monthly Customer"
    ]

    occasional_customers = customer_summary[
        customer_summary[
            "customer_category"
        ]
        == "Occasional Customer"
    ]

    one_time_customers = customer_summary[
        customer_summary[
            "customer_category"
        ]
        == "One-Time Customer"
    ]


    print(
        "\nCRT customer-frequency results:"
    )

    print(
        "Total CRT customers: "
        f"{len(customer_summary):,}"
    )

    print(
        "Weekly: "
        f"{len(weekly_customers):,}"
    )

    print(
        "Bi-Weekly: "
        f"{len(biweekly_customers):,}"
    )

    print(
        "Monthly: "
        f"{len(monthly_customers):,}"
    )

    print(
        "Bi-Monthly: "
        f"{len(bimonthly_customers):,}"
    )

    print(
        "Occasional: "
        f"{len(occasional_customers):,}"
    )

    print(
        "One-Time: "
        f"{len(one_time_customers):,}"
    )


    # ========================================
    # BUILD CRT TELEGRAM MESSAGES
    # ========================================

    print(
        "\nPreparing CRT Telegram alerts..."
    )

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
        "CRT Telegram messages "
        "generated before routing: "
        f"{len(telegram_messages):,}"
    )


    # ========================================
    # CRT TELEGRAM ROUTING
    # ========================================
    #
    # IMPORTANT:
    #
    # product="CRT"
    #
    # Example:
    #
    # CRT + Kandal
    # -> R1
    # -> R1-CRT / Kandal
    #
    # CRT + Phnom Penh
    # -> R1
    # -> R1-CRT / PP
    #
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
                    product="CRT",
                    province=province,
                )
            )

        except KeyError:

            print(
                "Skipping CRT Telegram route: "
                f"CRT / {province}"
            )

            skipped_messages.append(
                message
            )

            continue


        # ====================================
        # COPY MESSAGE
        # ====================================

        routed_message = (
            message.copy()
        )


        # ====================================
        # ADD TELEGRAM DESTINATION
        # ====================================

        routed_message[
            "region"
        ] = route[
            "region"
        ]

        routed_message[
            "chat_id"
        ] = route[
            "chat_id"
        ]

        routed_message[
            "message_thread_id"
        ] = route[
            "message_thread_id"
        ]


        routed_messages.append(
            routed_message
        )


    # ========================================
    # ALERT CUSTOMER COUNTS
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
        "\nCRT Telegram alert results:"
    )

    print(
        "Active due CRT customers: "
        f"{len(active_alerts):,}"
    )

    print(
        "Inactive CRT re-engagement customers: "
        f"{len(inactive_alerts):,}"
    )

    print(
        "CRT messages generated: "
        f"{len(telegram_messages):,}"
    )

    print(
        "CRT messages routed: "
        f"{len(routed_messages):,}"
    )

    print(
        "CRT messages skipped: "
        f"{len(skipped_messages):,}"
    )


    # ========================================
    # PRINT ROUTING
    # ========================================

    print(
        "\nCRT Telegram routing:"
    )

    for message in routed_messages:

        print(
            f"CRT | "
            f"{message['province']} "
            f"-> {message['region']} "
            f"| Chat: "
            f"{message['chat_id']} "
            f"| Topic: "
            f"{message['message_thread_id']}"
        )


    # ========================================
    # CREATE CRT TELEGRAM PREVIEW
    # ========================================

    preview_output_path = (
        OUTPUT_DIRECTORY
        / "crt_telegram_alert_preview.txt"
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
            "No CRT Telegram messages "
            "have valid routes."
        )


    preview_output_path.write_text(
        preview_text,
        encoding="utf-8",
    )


    print(
        "\nCRT Telegram preview created:"
    )

    print(
        preview_output_path
    )


    # ========================================
    # TEST MODE
    # ========================================

    if not SEND_TELEGRAM:

        print(
            "\nCRT Telegram sending is disabled."
        )

        print(
            "Review:"
        )

        print(
            preview_output_path
        )

        print(
            "\nWhen ready, change:"
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
            "\nNo routed CRT Telegram "
            "messages to send."
        )

        return


    # ========================================
    # SEND CRT TELEGRAM ALERTS
    # ========================================

    print(
        "\nSending real CRT Telegram alerts..."
    )


    sent_messages = (
        send_province_alert_messages(
            messages=routed_messages,
        )
    )


    # ========================================
    # COMPLETE
    # ========================================

    print(
        "\nCRT Telegram alert "
        "process completed."
    )

    print(
        "CRT messages sent successfully: "
        f"{len(sent_messages):,}"
    )