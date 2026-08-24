"""Create compact Telegram customer alerts grouped by province."""

import math
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd


# ============================================
# SETTINGS
# ============================================

TELEGRAM_MESSAGE_LIMIT = 4096

DEFAULT_MINIMUM_PROBABILITY = 60.0


# ============================================
# DISPLAY NAMES
# ============================================

CATEGORY_DISPLAY_NAMES = {
    "Weekly Customer": "Weekly",
    "Bi-Weekly Customer": "BiWkly",
    "Monthly Customer": "Monthly",
    "Bi-Monthly Customer": "BiMthly",
    "One-Time Customer": "OneTime",
    "Occasional Customer": "Occasnl",
}


SECTION_DISPLAY_NAMES = {
    "Active": (
        "Customer Info - Due / Active"
    ),
    "Inactive": (
        "Customer Info - Re-engagement"
    ),
}


# ============================================
# SORTING RULES
# ============================================
#
# FINAL ORDER:
#
# Active
#   Weekly
#   Bi-Weekly
#   Monthly
#   Bi-Monthly
#   Occasional
#   One-Time
#
# Inactive
#   Weekly
#   Bi-Weekly
#   Monthly
#   Bi-Monthly
#   Occasional
#   One-Time
#
# Within the SAME category:
#
# days_since_last_purchase DESC
#
# Example:
#
# Weekly 20d
# Weekly 15d
# Weekly 10d
#
# then
#
# BiWkly 40d
# BiWkly 30d
#
# ============================================

STATUS_SORT_ORDER = {
    "Active": 0,
    "Inactive": 1,
}


CATEGORY_SORT_ORDER = {
    "Weekly Customer": 0,
    "Bi-Weekly Customer": 1,
    "Monthly Customer": 2,
    "Bi-Monthly Customer": 3,
    "Occasional Customer": 4,
    "One-Time Customer": 5,
}


# ============================================
# TELEGRAM TABLE WIDTHS
# ============================================

COLUMN_WIDTHS = {
    "ID": 8,
    "Name": 14,
    "Last": 8,
    "Type": 7,
    "Status": 8,
    "Prob": 4,
}


# ============================================
# TEXT FORMATTERS
# ============================================

def shorten_text(
    value: object,
    maximum_width: int,
) -> str:
    """Convert a value to text and shorten it."""

    if pd.isna(value):

        text = ""

    else:

        text = str(
            value
        ).strip()


    if len(text) <= maximum_width:

        return text


    if maximum_width <= 3:

        return text[
            :maximum_width
        ]


    return (
        text[
            : maximum_width - 3
        ]
        + "..."
    )


# ============================================
# LAST PURCHASE DISPLAY
# ============================================

def format_last_purchase(
    days_since_last_purchase: object,
) -> str:
    """
    Display days since last purchase.

    Example:
    7 -> 7d-ago
    """

    if pd.isna(
        days_since_last_purchase
    ):

        return "N/A"


    days = int(
        days_since_last_purchase
    )


    if days < 0:

        return "Future"


    return f"{days}d-ago"


# ============================================
# CUSTOMER TYPE DISPLAY
# ============================================

def format_customer_type(
    customer_category: object,
) -> str:
    """Shorten customer type."""

    if pd.isna(
        customer_category
    ):

        return "Unknown"


    category = str(
        customer_category
    ).strip()


    return CATEGORY_DISPLAY_NAMES.get(
        category,
        category,
    )


# ============================================
# PROBABILITY DISPLAY
# ============================================

def format_probability(
    probability: object,
) -> str:
    """Display probability as whole percentage."""

    if pd.isna(
        probability
    ):

        return "N/A"


    percentage = int(
        round(
            float(
                probability
            )
        )
    )


    percentage = max(
        0,
        min(
            percentage,
            100,
        ),
    )


    return f"{percentage}%"


# ============================================
# TELEGRAM TABLE CELL
# ============================================

def _format_cell(
    value: object,
    width: int,
) -> str:
    """Shorten and left-align a table cell."""

    text = shorten_text(
        value=value,
        maximum_width=width,
    )


    return (
        f" {text:<{width}} "
    )


