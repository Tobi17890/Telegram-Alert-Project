"""Calculate customer purchase frequency using valid purchase dates."""

import pandas as pd
from zoneinfo import ZoneInfo


def calculate_purchase_frequency(
    crt_dataframe: pd.DataFrame,
    customer_id_column: str,
    customer_name_column: str,
    billing_date_column: str,
    province_column: str,
    delivery_quantity_column: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Calculate average days between valid purchase dates.

    Business rules:
    - Positive delivery quantity means purchase.
    - Zero or negative delivery quantity is excluded.
    - Multiple positive records on the same date count as one purchase day.
    - Average gap from 1 to 10 days means Weekly Customer.

    Returns:
        purchase_gap_detail:
            One row per valid customer purchase day.

        customer_frequency_summary:
            One row per customer with the calculated average gap.
    """

    required_columns = [
        customer_id_column,
        customer_name_column,
        billing_date_column,
        province_column,
        delivery_quantity_column
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in crt_dataframe.columns
    ]

    if missing_columns:
        raise KeyError(
            "The following required CRT columns were not found:\n"
            f"{missing_columns}\n\n"
            "Available columns:\n"
            f"{list(crt_dataframe.columns)}"
        )

    data = crt_dataframe[
        required_columns
    ].copy()

    # Rename the source columns into consistent internal names.
    data = data.rename(
        columns={
            customer_id_column: "customer_id",
            customer_name_column: "customer_name",
            province_column: "province",
            billing_date_column: "billing_date",
            delivery_quantity_column: "delivery_quantity"
        }
    )

    # Clean customer information.
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
    # Convert dates.
    # dayfirst=True supports dates such as 17.02.2026.
    data["billing_date"] = pd.to_datetime(
        data["billing_date"],
        errors="coerce",
        dayfirst=True
    ).dt.normalize()

    # Convert quantities such as "1,000" into numeric values.
    data["delivery_quantity"] = pd.to_numeric(
        data["delivery_quantity"]
        .astype("string")
        .str.replace(",", "", regex=False),
        errors="coerce"
    )

    # Remove incomplete records.
    data = data.dropna(
        subset=[
            "customer_id",
            "billing_date",
            "delivery_quantity"
        ]
    ).copy()

    data = data[
        data["customer_id"] != ""
    ].copy()

    # Keep purchases only.
    # Negative quantities are returns and are excluded.
    valid_purchase_rows = data[
        data["delivery_quantity"] > 0
    ].copy()

    if valid_purchase_rows.empty:
        raise ValueError(
            "No positive delivery-quantity records were found."
        )

    # Collapse multiple positive item rows on the same date into
    # one customer purchase day.
    purchase_days = (
    valid_purchase_rows.groupby(
        [
            "customer_id",
            "billing_date"
        ],
        as_index=False
    )
    .agg(
        customer_name=("customer_name", "last"),
        province=("province", "last"),
        purchase_quantity=("delivery_quantity", "sum")
    )
    .rename(
        columns={
            "billing_date": "purchase_date"
        }
    )
    .sort_values(
        [
            "customer_id",
            "purchase_date"
        ]
    )
    .reset_index(drop=True)
    )

    # Find each customer's previous valid purchase date.
    purchase_days["previous_purchase_date"] = (
        purchase_days.groupby("customer_id")["purchase_date"]
        .shift(1)
    )

    # Calculate the days between consecutive purchases.
    purchase_days["gap_days"] = (
        purchase_days["purchase_date"]
        - purchase_days["previous_purchase_date"]
    ).dt.days

    # General purchase information for every customer.
    customer_base = (
    purchase_days.groupby(
        "customer_id",
        as_index=False,
        dropna=False
        )
    .agg(
        customer_name=("customer_name", "last"),
        province=("province", "last"),
        valid_purchase_days=("purchase_date", "nunique"),
        first_purchase_date=("purchase_date", "min"),
        latest_purchase_date=("purchase_date", "max"),
        total_positive_quantity=("purchase_quantity", "sum")
        )
    )

    # Gap information.
    customer_gaps = (
    purchase_days.groupby(
        "customer_id",
        as_index=False,
        dropna=False
    )
    .agg(
        number_of_gaps=("gap_days", "count"),
        total_gap_days=("gap_days", "sum"),
        average_gap_days=("gap_days", "mean")
        )
    )

    customer_summary = customer_base.merge(
        customer_gaps,
        on="customer_id",
        how="left"
    )
    
    # Get today's date using Cambodia time.
    today = (
        pd.Timestamp.now(tz=ZoneInfo("Asia/Phnom_Penh"))
        .normalize()
        .tz_localize(None)
    )

    # Calculate the number of days from the latest purchase until today.
    customer_summary["days_since_last_purchase"] = (
        today - customer_summary["latest_purchase_date"]
    ).dt.days.astype("Int64")
    
    

    customer_summary["number_of_gaps"] = (
        customer_summary["number_of_gaps"]
        .fillna(0)
        .astype(int)
    )

    customer_summary["total_gap_days"] = (
        customer_summary["total_gap_days"]
        .fillna(0)
        .astype(int)
    )

    customer_summary["average_gap_days"] = (
        customer_summary["average_gap_days"]
        .round(2)
    )

    def classify_customer(row: pd.Series) -> str:
        """
        Apply the agreed customer-frequency classification.
        """
        average_gap = row["average_gap_days"]
        if 1 <= average_gap <= 10.5:
            return "Weekly Customer"

        if average_gap <= 21.5:
            return "Bi-Weekly Customer"

        if average_gap <= 45.5:
            return "Monthly Customer"

        if average_gap <= 75:
            return "Bi-Monthly Customer"

        return "Inactive Customer"

    customer_summary["customer_category"] = (
        customer_summary.apply(
            classify_customer,
            axis=1
        )
    )

    customer_summary = customer_summary.sort_values(
        [
            "customer_category",
            "average_gap_days",
            "customer_name"
        ],
        na_position="last"
    ).reset_index(drop=True)

    purchase_gap_detail = purchase_days[
        [
            "customer_id",
            "customer_name",
            "province",
            "purchase_date",
            "previous_purchase_date",
            "gap_days",
            "purchase_quantity"
        ]
    ].copy()

    return purchase_gap_detail, customer_summary