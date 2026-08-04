"""Enrich SQL customer summaries with type, status, and probability."""

import pandas as pd
from zoneinfo import ZoneInfo


def enrich_customer_frequency_summary(
    customer_summary_dataframe: pd.DataFrame,
) -> pd.DataFrame:
    """
    Add business classifications to the Phase 2 SQL summary.

    Expected SQL columns:
        customer_id
        customer_name
        province
        valid_purchase_days
        first_purchase_date
        latest_purchase_date
        total_positive_quantity
        number_of_gaps
        total_gap_days
        average_gap_days

    SQL Server has already handled:
    - Valid positive purchase filtering
    - Same-day purchase grouping
    - Previous purchase date
    - Gap days
    - Customer-level aggregation

    Python handles:
    - Cambodia current date
    - Days since last purchase
    - Customer category
    - Customer status
    - Purchase probability percentage
    """

    required_columns = [
        "customer_id",
        "customer_name",
        "province",
        "valid_purchase_days",
        "first_purchase_date",
        "latest_purchase_date",
        "total_positive_quantity",
        "number_of_gaps",
        "total_gap_days",
        "average_gap_days",
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in customer_summary_dataframe.columns
    ]

    if missing_columns:
        raise KeyError(
            "The following required Phase 2 summary columns "
            "were not found:\n"
            f"{missing_columns}\n\n"
            "Available columns:\n"
            f"{list(customer_summary_dataframe.columns)}"
        )

    customer_summary = customer_summary_dataframe[
        required_columns
    ].copy()

    if customer_summary.empty:
        raise ValueError(
            "No customer-summary records were returned from SQL."
        )

    # ---------------------------------------------------------
    # Safety cleaning
    # ---------------------------------------------------------

    for column in [
        "customer_id",
        "customer_name",
        "province",
    ]:
        customer_summary[column] = (
            customer_summary[column]
            .astype("string")
            .str.strip()
        )

    for column in [
        "first_purchase_date",
        "latest_purchase_date",
    ]:
        customer_summary[column] = pd.to_datetime(
            customer_summary[column],
            errors="coerce",
        ).dt.normalize()

    for column in [
        "valid_purchase_days",
        "number_of_gaps",
        "total_gap_days",
    ]:
        customer_summary[column] = pd.to_numeric(
            customer_summary[column],
            errors="coerce",
        ).fillna(0).astype(int)

    customer_summary["total_positive_quantity"] = pd.to_numeric(
        customer_summary["total_positive_quantity"],
        errors="coerce",
    )

    customer_summary["average_gap_days"] = pd.to_numeric(
        customer_summary["average_gap_days"],
        errors="coerce",
    ).round(2)

    customer_summary = customer_summary.dropna(
        subset=[
            "customer_id",
            "latest_purchase_date",
        ]
    ).copy()

    customer_summary = customer_summary[
        customer_summary["customer_id"] != ""
    ].copy()

    if customer_summary.empty:
        raise ValueError(
            "No valid customer-summary records remained after cleaning."
        )

    # ---------------------------------------------------------
    # Days since latest purchase in Cambodia time
    # ---------------------------------------------------------

    today = (
        pd.Timestamp.now(
            tz=ZoneInfo("Asia/Phnom_Penh")
        )
        .normalize()
        .tz_localize(None)
    )

    customer_summary["days_since_last_purchase"] = (
        today
        - customer_summary["latest_purchase_date"]
    ).dt.days.astype("Int64")

    # ---------------------------------------------------------
    # Customer type
    # ---------------------------------------------------------

    def classify_customer(row: pd.Series) -> str:
        """Classify the customer's historical purchase pattern."""

        valid_purchase_days = row["valid_purchase_days"]
        average_gap = row["average_gap_days"]

        if valid_purchase_days == 1:
            return "One-Time Customer"

        if 1 <= average_gap <= 10.5:
            return "Weekly Customer"

        if 10.5 < average_gap <= 21.5:
            return "Bi-Weekly Customer"

        if 21.5 < average_gap <= 45.5:
            return "Monthly Customer"

        if 45.5 < average_gap <= 75:
            return "Bi-Monthly Customer"

        if average_gap > 75:
            return "Occasional Customer"

        raise ValueError(
            "Unable to classify customer "
            f"{row['customer_id']!r}: "
            f"valid_purchase_days={valid_purchase_days}, "
            f"average_gap_days={average_gap}"
        )

    customer_summary["customer_category"] = (
        customer_summary.apply(
            classify_customer,
            axis=1,
        )
    )

    # ---------------------------------------------------------
    # Customer status
    # ---------------------------------------------------------

    status_thresholds = {
        "Weekly Customer": 21,
        "Bi-Weekly Customer": 45,
        "Monthly Customer": 60,
        "Bi-Monthly Customer": 100,
    }

    def classify_customer_status(row: pd.Series) -> str:
        """Mark the customer Active or Inactive by customer type."""

        days_since_last_purchase = row[
            "days_since_last_purchase"
        ]

        if pd.isna(days_since_last_purchase):
            return "Unknown"

        inactive_threshold = status_thresholds.get(
            row["customer_category"]
        )

        if inactive_threshold is None:
            return "Not Evaluated"

        if days_since_last_purchase > inactive_threshold:
            return "Inactive"

        return "Active"

    customer_summary["customer_status"] = (
        customer_summary.apply(
            classify_customer_status,
            axis=1,
        )
    )

    # ---------------------------------------------------------
    # Purchase probability percentage
    # ---------------------------------------------------------

    probability_divisors = {
        "Weekly Customer": 10.5,
        "Bi-Weekly Customer": 21.5,
        "Monthly Customer": 45.5,
        "Bi-Monthly Customer": 75.5,
    }

    def calculate_purchase_probability(row: pd.Series):
        """
        Calculate purchase probability using the fixed divisor
        selected for each customer type.

        Results are capped between 0% and 100%.
        """

        days_since_last_purchase = row[
            "days_since_last_purchase"
        ]

        if pd.isna(days_since_last_purchase):
            return pd.NA

        divisor = probability_divisors.get(
            row["customer_category"]
        )

        if divisor is None:
            return pd.NA

        probability = (
            float(days_since_last_purchase)
            / divisor
            * 100
        )

        probability = max(
            0.0,
            min(probability, 100.0),
        )

        return round(probability, 2)

    customer_summary["purchase_probability_percent"] = (
        customer_summary.apply(
            calculate_purchase_probability,
            axis=1,
        )
        .astype("Float64")
    )

    # ---------------------------------------------------------
    # Sort final summary
    # ---------------------------------------------------------

    customer_summary = (
        customer_summary
        .sort_values(
            [
                "customer_status",
                "purchase_probability_percent",
                "customer_category",
                "average_gap_days",
                "customer_name",
            ],
            ascending=[
                True,
                False,
                True,
                True,
                True,
            ],
            na_position="last",
        )
        .reset_index(drop=True)
    )

    return customer_summary