# ============================================
# TELEGRAM TABLE BORDER
# ============================================

def _build_border(
    left: str,
    middle: str,
    right: str,
) -> str:
    """Build horizontal border."""

    segments = [
        "─" * (
            width + 2
        )
        for width
        in COLUMN_WIDTHS.values()
    ]


    return (
        left
        + middle.join(
            segments
        )
        + right
    )


# ============================================
# TELEGRAM TABLE
# ============================================

def _build_table(
    rows: pd.DataFrame,
) -> list[str]:
    """Build bordered Telegram table."""

    top_border = (
        _build_border(
            "┌",
            "┬",
            "┐",
        )
    )


    middle_border = (
        _build_border(
            "├",
            "┼",
            "┤",
        )
    )


    bottom_border = (
        _build_border(
            "└",
            "┴",
            "┘",
        )
    )


    header_values = list(
        COLUMN_WIDTHS.keys()
    )


    header_line = (
        "│"
        + "│".join(
            _format_cell(
                header,
                COLUMN_WIDTHS[
                    header
                ],
            )
            for header
            in header_values
        )
        + "│"
    )


    lines = [
        top_border,
        header_line,
        middle_border,
    ]


    for (
        row_position,
        (_, row),
    ) in enumerate(
        rows.iterrows()
    ):

        values = {

            "ID": (
                row[
                    "customer_id"
                ]
            ),

            "Name": (
                row[
                    "customer_name"
                ]
            ),

            "Last": (
                format_last_purchase(
                    row[
                        "days_since_last_purchase"
                    ]
                )
            ),

            "Type": (
                format_customer_type(
                    row[
                        "customer_category"
                    ]
                )
            ),

            "Status": (
                row[
                    "customer_status"
                ]
            ),

            "Prob": (
                format_probability(
                    row[
                        "purchase_probability_percent"
                    ]
                )
            ),
        }


        row_line = (
            "│"
            + "│".join(

                _format_cell(
                    values[
                        column
                    ],
                    width,
                )

                for (
                    column,
                    width,
                )

                in COLUMN_WIDTHS.items()

            )
            + "│"
        )


        lines.append(
            row_line
        )


        is_last_row = (
            row_position
            ==
            len(rows) - 1
        )


        if is_last_row:

            lines.append(
                bottom_border
            )

        else:

            lines.append(
                middle_border
            )


    return lines


# ============================================
# SHARED ALERT CUSTOMER PREPARATION
# ============================================

