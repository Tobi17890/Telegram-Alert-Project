"""Create Telegram customer-alert messages grouped by province."""

import math
from html import escape
from zoneinfo import ZoneInfo

import pandas as pd


CATEGORY_DISPLAY_NAMES = {
    "Weekly Customer": "Weekly",
    "Bi-Weekly Customer": "Bi-Weekly",
    "Monthly Customer": "Monthly",
    "Bi-Monthly Customer": "Bi-Monthly",
    "Inactive Customer": "Inactive",
    "Insufficient Purchase History": "Insufficient",
}


def shorten_text(
    value: object,
    maximum_width: int,
) -> str:
    """
    Convert a value to text and shorten long values.
    """

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
    """
    Format days since last purchase as readable text.
    """

    if pd.isna(days_since_last_purchase):
        return "N/A"

    days = int(days_since_last_purchase)

    if days < 0:
        return "Future date"

    if days == 0:
        return "Today"

    if days == 1:
        return "1 day ago"

    return f"{days} days ago"


def format_customer_type(
    customer_category: object,
) -> str:
    """
    Shorten the internal customer-category description.
    """

    if pd.isna(customer_category):
        return "Unknown"

    category = str(
        customer_category
    ).strip()

    return CATEGORY_DISPLAY_NAMES.get(
        category,
        category,
    )


def build_province_alert_messages(
    customer_summary: pd.DataFrame,
    max_rows_per_message: int = 15,
) -> list[dict[str, object]]:
    """
    Build one or more Telegram messages for every province.

    No customers are filtered here. Every record in
    customer_summary is included.
    """

    required_columns = [
        "customer_id",
        "customer_name",
        "province",
        "days_since_last_purchase",
        "customer_category",
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

    data = customer_summary[
        required_columns
    ].copy()

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

    data = data.sort_values(
        [
            "province",
            "customer_name",
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
        province_data = (
            province_data
            .reset_index(drop=True)
        )

        total_customers = len(
            province_data
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

            part_data = province_data.iloc[
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
            ]

            if total_parts > 1:
                lines.append(
                    f"Part: {part_number}/{total_parts}"
                )

            lines.extend(
                [
                    "",
                    (
                        f"{'Customer ID':<12} | "
                        f"{'Customer Name':<22} | "
                        f"{'Last Purchase':<14} | "
                        f"{'Customer Type':<12}"
                    ),
                    (
                        f"{'-' * 12}-+-"
                        f"{'-' * 22}-+-"
                        f"{'-' * 14}-+-"
                        f"{'-' * 12}"
                    ),
                ]
            )

            for _, row in part_data.iterrows():
                customer_id = shorten_text(
                    row["customer_id"],
                    12,
                )

                customer_name = shorten_text(
                    row["customer_name"],
                    22,
                )

                last_purchase = shorten_text(
                    format_last_purchase(
                        row[
                            "days_since_last_purchase"
                        ]
                    ),
                    14,
                )

                customer_type = shorten_text(
                    format_customer_type(
                        row["customer_category"]
                    ),
                    12,
                )

                lines.append(
                    f"{customer_id:<12} | "
                    f"{customer_name:<22} | "
                    f"{last_purchase:<14} | "
                    f"{customer_type:<12}"
                )

            plain_text = "\n".join(
                lines
            )

            if len(plain_text) > 4096:
                raise ValueError(
                    "A Telegram message exceeded "
                    "4,096 characters. Reduce "
                    "max_rows_per_message."
                )

            telegram_html = (
                f"<pre>{escape(plain_text)}</pre>"
            )

            messages.append(
                {
                    "province": str(province),
                    "part_number": part_number,
                    "total_parts": total_parts,
                    "plain_text": plain_text,
                    "telegram_html": telegram_html,
                }
            )

    return messages