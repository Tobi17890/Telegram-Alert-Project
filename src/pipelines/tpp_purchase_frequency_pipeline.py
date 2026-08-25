"""Run the TPP customer-frequency Telegram pipeline."""

from src.analytics.tpp_purchase_frequency import (
    enrich_customer_frequency_summary,
)

from src.config import (
    PROJECT_ROOT,
)

from src.database import (
    get_database_connection,
)

from src.notifications.telegram_message import (
    build_province_alert_messages,
    prepare_alert_customers,
)

from src.notifications.telegram_routes import (
    get_telegram_route,
)

from src.notifications.telegram_service import (
    send_province_alert_packages,
)

from src.query_service import (
    fetch_dataframe,
)

from src.tracking.alert_history import (
    update_daily_alert_history,
)

from src.tracking.google_sheets_tracking import (
    REASON_REMINDER_DAYS,
    apply_reason_reminder_policy,
    build_tracking_dataset,
    sync_tracking_dataset,
)

from src.reports.province_alert_excel import (
    export_province_alert_excels,
)


# ============================================
# OUTPUT SETTINGS
# ============================================

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "outputs"
    / "tpp_purchase_frequency"
)


# ============================================
# SHARED ALERT HISTORY
# ============================================
#
# CRT and TPP use the SAME history file.
# Product column separates them.
#
# ============================================

ALERT_HISTORY_PATH = (
    PROJECT_ROOT
    / "outputs"
    / "alert_tracking"
    / "alert_history.csv"
)


# ============================================
# PIPELINE SETTINGS
# ============================================

EXPORT_GAP_DETAIL = False


# IMPORTANT:
# Keep False while checking Excel previews.
SEND_TELEGRAM = False


# Write to Google Sheets only after preview validation.
WRITE_GOOGLE_SHEETS = True


# Same alert rule as CRT.
MINIMUM_ALERT_PROBABILITY = 60.0


# Maximum customers shown
# in one Telegram message.
MAX_ROWS_PER_MESSAGE = 15


# ============================================
# MAIN TPP PIPELINE
# ============================================