def prepare_alert_customers(
    customer_summary: pd.DataFrame,
    minimum_probability: float = (
        DEFAULT_MINIMUM_PROBABILITY
    ),
) -> pd.DataFrame:
    """
    Prepare the EXACT customer population
    used by Telegram and Province Excel.

    ALERT RULE:

    1. Active or Inactive only
    2. Probability >= threshold
    3. Exclude Customer IDs starting
       with 14 or 15

    SORTING:

    1. Province
    2. Active before Inactive
    3. Weekly
    4. Bi-Weekly
    5. Monthly
    6. Bi-Monthly
    7. Occasional
    8. One-Time
    9. Within same type:
       days_since_last_purchase DESC
    10. Customer name as final tie breaker
    """

    required_columns = [
        "customer_id",
        "customer_name",
        "province",
        "days_since_last_purchase",
        "customer_category",
        "customer_status",
        "purchase_probability_percent",
    ]


    missing_columns = [

        column

        for column
        in required_columns

        if column
        not in customer_summary.columns

    ]


    if missing_columns:

        raise KeyError(
            "Alert preparation requires "
            "these missing columns:\n"
            f"{missing_columns}\n\n"
            "Available columns:\n"
            f"{list(customer_summary.columns)}"
        )


    if not (
        0
        <= minimum_probability
        <= 100
    ):

        raise ValueError(
            "minimum_probability must "
            "be between 0 and 100."
        )


    # ========================================
    # COPY ALL ORIGINAL COLUMNS
    # ========================================
    #
    # We keep all columns because Excel
    # also needs latest_purchase_date.
    #
    # ========================================

    data = (
        customer_summary.copy()
    )


    # ========================================
    # CLEAN PROBABILITY
    # ========================================

    data[
        "purchase_probability_percent"
    ] = pd.to_numeric(
        data[
            "purchase_probability_percent"
        ],
        errors="coerce",
    )


    # ========================================
    # CLEAN PROVINCE
    # ========================================

    data[
        "province"
    ] = (
        data[
            "province"
        ]
        .astype(
            "string"
        )
        .str.strip()
        .fillna(
            "Unknown Province"
        )
    )


    data.loc[
        data[
            "province"
        ]
        == "",
        "province",
    ] = (
        "Unknown Province"
    )


    # ========================================
    # CLEAN CUSTOMER ID
    # ========================================

    data[
        "customer_id"
    ] = (
        data[
            "customer_id"
        ]
        .astype(
            "string"
        )
        .str.strip()
    )


    # ========================================
    # CLEAN CUSTOMER NAME
    # ========================================

    data[
        "customer_name"
    ] = (
        data[
            "customer_name"
        ]
        .astype(
            "string"
        )
        .str.strip()
    )


    # ========================================
    # REMOVE CUSTOMER ID 14xxxx / 15xxxx
    # ========================================

    data = data[
        ~data[
            "customer_id"
        ].str.startswith(
            (
                "14",
                "15",
            ),
            na=False,
        )
    ].copy()


    # ========================================
    # TELEGRAM ALERT FILTER
    # ========================================

    data = data[
        (
            data[
                "customer_status"
            ].isin(
                [
                    "Active",
                    "Inactive",
                ]
            )
        )
        &
        (
            data[
                "purchase_probability_percent"
            ]
            >= minimum_probability
        )
    ].copy()


    if data.empty:

        return data


    # ========================================
    # CREATE STATUS SORT KEY
    # ========================================

    data[
        "status_sort_order"
    ] = (
        data[
            "customer_status"
        ]
        .map(
            STATUS_SORT_ORDER
        )
        .fillna(
            99
        )
    )


    # ========================================
    # CREATE CATEGORY SORT KEY
    # ========================================

    data[
        "category_sort_order"
    ] = (
        data[
            "customer_category"
        ]
        .map(
            CATEGORY_SORT_ORDER
        )
        .fillna(
            99
        )
    )


    # ========================================
    # FINAL SORTING
    # ========================================
    #
    # IMPORTANT:
    #
    # Probability is NOT used for sorting.
    #
    # ========================================

    data = (
        data
        .sort_values(
            [
                "province",
                "status_sort_order",
                "category_sort_order",
                "days_since_last_purchase",
                "customer_name",
            ],
            ascending=[
                True,
                True,
                True,
                False,
                True,
            ],
            na_position="last",
            kind="stable",
        )
        .reset_index(
            drop=True
        )
    )


    return data


# ============================================
# BUILD PROVINCE TELEGRAM ALERTS
# ============================================

