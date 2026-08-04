"""Apply CRT customer-frequency business rules."""

from zoneinfo import ZoneInfo

import pandas as pd


# ============================================
# CUSTOMER TYPE RULES
# ============================================

def classify_crt_customer(
    valid_purchase_events: object,
    average_gap_days: object,
) -> str:
    """
    Classify a CRT customer based on
    their average gap between purchase events.
    """

    if pd.isna(valid_purchase_events):
        return "Unknown"

    purchase_events = int(
        valid_purchase_events
    )

    # ========================================
    # ONE-TIME CUSTOMER
    # ========================================

    if purchase_events == 1:
        return "One-Time Customer"

    # ========================================
    # MULTIPLE PURCHASE EVENTS
    # ========================================

    if pd.isna(average_gap_days):
        return "Insufficient Purchase History"

    gap = float(
        average_gap_days
    )

    if 1.0 <= gap <= 10.5:
        return "Weekly Customer"

    if 10.5 < gap <= 21.5:
        return "Bi-Weekly Customer"

    if 21.5 < gap <= 45.5:
        return "Monthly Customer"

    if 45.5 < gap <= 75.0:
        return "Bi-Monthly Customer"

    if gap > 75.0:
        return "Occasional Customer"

    return "Insufficient Purchase History"


# ============================================
# CUSTOMER STATUS RULES
# ============================================

def calculate_customer_status(
    customer_category: object,
    days_since_last_purchase: object,
) -> str:
    """
    Determine whether a CRT customer
    is Active or Inactive.

    Rules remain the same as TPP.
    """

    if pd.isna(days_since_last_purchase):
        return "Unknown"

    category = str(
        customer_category
    ).strip()

    days = int(
        days_since_last_purchase
    )

    # ========================================
    # WEEKLY
    # ========================================

    if category == "Weekly Customer":

        if days > 21:
            return "Inactive"

        return "Active"

    # ========================================
    # BI-WEEKLY
    # ========================================

    if category == "Bi-Weekly Customer":

        if days > 45:
            return "Inactive"

        return "Active"

    # ========================================
    # MONTHLY
    # ========================================

    if category == "Monthly Customer":

        if days > 60:
            return "Inactive"

        return "Active"

    # ========================================
    # BI-MONTHLY
    # ========================================

    if category == "Bi-Monthly Customer":

        if days > 100:
            return "Inactive"

        return "Active"

    # ========================================
    # NOT EVALUATED
    # ========================================

    if category in [
        "One-Time Customer",
        "Occasional Customer",
        "Insufficient Purchase History",
    ]:
        return "Not Evaluated"

    return "Unknown"


# ============================================
# PURCHASE PROBABILITY
# ============================================

def calculate_purchase_probability(
    customer_category: object,
    days_since_last_purchase: object,
) -> float | None:
    """
    Calculate CRT purchase-cycle probability.

    Same calculation currently used for TPP.

    Result is capped between 0 and 100.
    """

    if pd.isna(days_since_last_purchase):
        return None

    category = str(
        customer_category
    ).strip()

    days = float(
        days_since_last_purchase
    )

    # Prevent negative percentages
    # if a future date somehow appears.
    days = max(
        days,
        0,
    )

    # ========================================
    # WEEKLY
    # ========================================

    if category == "Weekly Customer":

        probability = (
            days
            / 10.5
            * 100
        )

    # ========================================
    # BI-WEEKLY
    # ========================================

    elif category == "Bi-Weekly Customer":

        probability = (
            days
            / 21.5
            * 100
        )

    # ========================================
    # MONTHLY
    # ========================================

    elif category == "Monthly Customer":

        probability = (
            days
            / 45.5
            * 100
        )

    # ========================================
    # BI-MONTHLY
    # ========================================

    elif category == "Bi-Monthly Customer":

        probability = (
            days
            / 75.5
            * 100
        )

    # ========================================
    # NO PROBABILITY
    # ========================================

    else:
        return None

    # ========================================
    # CAP BETWEEN 0 AND 100
    # ========================================

    probability = max(
        0,
        min(
            probability,
            100,
        ),
    )

    return round(
        probability,
        2,
    )


