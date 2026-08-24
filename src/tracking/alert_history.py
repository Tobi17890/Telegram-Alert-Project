"""Track daily CRT/TPP customer alerts and re-engagement."""

from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


# ============================================
# HISTORY COLUMNS
# ============================================

HISTORY_COLUMNS = [
    "alert_date",
    "product",
    "province",
    "customer_id",
    "customer_name",

    # Purchase date when this row was created.
    "latest_purchase_date",

    # Purchase date when the current alert cycle began.
    # We keep this internally so Python can detect
    # whether the customer has purchased again.
    "baseline_purchase_date",

    "days_since_last_purchase",
    "customer_category",
    "customer_status",
    "purchase_probability_percent",

    # No Action / Action Taken
    "activity",

    # Manual regional feedback later.
    "reason",
]


# ============================================
# LOAD HISTORY
# ============================================

def load_alert_history(
    history_path: Path,
) -> pd.DataFrame:
    """
    Load existing alert history.

    If no history file exists yet,
    return an empty DataFrame.
    """

    if not history_path.exists():

        return pd.DataFrame(
            columns=HISTORY_COLUMNS
        )


    history = pd.read_csv(
        history_path,
        dtype={
            "product": "string",
            "province": "string",
            "customer_id": "string",
            "customer_name": "string",
            "customer_category": "string",
            "customer_status": "string",
            "activity": "string",
            "reason": "string",
        },
    )


    # Make sure all expected columns exist.
    for column in HISTORY_COLUMNS:

        if column not in history.columns:

            history[column] = pd.NA


    history = history[
        HISTORY_COLUMNS
    ].copy()


    # ========================================
    # DATE TYPES
    # ========================================

    for column in [
        "alert_date",
        "latest_purchase_date",
        "baseline_purchase_date",
    ]:

        history[column] = pd.to_datetime(
            history[column],
            errors="coerce",
        )


    # ========================================
    # CUSTOMER ID
    # ========================================

    history["customer_id"] = (
        history["customer_id"]
        .astype("string")
        .str.strip()
    )


    return history


# ============================================
# UPDATE DAILY ALERT HISTORY
# ============================================