def build_province_alert_messages(
    customer_summary: pd.DataFrame,
    max_rows_per_message: int = 15,
    minimum_probability: float = (
        DEFAULT_MINIMUM_PROBABILITY
    ),
) -> list[
    dict[
        str,
        object,
    ]
]:
    """
    Build Telegram alerts by province.

    Active and Inactive are separate sections.

    Within each section:

    Weekly
        ↓
    Bi-Weekly
        ↓
    Monthly
        ↓
    Bi-Monthly
        ↓
    Occasional
        ↓
    One-Time

    Within each type:

    highest days since last purchase first.
    """


    # ========================================
    # VALIDATE ROW LIMIT
    # ========================================

    if max_rows_per_message <= 0:

        raise ValueError(
            "max_rows_per_message must "
            "be greater than zero."
        )


    # ========================================
    # PREPARE EXACT ALERT POPULATION
    # ========================================

    data = (
        prepare_alert_customers(
            customer_summary=(
                customer_summary
            ),
            minimum_probability=(
                minimum_probability
            ),
        )
    )


    if data.empty:

        return []


    # ========================================
    # TODAY TEXT
    # ========================================

    today_text = (
        pd.Timestamp.now(
            tz=ZoneInfo(
                "Asia/Phnom_Penh"
            )
        )
        .strftime(
            "%d %b %Y"
        )
    )


    messages: list[
        dict[
            str,
            object,
        ]
    ] = []


    # ========================================
    # GROUP BY PROVINCE
    # ========================================

    for (
        province,
        province_data,
    ) in data.groupby(
        "province",
        sort=True,
        dropna=False,
    ):


        # ====================================
        # STATUS ORDER IS MANUAL
        # ====================================
        #
        # Active FIRST
        # Inactive SECOND
        #
        # ====================================

        for status in [
            "Active",
            "Inactive",
        ]:


            section_data = (
                province_data[
                    province_data[
                        "customer_status"
                    ]
                    == status
                ]
                .copy()
            )


            # =================================
            # RE-APPLY SECTION SORT
            # =================================
            #
            # This makes the rule explicit
            # and protects the order even
            # after groupby/filtering.
            #
            # =================================

            section_data = (
                section_data
                .sort_values(
                    [
                        "category_sort_order",
                        "days_since_last_purchase",
                        "customer_name",
                    ],
                    ascending=[
                        True,
                        False,
                        True,
                    ],
                    na_position="last",
                    kind="stable",
                )
                .reset_index(
                    drop=True
                )
            )


            total_customers = (
                len(
                    section_data
                )
            )


            if total_customers == 0:

                continue


            # =================================
            # NUMBER OF MESSAGE PARTS
            # =================================

            total_parts = (
                math.ceil(
                    total_customers
                    /
                    max_rows_per_message
                )
            )


            # =================================
            # SPLIT INTO TELEGRAM PARTS
            # =================================

            for part_index in range(
                total_parts
            ):


                start_index = (
                    part_index
                    *
                    max_rows_per_message
                )


                end_index = (
                    start_index
                    +
                    max_rows_per_message
                )


                part_data = (
                    section_data.iloc[
                        start_index:
                        end_index
                    ]
                )


                part_number = (
                    part_index
                    + 1
                )


                # =================================
                # MESSAGE HEADER
                # =================================

                lines = [
                    (
                        "CMI Depot Purchase "
                        "Prediction Alert"
                    ),
                    "",
                    (
                        f"Date: "
                        f"{today_text}"
                    ),
                    (
                        f"Region: "
                        f"{province}"
                    ),
                    (
                        "Alert Rule: "
                        f"Probability >= "
                        f"{minimum_probability:g}%"
                    ),
                ]


                if total_parts > 1:

                    lines.append(
                        (
                            f"Part: "
                            f"{part_number}/"
                            f"{total_parts}"
                        )
                    )


                # =================================
                # SECTION + TABLE
                # =================================

                lines.extend(
                    [
                        "",
                        SECTION_DISPLAY_NAMES[
                            status
                        ],
                        *_build_table(
                            part_data
                        ),
                    ]
                )


                # =================================
                # PLAIN TEXT
                # =================================

                plain_text = (
                    "\n".join(
                        lines
                    )
                )


                # =================================
                # TELEGRAM HTML
                # =================================

                telegram_html = (
                    "<pre>"
                    + escape(
                        plain_text
                    )
                    + "</pre>"
                )


                # =================================
                # TELEGRAM LIMIT
                # =================================

                if (
                    len(
                        telegram_html
                    )
                    >
                    TELEGRAM_MESSAGE_LIMIT
                ):

                    raise ValueError(
                        "A Telegram message "
                        "exceeded 4,096 characters. "
                        "Reduce "
                        "max_rows_per_message."
                    )


                # =================================
                # SAVE MESSAGE
                # =================================

                messages.append(
                    {

                        "province": (
                            str(
                                province
                            )
                        ),

                        "section": (
                            status
                        ),

                        "part_number": (
                            part_number
                        ),

                        "total_parts": (
                            total_parts
                        ),

                        "customer_count": (
                            len(
                                part_data
                            )
                        ),

                        "plain_text": (
                            plain_text
                        ),

                        "telegram_html": (
                            telegram_html
                        ),
                    }
                )


    return messages