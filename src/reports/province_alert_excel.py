"""Create clean province Excel files for regional follow-up."""

import re
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from src.notifications.telegram_message import (
    format_customer_type,
    format_last_purchase,
    format_probability,
)


# ============================================
# SAFE FILE NAME
# ============================================

def make_safe_filename(
    value: object,
) -> str:
    """Remove characters that cannot be used in filenames."""

    text = str(
        value
    ).strip()

    text = re.sub(
        r'[<>:"/\\|?*]+',
        "-",
        text,
    )

    return text


# ============================================
# EXPORT PROVINCE EXCEL FILES
# ============================================

def export_province_alert_excels(
    alert_customers: pd.DataFrame,
    today_tracking: pd.DataFrame,
    product: str,
    output_directory: Path,
    included_provinces: set[str] | None = None,
) -> dict[str, Path]:
    """
    Generate one clean Excel file per province.

    IMPORTANT:
    Only customers from alert_customers are exported.
    Therefore Excel contains exactly today's
    Telegram-qualified customers.

    Regional columns:
    - Alert Date
    - Customer ID
    - Customer Name
    - Last
    - Last Purchase Date
    - Type
    - Status
    - Prob
    - Activity
    - Reason
    """

    if alert_customers.empty:
        return {}


    required_columns = [
        "customer_id",
        "customer_name",
        "province",
        "latest_purchase_date",
        "days_since_last_purchase",
        "customer_category",
        "customer_status",
        "purchase_probability_percent",
    ]


    missing_columns = [
        column
        for column in required_columns
        if column not in alert_customers.columns
    ]


    if missing_columns:
        raise KeyError(
            "Province Excel requires these "
            "missing columns:\n"
            f"{missing_columns}"
        )


    # ========================================
    # TODAY - CAMBODIA
    # ========================================

    today = (
        pd.Timestamp.now(
            tz=ZoneInfo(
                "Asia/Phnom_Penh"
            )
        )
        .normalize()
        .tz_localize(None)
    )


    product = (
        str(product)
        .strip()
        .upper()
    )


    # ========================================
    # COPY TODAY'S TELEGRAM CUSTOMERS
    # ========================================

    data = alert_customers.copy()


    # ========================================
    # GET ACTIVITY FROM INTERNAL HISTORY
    # ========================================

    if (
        today_tracking is not None
        and
        not today_tracking.empty
    ):

        activity_lookup = (
            today_tracking[
                [
                    "customer_id",
                    "activity",
                ]
            ]
            .copy()
        )


        activity_lookup[
            "customer_id"
        ] = (
            activity_lookup[
                "customer_id"
            ]
            .astype("string")
            .str.strip()
        )


        activity_lookup = (
            activity_lookup
            .drop_duplicates(
                subset=[
                    "customer_id",
                ],
                keep="last",
            )
        )


        data = data.merge(
            activity_lookup,
            on="customer_id",
            how="left",
        )


    else:

        data[
            "activity"
        ] = "No Action"


    data[
        "activity"
    ] = (
        data[
            "activity"
        ]
        .fillna(
            "No Action"
        )
    )


    # ========================================
    # PREPARE BUSINESS-FRIENDLY COLUMNS
    # ========================================

    data[
        "Alert Date"
    ] = today


    data[
        "Customer ID"
    ] = (
        data[
            "customer_id"
        ]
    )


    data[
        "Customer Name"
    ] = (
        data[
            "customer_name"
        ]
    )


    data[
        "Last"
    ] = (
        data[
            "days_since_last_purchase"
        ]
        .apply(
            format_last_purchase
        )
    )


    data[
        "Last Purchase Date"
    ] = pd.to_datetime(
        data[
            "latest_purchase_date"
        ],
        errors="coerce",
    )


    data[
        "Type"
    ] = (
        data[
            "customer_category"
        ]
        .apply(
            format_customer_type
        )
    )


    data[
        "Status"
    ] = (
        data[
            "customer_status"
        ]
    )


    data[
        "Prob"
    ] = (
        data[
            "purchase_probability_percent"
        ]
        .apply(
            format_probability
        )
    )


    data[
        "Activity"
    ] = (
        data[
            "activity"
        ]
    )


    # Manual column for region.
    data[
        "Reason"
    ] = ""


    # ========================================
    # ONLY COLUMNS REGION NEEDS
    # ========================================

    regional_columns = [
        "Alert Date",
        "Customer ID",
        "Customer Name",
        "Last",
        "Last Purchase Date",
        "Type",
        "Status",
        "Prob",
        "Activity",
        "Reason",
    ]


    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )


    created_files: dict[
        str,
        Path,
    ] = {}


    # ========================================
    # CREATE ONE EXCEL PER PROVINCE
    # ========================================

    for province, province_data in (
        data.groupby(
            "province",
            sort=True,
            dropna=False,
        )
    ):

        province = str(
            province
        ).strip()


        # Only create Excel files for provinces
        # that have valid Telegram routes.
        if (
            included_provinces is not None
            and
            province not in included_provinces
        ):

            continue


        export_data = (
            province_data[
                regional_columns
            ]
            .copy()
            .reset_index(
                drop=True
            )
        )


        safe_province = (
            make_safe_filename(
                province
            )
        )


        date_filename = (
            today.strftime(
                "%Y-%m-%d"
            )
        )


        output_path = (
            output_directory
            / (
                f"{product}_"
                f"{safe_province}_"
                f"Alert_"
                f"{date_filename}.xlsx"
            )
        )


        # ====================================
        # WRITE + FORMAT EXCEL
        # ====================================

        with pd.ExcelWriter(
            output_path,
            engine="xlsxwriter",
            datetime_format="dd-mmm-yyyy",
        ) as writer:

            export_data.to_excel(
                writer,
                sheet_name="Alert",
                index=False,
            )


            workbook = writer.book

            worksheet = (
                writer.sheets[
                    "Alert"
                ]
            )


            # =================================
            # EXCEL TABLE
            # =================================

            last_row = len(
                export_data
            )

            last_column = (
                len(
                    regional_columns
                )
                - 1
            )


            worksheet.add_table(
                0,
                0,
                last_row,
                last_column,
                {
                    "name": (
                        "ProvinceAlertTable"
                    ),
                    "style": (
                        "Table Style Medium 9"
                    ),
                    "columns": [
                        {
                            "header": column
                        }
                        for column
                        in regional_columns
                    ],
                },
            )


            # =================================
            # FREEZE HEADER
            # =================================

            worksheet.freeze_panes(
                1,
                0,
            )


            # =================================
            # ZOOM
            # =================================

            worksheet.set_zoom(
                90
            )


            # =================================
            # ROW HEIGHT
            # =================================

            worksheet.set_default_row(
                20
            )


            # =================================
            # DATE FORMAT
            # =================================

            date_format = (
                workbook.add_format(
                    {
                        "num_format": (
                            "dd-mmm-yyyy"
                        ),
                    }
                )
            )


            # =================================
            # COLUMN WIDTHS
            # =================================

            worksheet.set_column(
                "A:A",
                14,
                date_format,
            )

            worksheet.set_column(
                "B:B",
                15,
            )

            worksheet.set_column(
                "C:C",
                30,
            )

            worksheet.set_column(
                "D:D",
                11,
            )

            worksheet.set_column(
                "E:E",
                19,
                date_format,
            )

            worksheet.set_column(
                "F:F",
                13,
            )

            worksheet.set_column(
                "G:G",
                12,
            )

            worksheet.set_column(
                "H:H",
                10,
            )

            worksheet.set_column(
                "I:I",
                16,
            )

            worksheet.set_column(
                "J:J",
                38,
            )


            # =================================
            # HIGHLIGHT REASON COLUMN
            # =================================

            reason_format = (
                workbook.add_format(
                    {
                        "bg_color": (
                            "#97ACFF"
                        ),
                    }
                )
            )


            if last_row >= 1:

                worksheet.set_column(
                    "J:J",
                    38,
                    reason_format,
                )


        created_files[
            province
        ] = output_path


    return created_files