def tpp_run_purchase_frequency_pipeline() -> None:
    """
    Run the complete TPP customer alert pipeline.

    Flow:

    SQL
        ↓
    TPP customer summary
        ↓
    Customer type / status / probability
        ↓
    Internal alert history
        ↓
    Today's qualified alert customers
        ↓
    Telegram messages
        ↓
    Telegram routing
        ↓
    Verify Telegram = Excel
        ↓
    Telegram TXT preview
        ↓
    Province Excel previews
        ↓
    Optional Telegram send
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
            "\nFetching TPP customer summary "
            "(one row per customer)..."
        )


        # ====================================
        # TPP CUSTOMER SUMMARY
        # ====================================

        customer_summary_base = (
            fetch_dataframe(
                connection=connection,
                sql_filename=(
                    "analytics/"
                    "tpp_customer_frequency_summary.sql"
                ),
            )
        )


        # ====================================
        # OPTIONAL GAP DETAIL
        # ====================================

        if EXPORT_GAP_DETAIL:

            print(
                "\nFetching optional "
                "TPP purchase-gap detail..."
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
        "\nTPP customer summary rows fetched: "
        f"{len(customer_summary_base):,}"
    )


    print(
        "TPP customer summary columns fetched: "
        f"{len(customer_summary_base.columns):,}"
    )


    print(
        "\nColumns returned by TPP SQL:"
    )


    for column in (
        customer_summary_base.columns
    ):

        print(
            f" - {column}"
        )


    # ========================================
    # APPLY TPP BUSINESS RULES
    # ========================================

    customer_summary = (
        enrich_customer_frequency_summary(
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
    # UPDATE INTERNAL ALERT HISTORY
    # ========================================

    print(
        "\nUpdating TPP alert tracking history..."
    )


    today_tracking = (
        update_daily_alert_history(
            customer_summary=(
                customer_summary
            ),
            product="TPP",
            minimum_probability=(
                MINIMUM_ALERT_PROBABILITY
            ),
            history_path=(
                ALERT_HISTORY_PATH
            ),
        )
    )


    print(
        "\nTPP tracking rows generated today: "
        f"{len(today_tracking):,}"
    )


    # ========================================
    # PREPARE EXACT TPP ALERT CUSTOMERS
    # ========================================
    #
    # This is the SAME population used for:
    #
    # 1. Telegram
    # 2. Province Excel
    #
    # Rules come from prepare_alert_customers():
    #
    # - Active or Inactive
    # - Probability >= 60%
    # - Customer IDs starting 14 / 15 excluded
    #
    # Sorting:
    #
    # Active
    #   Weekly
    #   Bi-Weekly
    #   Monthly
    #   Bi-Monthly
    #
    # Inactive
    #   Weekly
    #   Bi-Weekly
    #   Monthly
    #   Bi-Monthly
    #
    # Within same Type:
    # Days Since Last Purchase DESC
    #
    # ========================================

    alert_customers = (
        prepare_alert_customers(
            customer_summary=(
                customer_summary
            ),
            minimum_probability=(
                MINIMUM_ALERT_PROBABILITY
            ),
        )
    )


    print(
        "\nTPP business-rule alert candidates: "
        f"{len(alert_customers):,}"
    )


    # ========================================
    # EXPORT TODAY'S INTERNAL TRACKING PREVIEW
    # ========================================

    tracking_preview_path = (
        OUTPUT_DIRECTORY
        / "tpp_alert_tracking_preview.csv"
    )


    today_tracking.to_csv(
        tracking_preview_path,
        index=False,
        encoding="utf-8-sig",
    )


    print(
        "\nTPP tracking preview created:"
    )


    print(
        tracking_preview_path
    )


    # ========================================
    # EXPORT TPP CUSTOMER SUMMARY
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
        "\nTPP customer summary created:"
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
            / "tpp_purchase_gap_detail.csv"
        )


        purchase_gap_detail.to_csv(
            gap_output_path,
            index=False,
            encoding="utf-8-sig",
        )


        print(
            "\nTPP purchase gap detail created:"
        )


        print(
            gap_output_path
        )


    # ========================================
    # CUSTOMER STATISTICS
    # ========================================

    weekly_customers = (
        customer_summary[
            customer_summary[
                "customer_category"
            ]
            == "Weekly Customer"
        ]
    )


    biweekly_customers = (
        customer_summary[
            customer_summary[
                "customer_category"
            ]
            == "Bi-Weekly Customer"
        ]
    )


    monthly_customers = (
        customer_summary[
            customer_summary[
                "customer_category"
            ]
            == "Monthly Customer"
        ]
    )


    bimonthly_customers = (
        customer_summary[
            customer_summary[
                "customer_category"
            ]
            == "Bi-Monthly Customer"
        ]
    )


    occasional_customers = (
        customer_summary[
            customer_summary[
                "customer_category"
            ]
            == "Occasional Customer"
        ]
    )


    one_time_customers = (
        customer_summary[
            customer_summary[
                "customer_category"
            ]
            == "One-Time Customer"
        ]
    )


    print(
        "\nTPP customer-frequency results:"
    )


    print(
        "Total TPP customers: "
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
    # APPLY ONLINE REASON / 12-DAY REMINDER
    # ========================================
    # This is a post-qualification tracking rule only.
    # Existing TPP business rules remain unchanged.

    if WRITE_GOOGLE_SHEETS:

        follow_up_region_map = {}

        follow_up_provinces = set(
            alert_customers["province"]
            .astype("string")
            .str.strip()
            .dropna()
            .tolist()
        )

        if "province" in today_tracking.columns:
            follow_up_provinces.update(
                today_tracking["province"]
                .astype("string")
                .str.strip()
                .dropna()
                .tolist()
            )

        for province in sorted(
            follow_up_provinces
        ):
            province_name = str(province).strip()
            try:
                route = get_telegram_route(
                    product="TPP",
                    province=province_name,
                )
            except KeyError:
                continue

            follow_up_region_map[province_name] = str(
                route["region"]
            ).strip()

        alert_customers, reminder_summary = (
            apply_reason_reminder_policy(
                alert_customers=alert_customers,
                today_tracking=today_tracking,
                product="TPP",
                province_regions=follow_up_region_map,
                reminder_days=REASON_REMINDER_DAYS,
            )
        )

        print(
            "\nTPP 12-day follow-up policy:"
        )
        print(
            "Business-rule candidates: "
            f"{reminder_summary['business_candidates']:,}"
        )
        print(
            "Action Taken suppressed: "
            f"{reminder_summary['action_taken_suppressed']:,}"
        )
        print(
            "Reason waiting (< 12 days): "
            f"{reminder_summary['reason_wait_suppressed']:,}"
        )
        print(
            "Initial alerts: "
            f"{reminder_summary['initial_alerts']:,}"
        )
        print(
            "Unanswered alerts re-shown: "
            f"{reminder_summary['unanswered_realerts']:,}"
        )
        print(
            "12-day reminders: "
            f"{reminder_summary['12_day_reminders']:,}"
        )
        print(
            "Final Telegram customers: "
            f"{reminder_summary['final_alerts']:,}"
        )

    else:
        print(
            "\nWRITE_GOOGLE_SHEETS = False - "
            "Reason reminder policy was not applied."
        )


    # ========================================
    # CURRENT ALERT STATISTICS
    # ========================================

    active_alerts = (
        alert_customers[
            alert_customers[
                "customer_status"
            ]
            == "Active"
        ]
    )


    inactive_alerts = (
        alert_customers[
            alert_customers[
                "customer_status"
            ]
            == "Inactive"
        ]
    )


    print(
        "\nToday's TPP alert customers:"
    )


    print(
        "Active due TPP customers: "
        f"{len(active_alerts):,}"
    )


    print(
        "Inactive re-engagement TPP customers: "
        f"{len(inactive_alerts):,}"
    )


    # ========================================
    # BUILD TPP TELEGRAM MESSAGES
    # ========================================

    print(
        "\nPreparing TPP Telegram alerts..."
    )


    telegram_messages = (
        build_province_alert_messages(
            customer_summary=(
                alert_customers
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
        "TPP Telegram messages "
        "generated before routing: "
        f"{len(telegram_messages):,}"
    )


    # ========================================
    # ROUTE TPP TELEGRAM MESSAGES
    # ========================================

    routed_messages = []

    skipped_messages = []


    for message in telegram_messages:

        province = str(
            message[
                "province"
            ]
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
                "Skipping TPP Telegram route: "
                f"TPP / {province}"
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
        # ADD ROUTING INFORMATION
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
    # ROUTING RESULTS
    # ========================================

    print(
        "\nTPP Telegram alert results:"
    )


    print(
        "Messages generated: "
        f"{len(telegram_messages):,}"
    )


    print(
        "Messages routed: "
        f"{len(routed_messages):,}"
    )


    print(
        "Messages skipped: "
        f"{len(skipped_messages):,}"
    )


    # ========================================
    # GET ROUTED PROVINCES
    # ========================================
    #
    # IMPORTANT:
    # This happens AFTER routed_messages
    # is populated.
    #
    # ========================================

    routed_provinces = {
        str(
            message[
                "province"
            ]
        ).strip()

        for message
        in routed_messages
    }


    print(
        "\nTPP routed provinces:"
    )


    if routed_provinces:

        for province in sorted(
            routed_provinces
        ):

            print(
                f" - {province}"
            )


    else:

        print(
            "No provinces have valid routes."
        )


    # ========================================
    # SHOW TPP ROUTING
    # ========================================

    print(
        "\nTPP Telegram routing:"
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
    # VERIFY TELEGRAM = EXCEL
    # ========================================

    print(
        "\nVerifying TPP Telegram "
        "vs Excel customer counts..."
    )


    telegram_counts = {}


    for message in routed_messages:

        province = str(
            message[
                "province"
            ]
        ).strip()


        telegram_counts[
            province
        ] = (
            telegram_counts.get(
                province,
                0,
            )
            +
            int(
                message[
                    "customer_count"
                ]
            )
        )


    for province in sorted(
        routed_provinces
    ):

        excel_customer_count = len(
            alert_customers[
                alert_customers[
                    "province"
                ]
                == province
            ]
        )


        telegram_customer_count = (
            telegram_counts.get(
                province,
                0,
            )
        )


        print(
            f"{province}: "
            f"Telegram="
            f"{telegram_customer_count:,} "
            f"| Excel="
            f"{excel_customer_count:,}"
        )


        if (
            excel_customer_count
            != telegram_customer_count
        ):

            raise ValueError(
                "\nTPP Telegram / Excel "
                "customer count mismatch!\n"
                f"Province: {province}\n"
                f"Telegram: "
                f"{telegram_customer_count}\n"
                f"Excel: "
                f"{excel_customer_count}"
            )


    # ========================================
    # BUILD GOOGLE SHEETS TRACKING DATASET
    # ========================================
    # Uses the SAME routed alert_customers population.
    # No CRT/TPP business rule is repeated here.

    province_regions = {}

    for message in routed_messages:
        province = str(message["province"]).strip()
        region = str(message["region"]).strip()

        existing_region = province_regions.get(province)
        if existing_region is not None and existing_region != region:
            raise ValueError(
                f"TPP province {province} routed to multiple regions: "
                f"{existing_region} / {region}"
            )

        province_regions[province] = region

    google_tracking_dataset = build_tracking_dataset(
        alert_customers=alert_customers,
        today_tracking=today_tracking,
        product="TPP",
        province_regions=province_regions,
        included_provinces=routed_provinces,
    )

    google_tracking_preview_path = (
        OUTPUT_DIRECTORY
        / "tpp_google_sheets_tracking_preview.csv"
    )

    google_tracking_dataset.to_csv(
        google_tracking_preview_path,
        index=False,
        encoding="utf-8-sig",
    )

    print(
        "\nTPP Google Sheets tracking preview created:"
    )
    print(google_tracking_preview_path)

    # ========================================
    # VERIFY TELEGRAM = GOOGLE TRACKER
    # ========================================

    print(
        "\nVerifying TPP Telegram vs Google tracking customer counts..."
    )

    for province in sorted(routed_provinces):
        telegram_customer_count = telegram_counts.get(province, 0)
        tracking_customer_count = len(
            google_tracking_dataset[
                google_tracking_dataset["Province"] == province
            ]
        )

        print(
            f"{province}: Telegram={telegram_customer_count:,} "
            f"| Google Tracker={tracking_customer_count:,}"
        )

        if telegram_customer_count != tracking_customer_count:
            raise ValueError(
                f"TPP Telegram / Google tracking count mismatch for "
                f"{province}: Telegram={telegram_customer_count}, "
                f"Google={tracking_customer_count}"
            )

    # ========================================
    # OPTIONAL REAL GOOGLE SHEETS SYNC
    # ========================================

    follow_up_links = {}

    if WRITE_GOOGLE_SHEETS:
        print(
            "\nWriting TPP routed alerts to Google Sheets..."
        )

        follow_up_links = sync_tracking_dataset(
            tracking_dataset=google_tracking_dataset,
        )

        missing_links = sorted(
            routed_provinces - set(follow_up_links)
        )

        if missing_links:
            if SEND_TELEGRAM:
                raise ValueError(
                    "Telegram sending cancelled because some provinces do not "
                    "have a configured regional Google follow-up workbook: "
                    + ", ".join(missing_links)
                )

            print(
                "\nRegional Google follow-up is not configured yet for: "
                + ", ".join(missing_links)
            )
            print(
                "This is allowed while SEND_TELEGRAM = False. "
                "Only configured regions were written."
            )

        print("\nTPP online follow-up links:")
        for province in sorted(follow_up_links):
            print(f"{province}: {follow_up_links[province]}")

    else:
        print(
            "\nWRITE_GOOGLE_SHEETS = False - Google Sheets was not modified."
        )


    # ========================================
    # CREATE TPP TELEGRAM TXT PREVIEW
    # ========================================

    preview_output_path = (
        OUTPUT_DIRECTORY
        / "tpp_telegram_alert_preview.txt"
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
            "No TPP Telegram messages "
            "have valid routes."
        )


    preview_output_path.write_text(
        preview_text,
        encoding="utf-8",
    )


    print(
        "\nTPP Telegram preview created:"
    )


    print(
        preview_output_path
    )


    # ========================================
    # PROVINCE EXCEL PREVIEW DIRECTORY
    # ========================================

    excel_preview_directory = (
        OUTPUT_DIRECTORY
        / "province_excel_preview"
    )


    print(
        "\nCreating TPP province "
        "Excel previews..."
    )


    # ========================================
    # GENERATE TPP PROVINCE EXCEL FILES
    # ========================================

    created_excel_files = (
        export_province_alert_excels(
            alert_customers=(
                alert_customers
            ),
            today_tracking=(
                today_tracking
            ),
            product="TPP",
            output_directory=(
                excel_preview_directory
            ),
            included_provinces=(
                routed_provinces
            ),
        )
    )


    # ========================================
    # PRINT EXCEL RESULTS
    # ========================================

    print(
        "\nTPP province Excel previews:"
    )


    if created_excel_files:

        for (
            province,
            file_path,
        ) in created_excel_files.items():

            customer_count = len(
                alert_customers[
                    alert_customers[
                        "province"
                    ]
                    == province
                ]
            )


            print(
                f"\n{province}: "
                f"{customer_count:,} customers"
            )


            print(
                f"  {file_path}"
            )


    else:

        print(
            "No TPP province Excel "
            "files were created."
        )


    # ========================================
    # FINAL EXCEL SUMMARY
    # ========================================

    print(
        "\nTotal TPP province Excel files: "
        f"{len(created_excel_files):,}"
    )


    print(
        "Excel preview folder:"
    )


    print(
        excel_preview_directory
    )


    # ========================================
    # TEST / PREVIEW MODE
    # ========================================

    if not SEND_TELEGRAM:

        print(
            "\n"
            + "=" * 60
        )


        print(
            "TPP PREVIEW MODE"
        )


        print(
            "=" * 60
        )


        print(
            "\nTelegram sending is disabled."
        )


        print(
            "\nReview Telegram preview:"
        )


        print(
            preview_output_path
        )


        print(
            "\nReview Google Sheets tracking preview:"
        )

        print(
            google_tracking_preview_path
        )


        print(
            "\nReview province Excel files:"
        )


        print(
            excel_preview_directory
        )


        print(
            "\nWhen everything is correct, "
            "change:"
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
            "\nNo routed TPP Telegram "
            "messages to send."
        )


        return


    # ========================================
    # ONLINE TRACKER REQUIRED FOR REAL SEND
    # ========================================

    if not WRITE_GOOGLE_SHEETS:
        raise RuntimeError(
            "TPP Telegram sending requires WRITE_GOOGLE_SHEETS = True "
            "so every province receives one online follow-up link."
        )


    # ========================================
    # SEND REAL TPP TELEGRAM ALERTS
    # ========================================

    print(
        "\nSending real TPP "
        "Telegram alerts..."
    )


    sent_results = (
        send_province_alert_packages(
            messages=(
                routed_messages
            ),
            follow_up_links=(
                follow_up_links
            ),
            product="TPP",
        )
    )


    # ========================================
    # COMPLETED
    # ========================================

    print(
        "\n"
        + "=" * 60
    )


    print(
        "TPP TELEGRAM SENDING COMPLETED"
    )


    print(
        "=" * 60
    )


    message_count = sum(
        1
        for result
        in sent_results
        if result["type"]
        == "message"
    )


    follow_up_link_count = sum(
        1
        for result
        in sent_results
        if result["type"]
        == "follow_up_link"
    )


    print(
        "\nTPP alert messages sent: "
        f"{message_count:,}"
    )


    print(
        "TPP online follow-up links sent: "
        f"{follow_up_link_count:,}"
    )


# ============================================
# DIRECT RUN
# ============================================

if __name__ == "__main__":

    tpp_run_purchase_frequency_pipeline()