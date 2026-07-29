"""Create compact Telegram customer alerts grouped by province."""

import math
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd


TELEGRAM_MESSAGE_LIMIT = 4096
DEFAULT_MINIMUM_PROBABILITY = 60.0

CATEGORY_DISPLAY_NAMES = {
    "Weekly Customer": "Weekly",
    "Bi-Weekly Customer": "BiWkly",
    "Monthly Customer": "Monthly",
    "Bi-Monthly Customer": "BiMthly",
    "One-Time Customer": "OneTime",
    "Occasional Customer": "Occasnl",
}

SECTION_DISPLAY_NAMES = {
    "Active": "Customer Info - Due / Active",
    "Inactive": "Customer Info - Re-engagement",
}

STATUS_SORT_ORDER = {
    "Active": 0,
    "Inactive": 1,
}

COLUMN_WIDTHS = {
    "ID": 8,
    "Name": 14,
    "Last": 8,
    "Type": 7,
    "Status": 8,
    "Prob": 4,
}


def shorten_text(
    value: object,
    maximum_width: int,
) -> str:
    """Convert a value to text and shorten long values."""

    if pd.isna(value):
        text = ""
    else:
        text = str(value).strip()

    if len(text) <= maximum_width:
        return text

    if maximum_width <= 3:
        return text[:maximum_width]

    return (
        text[: maximum_width - 3]
        + "..."
    )


def format_last_purchase(
    days_since_last_purchase: object,
) -> str:
    """Format days since last purchase as compact text."""

    if pd.isna(days_since_last_purchase):
        return "N/A"

    days = int(days_since_last_purchase)

    if days < 0:
        return "Future"

    return f"{days}d-ago"


def format_customer_type(
    customer_category: object,
) -> str:
    """Shorten the customer type for the Telegram table."""

    if pd.isna(customer_category):
        return "Unknown"

    category = str(
        customer_category
    ).strip()

    return CATEGORY_DISPLAY_NAMES.get(
        category,
        category,
    )


def format_probability(
    probability: object,
) -> str:
    """Format the displayed probability as a whole percent."""

    if pd.isna(probability):
        return "N/A"

    percentage = max(
        0,
        min(
            int(round(float(probability))),
            100,
        ),
    )

    return f"{percentage}%"


def _format_cell(
    value: object,
    width: int,
) -> str:
    """Shorten and left-align one table cell."""

    text = shorten_text(
        value=value,
        maximum_width=width,
    )

    return f" {text:<{width}} "


def _build_border(
    left: str,
    middle: str,
    right: str,
) -> str:
    """Build one horizontal box-table border."""

    segments = [
        "─" * (width + 2)
        for width in COLUMN_WIDTHS.values()
    ]

    return (
        left
        + middle.join(segments)
        + right
    )