def update_daily_alert_history(
    customer_summary: pd.DataFrame,
    product: str,
    minimum_probability: float,
    history_path: Path,
) -> pd.DataFrame:
    """
    Compare today's customer data against previous
    alert history.

    Activity rules:

    No Action
        Customer is currently an alert customer
        and no new purchase has happened since
        the current alert cycle started.

    Action Taken
        Customer existed in previous alert history
        and now has a newer purchase date.

    Returns only today's tracking rows.

    The permanent history CSV is also updated.
    """

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
        if column not in customer_summary.columns
    ]


    if missing_columns:

        raise KeyError(
            "Alert tracking requires these columns:\n"
            f"{missing_columns}"
        )


    # ========================================
    # TODAY - CAMBODIA TIME
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
    # PREPARE CURRENT CUSTOMER DATA
    # ========================================

    current = customer_summary[
        required_columns
    ].copy()


    current["customer_id"] = (
        current["customer_id"]
        .astype("string")
        .str.strip()
    )


    current["customer_name"] = (
        current["customer_name"]
        .astype("string")
        .str.strip()
    )


    current["province"] = (
        current["province"]
        .astype("string")
        .str.strip()
        .fillna(
            "Unknown Province"
        )
    )


    current[
        "latest_purchase_date"
    ] = pd.to_datetime(
        current[
            "latest_purchase_date"
        ],
        errors="coerce",
    )


    current[
        "purchase_probability_percent"
    ] = pd.to_numeric(
        current[
            "purchase_probability_percent"
        ],
        errors="coerce",
    )


    # ========================================
    # REMOVE CUSTOMER IDs 14xxxx / 15xxxx
    # ========================================

    current = current[
        ~current[
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
    # TODAY'S NORMAL ALERT CUSTOMERS
    # ========================================

    current_alerts = current[
        current[
            "customer_status"
        ].isin(
            [
                "Active",
                "Inactive",
            ]
        )
        &
        (
            current[
                "purchase_probability_percent"
            ]
            >= minimum_probability
        )
    ].copy()


    current_alert_ids = set(
        current_alerts[
            "customer_id"
        ].dropna()
    )


    # ========================================
    # LOAD PREVIOUS HISTORY
    # ========================================

    history = load_alert_history(
        history_path=history_path,
    )


    product_history = history[
        history["product"]
        .astype("string")
        .str.upper()
        == product
    ].copy()


    # ========================================
    # FIND LATEST HISTORY STATUS
    # FOR EACH CUSTOMER
    # ========================================

    latest_history_by_customer = {}


    if not product_history.empty:

        product_history = (
            product_history
            .sort_values(
                [
                    "alert_date",
                ]
            )
        )


        latest_rows = (
            product_history
            .groupby(
                "customer_id",
                dropna=False,
            )
            .tail(1)
        )


        latest_history_by_customer = {
            str(row["customer_id"]): row
            for _, row
            in latest_rows.iterrows()
        }


    # ========================================
    # CUSTOMERS WITH OPEN PREVIOUS ALERTS
    # ========================================

    previous_open_ids = set()


    for (
        customer_id,
        previous_row,
    ) in latest_history_by_customer.items():

        previous_activity = str(
            previous_row[
                "activity"
            ]
        ).strip()

        if previous_activity == "No Action":

            previous_open_ids.add(
                customer_id
            )


    # ========================================
    # CUSTOMERS TO CHECK TODAY
    # ========================================
    #
    # 1. Today's alert customers
    # 2. Customers still open from history
    #
    # This second group is important because
    # after they purchase their probability may
    # drop below 60%, but we still need to detect
    # "Action Taken".
    # ========================================

    customers_to_check = (
        current_alert_ids
        |
        previous_open_ids
    )


    current_by_customer = (
        current
        .drop_duplicates(
            subset=[
                "customer_id",
            ],
            keep="last",
        )
        .set_index(
            "customer_id"
        )
    )


    today_rows = []


    # ========================================
    # DETERMINE ACTIVITY
    # ========================================

    for customer_id in customers_to_check:

        if (
            customer_id
            not in current_by_customer.index
        ):

            continue


        row = current_by_customer.loc[
            customer_id
        ]


        current_latest_purchase = (
            row[
                "latest_purchase_date"
            ]
        )


        previous_row = (
            latest_history_by_customer.get(
                str(customer_id)
            )
        )


        # ====================================
        # CASE 1:
        # CUSTOMER HAS NO OPEN HISTORY
        # ====================================

        if (
            previous_row is None
            or str(
                previous_row[
                    "activity"
                ]
            ).strip()
            == "Action Taken"
        ):

            # Only start a new alert cycle if
            # the customer qualifies today.
            if (
                customer_id
                not in current_alert_ids
            ):

                continue


            baseline_purchase_date = (
                current_latest_purchase
            )


            activity = "No Action"


        # ====================================
        # CASE 2:
        # CUSTOMER HAS PREVIOUS OPEN ALERT
        # ====================================

        else:

            baseline_purchase_date = (
                previous_row[
                    "baseline_purchase_date"
                ]
            )


            # Fallback for old/broken history.
            if pd.isna(
                baseline_purchase_date
            ):

                baseline_purchase_date = (
                    previous_row[
                        "latest_purchase_date"
                    ]
                )


            # =================================
            # NEW PURCHASE DETECTED
            # =================================

            if (
                pd.notna(
                    current_latest_purchase
                )
                and
                pd.notna(
                    baseline_purchase_date
                )
                and
                current_latest_purchase
                >
                baseline_purchase_date
            ):

                activity = (
                    "Action Taken"
                )


            # =================================
            # STILL NO PURCHASE
            # =================================

            else:

                # Customer must still qualify
                # for today's alert.
                if (
                    customer_id
                    not in current_alert_ids
                ):

                    continue


                activity = "No Action"


        # ====================================
        # ADD TODAY'S HISTORY ROW
        # ====================================

        today_rows.append(
            {
                "alert_date": today,
                "product": product,
                "province": (
                    row["province"]
                ),
                "customer_id": (
                    customer_id
                ),
                "customer_name": (
                    row[
                        "customer_name"
                    ]
                ),
                "latest_purchase_date": (
                    current_latest_purchase
                ),
                "baseline_purchase_date": (
                    baseline_purchase_date
                ),
                "days_since_last_purchase": (
                    row[
                        "days_since_last_purchase"
                    ]
                ),
                "customer_category": (
                    row[
                        "customer_category"
                    ]
                ),
                "customer_status": (
                    row[
                        "customer_status"
                    ]
                ),
                "purchase_probability_percent": (
                    row[
                        "purchase_probability_percent"
                    ]
                ),
                "activity": activity,
                "reason": "",
            }
        )


    # ========================================
    # CREATE TODAY DATAFRAME
    # ========================================

    today_tracking = pd.DataFrame(
        today_rows,
        columns=HISTORY_COLUMNS,
    )


    if today_tracking.empty:

        print(
            f"\nNo {product} tracking "
            "rows generated today."
        )

        return today_tracking


    # ========================================
    # APPEND TO PERMANENT HISTORY
    # ========================================

    updated_history = pd.concat(
        [
            history,
            today_tracking,
        ],
        ignore_index=True,
    )


    # ========================================
    # PREVENT DUPLICATES IF YOU RUN
    # THE SCRIPT MORE THAN ONCE TODAY
    # ========================================

    updated_history = (
        updated_history
        .sort_values(
            [
                "alert_date",
                "product",
                "customer_id",
            ]
        )
        .drop_duplicates(
            subset=[
                "alert_date",
                "product",
                "customer_id",
            ],
            keep="last",
        )
        .reset_index(
            drop=True
        )
    )


    # ========================================
    # SAVE HISTORY
    # ========================================

    history_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )


    updated_history.to_csv(
        history_path,
        index=False,
        encoding="utf-8-sig",
    )


    print(
        f"\n{product} alert history updated:"
    )

    print(
        history_path
    )


    print(
        "Today's No Action customers: "
        f"{(
            today_tracking['activity']
            == 'No Action'
        ).sum():,}"
    )


    print(
        "Today's Action Taken customers: "
        f"{(
            today_tracking['activity']
            == 'Action Taken'
        ).sum():,}"
    )


    return today_tracking