# ============================================
# ENRICH CRT CUSTOMER SUMMARY
# ============================================

def enrich_crt_customer_frequency_summary(
    customer_summary_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add CRT business-rule columns:

    - days_since_last_purchase
    - customer_category
    - customer_status
    - purchase_probability_percent
    """

    required_columns = [
        "customer_id",
        "customer_name",
        "province",
        "valid_purchase_events",
        "first_purchase_date",
        "latest_purchase_date",
        "total_del_qty",
        "number_of_gaps",
        "total_gap_days",
        "average_gap_days",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column
        not in customer_summary_dataframe.columns
    ]

    if missing_columns:

        raise KeyError(
            "CRT customer summary is missing "
            f"these columns:\n"
            f"{missing_columns}\n\n"
            "Available columns:\n"
            f"{list(customer_summary_dataframe.columns)}"
        )

    data = (
        customer_summary_dataframe[
            required_columns
        ]
        .copy()
    )

    # ========================================
    # CLEAN CUSTOMER TEXT
    # ========================================

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

    data["province"] = (
        data["province"]
        .astype("string")
        .str.strip()
    )

    # ========================================
    # DATE TYPES
    # ========================================

    data[
        "first_purchase_date"
    ] = pd.to_datetime(
        data[
            "first_purchase_date"
        ],
        errors="coerce",
    )

    data[
        "latest_purchase_date"
    ] = pd.to_datetime(
        data[
            "latest_purchase_date"
        ],
        errors="coerce",
    )

    # ========================================
    # NUMERIC TYPES
    # ========================================

    numeric_columns = [
        "valid_purchase_events",
        "total_del_qty",
        "number_of_gaps",
        "total_gap_days",
        "average_gap_days",
    ]

    for column in numeric_columns:

        data[column] = pd.to_numeric(
            data[column],
            errors="coerce",
        )

    # ========================================
    # CAMBODIA CURRENT DATE
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

    # ========================================
    # DAYS SINCE LAST PURCHASE EVENT
    # ========================================

    data[
        "days_since_last_purchase"
    ] = (
        today
        - data[
            "latest_purchase_date"
        ]
    ).dt.days

    # ========================================
    # CUSTOMER TYPE
    # ========================================

    data[
        "customer_category"
    ] = data.apply(
        lambda row: classify_crt_customer(
            valid_purchase_events=row[
                "valid_purchase_events"
            ],
            average_gap_days=row[
                "average_gap_days"
            ],
        ),
        axis=1,
    )

    # ========================================
    # CUSTOMER STATUS
    # ========================================

    data[
        "customer_status"
    ] = data.apply(
        lambda row: calculate_customer_status(
            customer_category=row[
                "customer_category"
            ],
            days_since_last_purchase=row[
                "days_since_last_purchase"
            ],
        ),
        axis=1,
    )

    # ========================================
    # PURCHASE PROBABILITY
    # ========================================

    data[
        "purchase_probability_percent"
    ] = data.apply(
        lambda row: calculate_purchase_probability(
            customer_category=row[
                "customer_category"
            ],
            days_since_last_purchase=row[
                "days_since_last_purchase"
            ],
        ),
        axis=1,
    )

    # ========================================
    # FINAL COLUMN ORDER
    # ========================================

    final_columns = [
        "customer_id",
        "customer_name",
        "province",

        "valid_purchase_events",

        "first_purchase_date",
        "latest_purchase_date",

        "days_since_last_purchase",

        "total_del_qty",

        "number_of_gaps",
        "total_gap_days",
        "average_gap_days",

        "customer_category",
        "customer_status",
        "purchase_probability_percent",
    ]

    return (
        data[
            final_columns
        ]
        .copy()
    )