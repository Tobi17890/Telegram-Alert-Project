"""Offline tests for Google Sheets tracking dataset preparation."""

import pandas as pd

from src.tracking.google_sheets_tracking import (
    ALL_COLUMNS,
    build_alert_id,
    build_tracking_dataset,
)


def sample_alerts():
    return pd.DataFrame(
        [
            {
                "customer_id": "9001",
                "customer_name": "Weekly A",
                "province": "Kandal",
                "latest_purchase_date": pd.Timestamp("2026-08-01"),
                "days_since_last_purchase": 24,
                "customer_category": "Weekly Customer",
                "customer_status": "Active",
                "purchase_probability_percent": 100.0,
            },
            {
                "customer_id": "9002",
                "customer_name": "Monthly B",
                "province": "Kandal",
                "latest_purchase_date": pd.Timestamp("2026-07-01"),
                "days_since_last_purchase": 55,
                "customer_category": "Bi-Weekly Customer",
                "customer_status": "Inactive",
                "purchase_probability_percent": 80.0,
            },
        ]
    )


def sample_tracking():
    return pd.DataFrame(
        [
            {"customer_id": "9001", "activity": "No Action"},
            {"customer_id": "9002", "activity": "No Action"},
        ]
    )


def run_tests():
    assert build_alert_id("CRT", "2026-08-25", "9001") == "CRT-20260825-9001"
    assert build_alert_id("TPP", "2026-08-25", 9002.0) == "TPP-20260825-9002"

    result = build_tracking_dataset(
        alert_customers=sample_alerts(),
        today_tracking=sample_tracking(),
        product="CRT",
        province_regions={"Kandal": "R1"},
        included_provinces={"Kandal"},
    )

    assert list(result.columns) == ALL_COLUMNS
    assert result["Customer ID"].tolist() == ["9001", "9002"]
    assert result["Customer Type"].tolist() == ["Weekly", "Bi-Weekly"]
    assert result["Status"].tolist() == ["Active", "Inactive"]
    assert result["Region"].tolist() == ["R1", "R1"]
    assert result["Reason"].tolist() == ["", ""]
    assert result["Activity"].tolist() == ["No Action", "No Action"]

    extra = sample_alerts().iloc[[0]].copy()
    extra["customer_id"] = "9999"
    extra["province"] = "Unrouted"
    with_extra = pd.concat([sample_alerts(), extra], ignore_index=True)
    tracking = pd.concat(
        [sample_tracking(), pd.DataFrame([{"customer_id": "9999", "activity": "No Action"}])],
        ignore_index=True,
    )
    routed_only = build_tracking_dataset(
        alert_customers=with_extra,
        today_tracking=tracking,
        product="CRT",
        province_regions={"Kandal": "R1"},
        included_provinces={"Kandal"},
    )
    assert set(routed_only["Province"].tolist()) == {"Kandal"}

    print("Google Sheets tracking offline tests passed.")


if __name__ == "__main__":
    run_tests()