def _build_table(
    rows: pd.DataFrame,
) -> list[str]:
    """Build a bordered fixed-width table."""

    top_border = _build_border(
        "┌",
        "┬",
        "┐",
    )

    middle_border = _build_border(
        "├",
        "┼",
        "┤",
    )

    bottom_border = _build_border(
        "└",
        "┴",
        "┘",
    )

    header_values = list(
        COLUMN_WIDTHS.keys()
    )

    header_line = (
        "│"
        + "│".join(
            _format_cell(
                header,
                COLUMN_WIDTHS[header],
            )
            for header in header_values
        )
        + "│"
    )

    lines = [
        top_border,
        header_line,
        middle_border,
    ]

    for row_position, (_, row) in enumerate(
        rows.iterrows()
    ):
        values = {
            "ID": row["customer_id"],
            "Name": row["customer_name"],
            "Last": format_last_purchase(
                row["days_since_last_purchase"]
            ),
            "Type": format_customer_type(
                row["customer_category"]
            ),
            "Status": row["customer_status"],
            "Prob": format_probability(
                row[
                    "purchase_probability_percent"
                ]
            ),
        }

        row_line = (
            "│"
            + "│".join(
                _format_cell(
                    values[column],
                    width,
                )
                for column, width
                in COLUMN_WIDTHS.items()
            )
            + "│"
        )

        lines.append(
            row_line
        )

        is_last_row = (
            row_position
            == len(rows) - 1
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


def build_province_alert_messages(
    customer_summary: pd.DataFrame,
    max_rows_per_message: int = 15,
    minimum_probability: float = (
        DEFAULT_MINIMUM_PROBABILITY
    ),
) -> list[dict[str, object]]:
    """
    Build compact purchase alerts grouped by province and status.

    Included customers:
    - purchase_probability_percent >= minimum_probability
    - customer_status is Active or Inactive

    Active customers and inactive re-engagement customers are
    placed into separate message sections.
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
        for column in required_columns
        if column not in customer_summary.columns
    ]

    if missing_columns:
        raise KeyError(
            "The Telegram message requires these missing columns:\n"
            f"{missing_columns}\n\n"
            "Available columns:\n"
            f"{list(customer_summary.columns)}"
        )

    if max_rows_per_message <= 0:
        raise ValueError(
            "max_rows_per_message must be greater than zero."
        )

    if not 0 <= minimum_probability <= 100:
        raise ValueError(
            "minimum_probability must be between 0 and 100."
        )

    data = customer_summary[
        required_columns
    ].copy()

    data["purchase_probability_percent"] = pd.to_numeric(
        data["purchase_probability_percent"],
        errors="coerce",
    )

    data = data[
        data["customer_status"].isin(
            [
                "Active",
                "Inactive",
            ]
        )
        & (
            data["purchase_probability_percent"]
            >= minimum_probability
        )
    ].copy()

    if data.empty:
        return []

    data["province"] = (
        data["province"]
        .astype("string")
        .str.strip()
        .fillna("Unknown Province")
    )

    data.loc[
        data["province"] == "",
        "province",
    ] = "Unknown Province"

    data["customer_id"] = (
        data["customer_id"]
        .astype("string")
        .str.strip()
    )

    data["customer_name"] = (
        data["customer_name"]
        .astype("string")
        .str.strip()
    )

    data["status_sort_order"] = (
        data["customer_status"]
        .map(STATUS_SORT_ORDER)
        .fillna(99)
    )

    data = data.sort_values(
        [
            "province",
            "status_sort_order",
            "purchase_probability_percent",
            "days_since_last_purchase",
            "customer_name",
        ],
        ascending=[
            True,
            True,
            False,
            False,
            True,
        ],
        na_position="last",
    ).reset_index(drop=True)

    today_text = pd.Timestamp.now(
        tz=ZoneInfo("Asia/Phnom_Penh")
    ).strftime("%d %b %Y")

    messages: list[dict[str, object]] = []

    for province, province_data in data.groupby(
        "province",
        sort=True,
        dropna=False,
    ):
        for status in [
            "Active",
            "Inactive",
        ]:
            section_data = province_data[
                province_data["customer_status"]
                == status
            ].reset_index(drop=True)

            total_customers = len(
                section_data
            )

            if total_customers == 0:
                continue

            total_parts = math.ceil(
                total_customers
                / max_rows_per_message
            )

            for part_index in range(
                total_parts
            ):
                start_index = (
                    part_index
                    * max_rows_per_message
                )

                end_index = (
                    start_index
                    + max_rows_per_message
                )

                part_data = section_data.iloc[
                    start_index:end_index
                ]

                part_number = (
                    part_index + 1
                )

                lines = [
                    "CMI Depot Purchase Prediction Alert",
                    "",
                    f"Date: {today_text}",
                    f"Region: {province}",
                    (
                        "Alert Rule: "
                        f"Probability >= "
                        f"{minimum_probability:g}%"
                    ),
                ]

                if total_parts > 1:
                    lines.append(
                        f"Part: "
                        f"{part_number}/{total_parts}"
                    )

                lines.extend(
                    [
                        "",
                        SECTION_DISPLAY_NAMES[status],
                        *_build_table(
                            part_data
                        ),
                    ]
                )

                plain_text = "\n".join(
                    lines
                )

                telegram_html = (
                    f"<pre>{escape(plain_text)}</pre>"
                )

                if len(telegram_html) > TELEGRAM_MESSAGE_LIMIT:
                    raise ValueError(
                        "A Telegram message exceeded "
                        "4,096 characters. Reduce "
                        "max_rows_per_message."
                    )

                messages.append(
                    {
                        "province": str(province),
                        "section": status,
                        "part_number": part_number,
                        "total_parts": total_parts,
                        "customer_count": len(
                            part_data
                        ),
                        "plain_text": plain_text,
                        "telegram_html": telegram_html,
                    }
                )

    return messages
