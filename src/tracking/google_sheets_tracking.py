"""Google Sheets tracking for the Telegram Customer Alert System.

Architecture
------------
1. The existing validated CRT/TPP engine produces the exact routed alert
   population.
2. A private MASTER spreadsheet keeps the centralized historical Alert_Data.
3. Each configured region has its own Google Spreadsheet for salesman follow-up.
4. Inside a regional spreadsheet, Python creates one tab per Product + Province,
   for example ``CRT - Pailin`` or ``TPP - Pailin``.
5. Telegram receives the province-specific regional-tab link, not the MASTER
   Alert_Data link.

This module does not reimplement alert eligibility, customer classification,
Active/Inactive status, probability thresholds, customer-ID exclusions,
sorting, Telegram routing, or purchase/re-engagement business rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
from zoneinfo import ZoneInfo
import json
import numbers
import os
import re

import pandas as pd
from dotenv import load_dotenv


# ============================================
# SHEET SCHEMA
# ============================================

LEGACY_VISIBLE_COLUMNS = [
    "Alert Date",
    "Customer ID",
    "Customer Name",
    "Customer Type",
    "Status",
    "Last Purchase Date",
    "Activity",
    "Reason",
]

VISIBLE_COLUMNS = [
    "Alert Date",
    "Customer ID",
    "Customer Name",
    "Customer Type",
    "Status",
    "Last",
    "Last Purchase Date",
    "Activity",
    "Reason",
]

BASE_INTERNAL_COLUMNS = [
    "Alert_ID",
    "Product",
    "Region",
    "Province",
    "Days Since Last Purchase",
    "Probability",
    "Updated_By",
    "Updated_At",
]

REMINDER_INTERNAL_COLUMNS = [
    "Reason_Filled_At",
    "Reminder_Count",
]

INTERNAL_COLUMNS = BASE_INTERNAL_COLUMNS + REMINDER_INTERNAL_COLUMNS
LEGACY_V1_ALL_COLUMNS = LEGACY_VISIBLE_COLUMNS + BASE_INTERNAL_COLUMNS
LEGACY_V2_ALL_COLUMNS = VISIBLE_COLUMNS + BASE_INTERNAL_COLUMNS
ALL_COLUMNS = VISIBLE_COLUMNS + INTERNAL_COLUMNS

REASON_REMINDER_DAYS = 12

PROTECTION_DESCRIPTION = (
    "Telegram Customer Alert - Reason only editable"
)

SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"

REGION_ENV_KEYS = {
    "R1": "GOOGLE_SHEETS_R1_SPREADSHEET_ID",
    "R2": "GOOGLE_SHEETS_R2_SPREADSHEET_ID",
    "R3": "GOOGLE_SHEETS_R3_SPREADSHEET_ID",
    "R4": "GOOGLE_SHEETS_R4_SPREADSHEET_ID",
    "R5": "GOOGLE_SHEETS_R5_SPREADSHEET_ID",
    "R6": "GOOGLE_SHEETS_R6_SPREADSHEET_ID",
}


# Automatic retry for transient Google API failures (429 and 5xx).
# google-api-python-client uses exponential backoff when num_retries > 0.
GOOGLE_API_NUM_RETRIES = 6

# Process-local caches. The same tab is touched during Reason evaluation and
# again during final sync; these caches prevent repeated reads in one run.
_SERVICE_CACHE: dict[str, Any] = {}
_WORKBOOK_METADATA_CACHE: dict[str, dict[str, Any]] = {}
_TAB_VALUES_CACHE: dict[tuple[str, str], list[list[Any]]] = {}
_SCHEMA_CACHE: dict[tuple[str, str], int] = {}


# ============================================
# ERRORS / CONFIG
# ============================================

class GoogleSheetsTrackingError(RuntimeError):
    """Base error for the online tracking layer."""


class GoogleSheetsTrackingValidationError(GoogleSheetsTrackingError):
    """Raised when tracker input or Google Sheet schema is inconsistent."""


@dataclass(frozen=True)
class GoogleSheetsTrackingConfig:
    """Configuration for one spreadsheet + one worksheet/tab."""

    spreadsheet_id: str
    service_account_file: Path
    worksheet_title: str = "Alert_Data"
    protect_reason_only: bool = False

    @classmethod
    def from_env(cls) -> "GoogleSheetsTrackingConfig":
        """Load the MASTER tracker settings from the project .env file."""

        project_root = Path(__file__).resolve().parents[2]
        load_dotenv(project_root / ".env")

        spreadsheet_id = str(
            os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
        ).strip()
        service_account_text = str(
            os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
        ).strip()
        worksheet_title = str(
            os.getenv("GOOGLE_SHEETS_WORKSHEET", "Alert_Data")
        ).strip() or "Alert_Data"

        if not spreadsheet_id:
            raise GoogleSheetsTrackingValidationError(
                "GOOGLE_SHEETS_SPREADSHEET_ID is missing from .env. "
                "This should be the private MASTER spreadsheet ID."
            )

        if not service_account_text:
            raise GoogleSheetsTrackingValidationError(
                "GOOGLE_SERVICE_ACCOUNT_FILE is missing from .env."
            )

        service_account_file = Path(service_account_text)
        if not service_account_file.is_absolute():
            service_account_file = project_root / service_account_file

        return cls(
            spreadsheet_id=spreadsheet_id,
            service_account_file=service_account_file,
            worksheet_title=worksheet_title,
        )


# ============================================
# ENV / REGIONAL ROUTING
# ============================================

def get_configured_regional_spreadsheets() -> dict[str, str]:
    """Return only regional workbooks currently configured in .env."""

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

    configured: dict[str, str] = {}

    for region, env_key in REGION_ENV_KEYS.items():
        spreadsheet_id = str(os.getenv(env_key, "")).strip()
        if spreadsheet_id:
            configured[region] = spreadsheet_id

    return configured


def get_service_account_file() -> Path:
    """Return the Google service-account JSON path without requiring a MASTER sheet."""

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

    service_account_text = str(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "")
    ).strip()

    if not service_account_text:
        raise GoogleSheetsTrackingValidationError(
            "GOOGLE_SERVICE_ACCOUNT_FILE is missing from .env."
        )

    service_account_file = Path(service_account_text)

    if not service_account_file.is_absolute():
        service_account_file = project_root / service_account_file

    return service_account_file


def should_write_master_google_sheet() -> bool:
    """Return whether the private MASTER Alert_Data write is enabled.

    Environment variable:
        GOOGLE_SHEETS_WRITE_MASTER=true/false

    Default is true so existing behavior is preserved unless explicitly disabled.
    """

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

    raw_value = str(
        os.getenv("GOOGLE_SHEETS_WRITE_MASTER", "true")
    ).strip().lower()

    if raw_value in {
        "1",
        "true",
        "yes",
        "y",
        "on",
    }:
        return True

    if raw_value in {
        "0",
        "false",
        "no",
        "n",
        "off",
    }:
        return False

    raise GoogleSheetsTrackingValidationError(
        "GOOGLE_SHEETS_WRITE_MASTER must be true or false."
    )


def get_optional_master_config() -> GoogleSheetsTrackingConfig | None:
    """Return MASTER config when enabled and configured; otherwise None.

    This lets regional workbooks continue operating while MASTER access is
    temporarily unavailable.
    """

    if not should_write_master_google_sheet():
        return None

    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")

    spreadsheet_id = str(
        os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    ).strip()

    if not spreadsheet_id:
        print(
            "MASTER Google Sheet is enabled but "
            "GOOGLE_SHEETS_SPREADSHEET_ID is blank; "
            "MASTER sync will be skipped."
        )
        return None

    worksheet_title = str(
        os.getenv("GOOGLE_SHEETS_WORKSHEET", "Alert_Data")
    ).strip() or "Alert_Data"

    return GoogleSheetsTrackingConfig(
        spreadsheet_id=spreadsheet_id,
        service_account_file=get_service_account_file(),
        worksheet_title=worksheet_title,
    )


def get_configured_google_regions() -> set[str]:
    """Return configured region codes such as {'R4', 'R5', 'R6'}."""

    return set(get_configured_regional_spreadsheets())


# ============================================
# SMALL HELPERS
# ============================================

def _cambodia_today() -> pd.Timestamp:
    return (
        pd.Timestamp.now(tz=ZoneInfo("Asia/Phnom_Penh"))
        .normalize()
        .tz_localize(None)
    )


def _cambodia_now_iso() -> str:
    return (
        pd.Timestamp.now(tz=ZoneInfo("Asia/Phnom_Penh"))
        .replace(microsecond=0)
        .isoformat()
    )


def _reason_age_days(
    reason_filled_at: Any,
    today: pd.Timestamp | None = None,
) -> int | None:
    """Return full Cambodia calendar days since Reason was first detected."""

    timestamp = pd.to_datetime(
        reason_filled_at,
        errors="coerce",
    )

    if pd.isna(timestamp):
        return None

    if getattr(timestamp, "tzinfo", None) is not None:
        timestamp = (
            timestamp
            .tz_convert("Asia/Phnom_Penh")
            .tz_localize(None)
        )

    current_day = pd.Timestamp(
        today if today is not None else _cambodia_today()
    ).normalize()

    return max(
        0,
        int((current_day - pd.Timestamp(timestamp).normalize()).days),
    )


def _normalize_customer_id(value: Any) -> str:
    if value is None:
        return ""

    try:
        if value != value:
            return ""
    except Exception:
        pass

    if isinstance(value, numbers.Real) and not isinstance(value, bool):
        try:
            if float(value).is_integer():
                value = str(int(value))
        except (TypeError, ValueError, OverflowError):
            pass

    return str(value).strip()


def _safe_alert_id_component(value: Any) -> str:
    value = _normalize_customer_id(value)

    if not value:
        raise GoogleSheetsTrackingValidationError(
            "Customer ID cannot be blank when creating Alert_ID."
        )

    safe = re.sub(r"[^A-Za-z0-9_-]+", "", value)

    if not safe:
        raise GoogleSheetsTrackingValidationError(
            "Customer ID could not be converted to a safe Alert_ID component."
        )

    return safe


def _normalize_product(product: str) -> str:
    value = re.sub(
        r"[^A-Za-z0-9]+",
        "",
        str(product).strip().upper(),
    )

    if not value:
        raise GoogleSheetsTrackingValidationError("Product cannot be blank.")

    return value


def _to_iso_date_text(value: Any) -> str:
    if value is None:
        return ""

    try:
        if value != value:
            return ""
    except Exception:
        pass

    timestamp = pd.to_datetime(value, errors="coerce")

    if pd.isna(timestamp):
        return ""

    return timestamp.strftime("%Y-%m-%d")


def _clean_cell_value(value: Any) -> Any:
    if value is None:
        return ""

    try:
        if value != value:
            return ""
    except Exception:
        pass

    if isinstance(value, pd.Timestamp):
        return _to_iso_date_text(value)

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    item_method = getattr(value, "item", None)
    if callable(item_method):
        try:
            return item_method()
        except Exception:
            pass

    return value


def _customer_type_display(value: Any) -> str:
    if pd.isna(value):
        return "Unknown"

    text = str(value).strip()

    if text.endswith(" Customer"):
        text = text[: -len(" Customer")]

    return text


def _last_days_display(value: Any) -> str:
    """Format days-since-last-purchase for salesmen, e.g. 84d-ago."""

    if value is None:
        return ""

    try:
        if value != value:
            return ""
    except Exception:
        pass

    try:
        days = int(float(value))
    except (TypeError, ValueError, OverflowError):
        return str(value).strip()

    return f"{days}d-ago"


def _column_to_a1(column_number: int) -> str:
    if column_number < 1:
        raise ValueError("Column number must be >= 1.")

    result = ""
    current = column_number

    while current:
        current, remainder = divmod(current - 1, 26)
        result = chr(65 + remainder) + result

    return result


def _quote_sheet_title(title: str) -> str:
    return "'" + str(title).replace("'", "''") + "'"


def _regional_tab_title(product: str, province: str) -> str:
    """Build a safe, readable Google worksheet name."""

    product_code = _normalize_product(product)
    province_name = str(province).strip()

    if not province_name:
        raise GoogleSheetsTrackingValidationError(
            "Province cannot be blank when creating a regional tab."
        )

    title = f"{product_code} - {province_name}"
    title = re.sub(r"[\\/\?\*\[\]:]", "-", title)
    title = title[:100].strip()

    if not title:
        raise GoogleSheetsTrackingValidationError(
            "Regional Google Sheet tab title is blank."
        )

    return title


# ============================================
# ALERT ID
# ============================================

def build_alert_id(product: str, alert_date: Any, customer_id: Any) -> str:
    """Build deterministic event ID, e.g. CRT-20260825-12345."""

    product_code = _normalize_product(product)
    alert_date_text = _to_iso_date_text(alert_date)

    if not alert_date_text:
        raise GoogleSheetsTrackingValidationError("Alert Date is invalid.")

    date_key = pd.Timestamp(alert_date_text).strftime("%Y%m%d")
    customer_key = _safe_alert_id_component(customer_id)

    return f"{product_code}-{date_key}-{customer_key}"


# ============================================
# BUILD EXACT TRACKING POPULATION
# ============================================

def build_tracking_dataset(
    alert_customers: pd.DataFrame,
    today_tracking: pd.DataFrame,
    product: str,
    province_regions: Mapping[str, str],
    included_provinces: set[str] | None = None,
) -> pd.DataFrame:
    """Build tracking rows from the exact routed Telegram alert population."""

    product_code = _normalize_product(product)

    required = [
        "customer_id",
        "customer_name",
        "province",
        "latest_purchase_date",
        "days_since_last_purchase",
        "customer_category",
        "customer_status",
        "purchase_probability_percent",
    ]

    missing = [
        column
        for column in required
        if column not in alert_customers.columns
    ]

    if missing:
        raise GoogleSheetsTrackingValidationError(
            f"Google Sheets tracking is missing alert columns: {missing}"
        )

    if alert_customers.empty:
        return pd.DataFrame(columns=ALL_COLUMNS)

    optional_policy_columns = [
        "_reminder_count"
    ] if "_reminder_count" in alert_customers.columns else []

    data = alert_customers[required + optional_policy_columns].copy()
    data["customer_id"] = data["customer_id"].map(_normalize_customer_id)
    data["province"] = data["province"].astype("string").str.strip()

    if included_provinces is not None:
        allowed = {str(value).strip() for value in included_provinces}
        data = data[data["province"].isin(allowed)].copy()

    if data.empty:
        return pd.DataFrame(columns=ALL_COLUMNS)

    if today_tracking is None or today_tracking.empty:
        raise GoogleSheetsTrackingValidationError(
            "today_tracking is empty while routed alert customers exist."
        )

    for column in ["customer_id", "activity"]:
        if column not in today_tracking.columns:
            raise GoogleSheetsTrackingValidationError(
                f"today_tracking is missing required column: {column}"
            )

    activity_lookup = today_tracking[["customer_id", "activity"]].copy()
    activity_lookup["customer_id"] = activity_lookup["customer_id"].map(
        _normalize_customer_id
    )
    activity_lookup = activity_lookup.drop_duplicates(
        subset=["customer_id"],
        keep="last",
    )

    data = data.merge(
        activity_lookup,
        on="customer_id",
        how="left",
        sort=False,
        validate="many_to_one",
    )

    if data["activity"].isna().any():
        missing_ids = data.loc[
            data["activity"].isna(),
            "customer_id",
        ].tolist()
        raise GoogleSheetsTrackingValidationError(
            "Some routed Telegram customers have no today_tracking row: "
            f"{missing_ids}"
        )

    region_map = {
        str(province).strip(): str(region).strip()
        for province, region in province_regions.items()
    }

    data["_region"] = data["province"].map(region_map)

    missing_region = (
        data["_region"].isna()
        | (data["_region"].astype(str).str.strip() == "")
    )

    if missing_region.any():
        missing_provinces = sorted(
            set(
                data.loc[missing_region, "province"]
                .astype(str)
                .tolist()
            )
        )
        raise GoogleSheetsTrackingValidationError(
            "Routed alert provinces are missing region mapping: "
            f"{missing_provinces}"
        )

    alert_date = _cambodia_today()
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for _, row in data.iterrows():
        customer_id = _normalize_customer_id(row["customer_id"])
        event_alert_date = alert_date
        alert_id = build_alert_id(
            product_code,
            event_alert_date,
            customer_id,
        )

        reminder_count = pd.to_numeric(
            row.get("_reminder_count", 0),
            errors="coerce",
        )
        if pd.isna(reminder_count):
            reminder_count = 0
        reminder_count = int(reminder_count)

        if alert_id in seen_ids:
            raise GoogleSheetsTrackingValidationError(
                f"Duplicate alert event in tracker population: {alert_id}"
            )

        seen_ids.add(alert_id)

        rows.append(
            {
                "Alert Date": pd.Timestamp(event_alert_date).strftime("%Y-%m-%d"),
                "Customer ID": customer_id,
                "Customer Name": _clean_cell_value(row["customer_name"]),
                "Customer Type": _customer_type_display(
                    row["customer_category"]
                ),
                "Status": _clean_cell_value(row["customer_status"]),
                "Last": _last_days_display(
                    row["days_since_last_purchase"]
                ),
                "Last Purchase Date": _to_iso_date_text(
                    row["latest_purchase_date"]
                ),
                "Activity": _clean_cell_value(row["activity"]),
                "Reason": "",
                "Alert_ID": alert_id,
                "Product": product_code,
                "Region": _clean_cell_value(row["_region"]),
                "Province": _clean_cell_value(row["province"]),
                "Days Since Last Purchase": _clean_cell_value(
                    row["days_since_last_purchase"]
                ),
                "Probability": _clean_cell_value(
                    row["purchase_probability_percent"]
                ),
                "Updated_By": "",
                "Updated_At": "",
                "Reason_Filled_At": "",
                "Reminder_Count": reminder_count,
            }
        )

    return pd.DataFrame(rows, columns=ALL_COLUMNS)


# ============================================
# LOW-LEVEL GOOGLE SHEET READER/WRITER
# ============================================

class GoogleSheetsAlertTracker:
    """One spreadsheet + one worksheet/tab Google Sheets reader/writer."""

    def __init__(
        self,
        config: GoogleSheetsTrackingConfig,
        service: Any | None = None,
    ) -> None:
        self.config = config
        self._service = service

    @property
    def service(self) -> Any:
        if self._service is None:
            self._service = self._build_service()
        return self._service

    def _build_service(self) -> Any:
        if not self.config.service_account_file.exists():
            raise GoogleSheetsTrackingValidationError(
                "Google service-account JSON was not found: "
                f"{self.config.service_account_file}"
            )

        try:
            from google.oauth2 import service_account
            from googleapiclient.discovery import build
        except ImportError as error:
            raise GoogleSheetsTrackingError(
                "Google Sheets libraries are missing. "
                "Run pip install -r requirements.txt."
            ) from error

        service_key = str(
            self.config.service_account_file.resolve()
        )

        cached_service = _SERVICE_CACHE.get(
            service_key
        )
        if cached_service is not None:
            return cached_service

        credentials = service_account.Credentials.from_service_account_file(
            str(self.config.service_account_file),
            scopes=[SHEETS_SCOPE],
        )

        service = build(
            "sheets",
            "v4",
            credentials=credentials,
            cache_discovery=False,
        )
        _SERVICE_CACHE[service_key] = service
        return service

    def _service_account_email(self) -> str:
        """Return the service-account email from the JSON credential."""

        try:
            payload = json.loads(
                self.config.service_account_file.read_text(
                    encoding="utf-8"
                )
            )
        except Exception as error:
            raise GoogleSheetsTrackingValidationError(
                "Could not read the Google service-account JSON "
                "while configuring sheet protection."
            ) from error

        email = str(
            payload.get(
                "client_email",
                "",
            )
        ).strip()

        if not email:
            raise GoogleSheetsTrackingValidationError(
                "Google service-account JSON is missing client_email."
            )

        return email

    def _migrate_schema(
        self,
        sheet_id: int,
        existing_headers: list[Any],
    ) -> bool:
        """Migrate V1/V2 tracker tabs without deleting existing data or Reasons."""

        raw = [str(value).strip() for value in existing_headers]
        while raw and raw[-1] == "":
            raw.pop()

        if raw == ALL_COLUMNS:
            return False

        if raw == LEGACY_V1_ALL_COLUMNS:
            last_index = VISIBLE_COLUMNS.index("Last")
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.config.spreadsheet_id,
                body={
                    "requests": [
                        {
                            "insertDimension": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "COLUMNS",
                                    "startIndex": last_index,
                                    "endIndex": last_index + 1,
                                },
                                "inheritFromBefore": True,
                            }
                        }
                    ]
                },
            ).execute(num_retries=GOOGLE_API_NUM_RETRIES)
            was_v1 = True

        elif raw == LEGACY_V2_ALL_COLUMNS:
            was_v1 = False

        else:
            return False

        properties = self._get_sheet_properties()
        current_count = int(
            properties.get("gridProperties", {}).get(
                "columnCount",
                len(ALL_COLUMNS),
            )
        )

        if current_count < len(ALL_COLUMNS):
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.config.spreadsheet_id,
                body={
                    "requests": [
                        {
                            "appendDimension": {
                                "sheetId": sheet_id,
                                "dimension": "COLUMNS",
                                "length": len(ALL_COLUMNS) - current_count,
                            }
                        }
                    ]
                },
            ).execute(num_retries=GOOGLE_API_NUM_RETRIES)

        title = _quote_sheet_title(self.config.worksheet_title)
        end_col = _column_to_a1(len(ALL_COLUMNS))
        self.service.spreadsheets().values().update(
            spreadsheetId=self.config.spreadsheet_id,
            range=f"{title}!A1:{end_col}1",
            valueInputOption="RAW",
            body={"values": [ALL_COLUMNS]},
        ).execute(num_retries=GOOGLE_API_NUM_RETRIES)

        if was_v1:
            days_col = _column_to_a1(
                ALL_COLUMNS.index("Days Since Last Purchase") + 1
            )
            last_col = _column_to_a1(ALL_COLUMNS.index("Last") + 1)
            day_values = (
                self.service.spreadsheets()
                .values()
                .get(
                    spreadsheetId=self.config.spreadsheet_id,
                    range=f"{title}!{days_col}2:{days_col}",
                )
                .execute(num_retries=GOOGLE_API_NUM_RETRIES)
                .get("values", [])
            )
            if day_values:
                formatted = [
                    [_last_days_display(row[0] if row else "")]
                    for row in day_values
                ]
                self.service.spreadsheets().values().update(
                    spreadsheetId=self.config.spreadsheet_id,
                    range=f"{title}!{last_col}2:{last_col}",
                    valueInputOption="RAW",
                    body={"values": formatted},
                ).execute(num_retries=GOOGLE_API_NUM_RETRIES)

        # Structural migration changes both workbook metadata and row values.
        self._invalidate_tab_values()
        self._invalidate_workbook_metadata()

        return True

    def _cache_key(self) -> tuple[str, str]:
        return (
            self.config.spreadsheet_id,
            self.config.worksheet_title,
        )

    def _get_workbook_metadata(
        self,
        refresh: bool = False,
    ) -> dict[str, Any]:
        """Read workbook metadata once and share it across all province tabs."""

        spreadsheet_id = self.config.spreadsheet_id

        if (
            not refresh
            and spreadsheet_id in _WORKBOOK_METADATA_CACHE
        ):
            return _WORKBOOK_METADATA_CACHE[spreadsheet_id]

        metadata = (
            self.service.spreadsheets()
            .get(
                spreadsheetId=spreadsheet_id,
                fields=(
                    "sheets(properties(sheetId,title,"
                    "gridProperties(rowCount,columnCount)),"
                    "protectedRanges(protectedRangeId,description))"
                ),
            )
            .execute(
                num_retries=GOOGLE_API_NUM_RETRIES
            )
        )

        _WORKBOOK_METADATA_CACHE[spreadsheet_id] = metadata
        return metadata

    def _invalidate_workbook_metadata(self) -> None:
        _WORKBOOK_METADATA_CACHE.pop(
            self.config.spreadsheet_id,
            None,
        )

    def _invalidate_tab_values(self) -> None:
        _TAB_VALUES_CACHE.pop(
            self._cache_key(),
            None,
        )

    def _set_cached_values(
        self,
        values: list[list[Any]],
    ) -> None:
        _TAB_VALUES_CACHE[self._cache_key()] = values

    def _ensure_reason_only_protection(
        self,
        sheet_id: int,
    ) -> None:
        """Protect a regional tab once, leaving only Reason data cells editable."""

        if not self.config.protect_reason_only:
            return

        metadata = self._get_workbook_metadata()

        for sheet in metadata.get("sheets", []):
            properties = sheet.get("properties", {})
            if int(properties.get("sheetId", -1)) != sheet_id:
                continue

            for protected_range in sheet.get("protectedRanges", []):
                if (
                    protected_range.get("description")
                    == PROTECTION_DESCRIPTION
                ):
                    # Already protected correctly from a prior run.
                    return

        reason_index = VISIBLE_COLUMNS.index("Reason")

        self.service.spreadsheets().batchUpdate(
            spreadsheetId=self.config.spreadsheet_id,
            body={
                "requests": [
                    {
                        "addProtectedRange": {
                            "protectedRange": {
                                "range": {"sheetId": sheet_id},
                                "description": PROTECTION_DESCRIPTION,
                                "warningOnly": False,
                                "editors": {
                                    "users": [self._service_account_email()],
                                    "domainUsersCanEdit": False,
                                },
                                "unprotectedRanges": [
                                    {
                                        "sheetId": sheet_id,
                                        "startRowIndex": 1,
                                        "startColumnIndex": reason_index,
                                        "endColumnIndex": reason_index + 1,
                                    }
                                ],
                            }
                        }
                    }
                ]
            },
        ).execute(
            num_retries=GOOGLE_API_NUM_RETRIES
        )

        self._invalidate_workbook_metadata()

    def _get_sheet_properties(
        self,
        refresh: bool = False,
    ) -> dict[str, Any] | None:
        metadata = self._get_workbook_metadata(refresh=refresh)

        for sheet in metadata.get("sheets", []):
            properties = sheet.get("properties", {})
            if properties.get("title") == self.config.worksheet_title:
                return properties

        return None

    def ensure_schema(self) -> int:
        """Create/validate a tab once per Python process.

        The first values read is retained and reused by Reason detection,
        history evaluation, and final sync.
        """

        cache_key = self._cache_key()
        cached_sheet_id = _SCHEMA_CACHE.get(cache_key)
        if cached_sheet_id is not None:
            return cached_sheet_id

        properties = self._get_sheet_properties()
        created = properties is None

        if created:
            response = (
                self.service.spreadsheets()
                .batchUpdate(
                    spreadsheetId=self.config.spreadsheet_id,
                    body={
                        "requests": [
                            {
                                "addSheet": {
                                    "properties": {
                                        "title": self.config.worksheet_title,
                                        "gridProperties": {
                                            "rowCount": 1000,
                                            "columnCount": len(ALL_COLUMNS),
                                            "frozenRowCount": 1,
                                        },
                                    }
                                }
                            }
                        ]
                    },
                )
                .execute(
                    num_retries=GOOGLE_API_NUM_RETRIES
                )
            )
            properties = response["replies"][0]["addSheet"]["properties"]
            self._invalidate_workbook_metadata()

        sheet_id = int(properties["sheetId"])
        current_column_count = int(
            properties.get("gridProperties", {}).get(
                "columnCount",
                len(ALL_COLUMNS),
            )
        )

        # Old tabs can physically have fewer columns than the current schema.
        # Expand first so the one full values read below is always a valid range.
        if current_column_count < len(ALL_COLUMNS):
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.config.spreadsheet_id,
                body={
                    "requests": [
                        {
                            "appendDimension": {
                                "sheetId": sheet_id,
                                "dimension": "COLUMNS",
                                "length": len(ALL_COLUMNS) - current_column_count,
                            }
                        }
                    ]
                },
            ).execute(
                num_retries=GOOGLE_API_NUM_RETRIES
            )
            current_column_count = len(ALL_COLUMNS)
            self._invalidate_workbook_metadata()

        values = self._read_all_values(
            ensure_schema=False
        )
        raw_headers = list(values[0]) if values else []
        is_blank = (
            not raw_headers
            or not any(str(value).strip() for value in raw_headers)
        )

        migrated = False
        if not is_blank:
            migrated = self._migrate_schema(
                sheet_id=sheet_id,
                existing_headers=raw_headers,
            )

            if migrated:
                # Rare one-time migration: refresh only this tab once.
                values = self._read_all_values(
                    ensure_schema=False,
                    refresh=True,
                )
                properties = self._get_sheet_properties(refresh=True) or properties

        title = _quote_sheet_title(self.config.worksheet_title)
        end_col = _column_to_a1(len(ALL_COLUMNS))
        header_range = f"{title}!A1:{end_col}1"

        if is_blank:
            self.service.spreadsheets().values().update(
                spreadsheetId=self.config.spreadsheet_id,
                range=header_range,
                valueInputOption="RAW",
                body={"values": [ALL_COLUMNS]},
            ).execute(
                num_retries=GOOGLE_API_NUM_RETRIES
            )
            values = [list(ALL_COLUMNS)]
            self._set_cached_values(values)

        elif not migrated:
            actual = list(raw_headers)
            actual += [""] * (len(ALL_COLUMNS) - len(actual))
            actual = actual[: len(ALL_COLUMNS)]
            if actual != ALL_COLUMNS:
                raise GoogleSheetsTrackingValidationError(
                    "Existing Google Sheet headers do not match "
                    "the expected schema in tab "
                    f"{self.config.worksheet_title!r}. "
                    "No data was overwritten."
                )

        # Stable tabs already have the desired formatting. Avoid repeat writes.
        if created or migrated or is_blank:
            self.service.spreadsheets().batchUpdate(
                spreadsheetId=self.config.spreadsheet_id,
                body={
                    "requests": [
                        {
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": sheet_id,
                                    "gridProperties": {"frozenRowCount": 1},
                                },
                                "fields": "gridProperties.frozenRowCount",
                            }
                        },
                        {
                            "repeatCell": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "startRowIndex": 0,
                                    "endRowIndex": 1,
                                    "startColumnIndex": 0,
                                    "endColumnIndex": len(ALL_COLUMNS),
                                },
                                "cell": {
                                    "userEnteredFormat": {
                                        "textFormat": {"bold": True}
                                    }
                                },
                                "fields": "userEnteredFormat.textFormat.bold",
                            }
                        },
                        {
                            "updateDimensionProperties": {
                                "range": {
                                    "sheetId": sheet_id,
                                    "dimension": "COLUMNS",
                                    "startIndex": len(VISIBLE_COLUMNS),
                                    "endIndex": len(ALL_COLUMNS),
                                },
                                "properties": {"hiddenByUser": True},
                                "fields": "hiddenByUser",
                            }
                        },
                    ]
                },
            ).execute(
                num_retries=GOOGLE_API_NUM_RETRIES
            )

        self._ensure_reason_only_protection(sheet_id=sheet_id)
        _SCHEMA_CACHE[cache_key] = sheet_id
        return sheet_id

    def _read_all_values(
        self,
        ensure_schema: bool = True,
        refresh: bool = False,
    ) -> list[list[Any]]:
        """Read a tab once and reuse it for the rest of this Python run."""

        if ensure_schema:
            self.ensure_schema()

        cache_key = self._cache_key()
        if not refresh and cache_key in _TAB_VALUES_CACHE:
            return _TAB_VALUES_CACHE[cache_key]

        title = _quote_sheet_title(self.config.worksheet_title)
        end_col = _column_to_a1(len(ALL_COLUMNS))
        values = (
            self.service.spreadsheets()
            .values()
            .get(
                spreadsheetId=self.config.spreadsheet_id,
                range=f"{title}!A:{end_col}",
            )
            .execute(num_retries=GOOGLE_API_NUM_RETRIES)
            .get("values", [])
        )
        self._set_cached_values(values)
        return values

    def stamp_new_reason_timestamps(self) -> int:
        """Stamp Reason_Filled_At once when Python first detects a Reason."""

        values = self._read_all_values()
        if not values:
            return 0

        reason_index = ALL_COLUMNS.index("Reason")
        stamp_index = ALL_COLUMNS.index("Reason_Filled_At")
        updated_at_index = ALL_COLUMNS.index("Updated_At")
        title = _quote_sheet_title(self.config.worksheet_title)
        stamp_col = _column_to_a1(stamp_index + 1)
        updated_at_col = _column_to_a1(updated_at_index + 1)
        now_text = _cambodia_now_iso()
        updates = []
        changed = 0

        for sheet_row, raw_row in enumerate(values[1:], start=2):
            padded = list(raw_row) + [""] * (len(ALL_COLUMNS) - len(raw_row))
            reason = str(padded[reason_index]).strip()
            existing_stamp = str(padded[stamp_index]).strip()
            if reason and not existing_stamp:
                updates.extend([
                    {
                        "range": f"{title}!{stamp_col}{sheet_row}",
                        "values": [[now_text]],
                    },
                    {
                        "range": f"{title}!{updated_at_col}{sheet_row}",
                        "values": [[now_text]],
                    },
                ])
                changed += 1

        if updates:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.config.spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates,
                },
            ).execute(num_retries=GOOGLE_API_NUM_RETRIES)

            # Apply the same timestamp changes to the cached rows so the
            # immediate policy read uses memory instead of another API call.
            for raw_row in values[1:]:
                while len(raw_row) < len(ALL_COLUMNS):
                    raw_row.append("")
                reason = str(raw_row[reason_index]).strip()
                existing_stamp = str(raw_row[stamp_index]).strip()
                if reason and not existing_stamp:
                    raw_row[stamp_index] = now_text
                    raw_row[updated_at_index] = now_text
            self._set_cached_values(values)

        return changed

    def update_existing_system_fields(
        self,
        tracking_dataset: pd.DataFrame,
        existing_row_map: Mapping[str, int],
    ) -> int:
        """Refresh system columns while preserving Reason and reminder metadata."""

        if tracking_dataset.empty:
            return 0

        title = _quote_sheet_title(self.config.worksheet_title)
        system_columns = [
            "Customer ID",
            "Customer Name",
            "Customer Type",
            "Status",
            "Last",
            "Last Purchase Date",
            "Activity",
            "Product",
            "Region",
            "Province",
            "Days Since Last Purchase",
            "Probability",
        ]
        updates = []
        changed_rows = 0
        now_text = _cambodia_now_iso()
        updated_at_col = _column_to_a1(ALL_COLUMNS.index("Updated_At") + 1)

        for _, row in tracking_dataset.iterrows():
            alert_id = str(row.get("Alert_ID", "")).strip()
            sheet_row = existing_row_map.get(alert_id)
            if sheet_row is None:
                continue

            for column in system_columns:
                col = _column_to_a1(ALL_COLUMNS.index(column) + 1)
                updates.append({
                    "range": f"{title}!{col}{sheet_row}",
                    "values": [[_clean_cell_value(row.get(column, ""))]],
                })

            updates.append({
                "range": f"{title}!{updated_at_col}{sheet_row}",
                "values": [[now_text]],
            })
            changed_rows += 1

        if updates:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.config.spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": updates,
                },
            ).execute(num_retries=GOOGLE_API_NUM_RETRIES)

            cached_values = self._read_all_values()
            for _, row in tracking_dataset.iterrows():
                alert_id = str(row.get("Alert_ID", "")).strip()
                sheet_row = existing_row_map.get(alert_id)
                if sheet_row is None:
                    continue
                while len(cached_values) < sheet_row:
                    cached_values.append([])
                raw_row = cached_values[sheet_row - 1]
                while len(raw_row) < len(ALL_COLUMNS):
                    raw_row.append("")
                for column in system_columns:
                    raw_row[ALL_COLUMNS.index(column)] = _clean_cell_value(
                        row.get(column, "")
                    )
                raw_row[ALL_COLUMNS.index("Updated_At")] = now_text
            self._set_cached_values(cached_values)

        return changed_rows

    def _existing_alert_rows(self) -> dict[str, int]:
        values = self._read_all_values()

        if not values:
            return {}

        headers = list(values[0])
        headers += [""] * (len(ALL_COLUMNS) - len(headers))

        if headers[: len(ALL_COLUMNS)] != ALL_COLUMNS:
            raise GoogleSheetsTrackingValidationError(
                "Google Sheet headers changed after schema validation."
            )

        alert_id_index = ALL_COLUMNS.index("Alert_ID")
        row_map: dict[str, int] = {}

        for sheet_row, row in enumerate(values[1:], start=2):
            if alert_id_index >= len(row):
                continue

            alert_id = str(row[alert_id_index]).strip()

            if not alert_id:
                continue

            if alert_id in row_map:
                raise GoogleSheetsTrackingValidationError(
                    "Duplicate Alert_ID already exists in Google Sheets: "
                    f"{alert_id}"
                )

            row_map[alert_id] = sheet_row

        return row_map

    def _build_follow_up_link(
        self,
        sheet_id: int,
        sheet_rows: Sequence[int],
    ) -> str:
        base = (
            "https://docs.google.com/spreadsheets/d/"
            f"{self.config.spreadsheet_id}/edit#gid={sheet_id}"
        )

        if not sheet_rows:
            return base

        rows = sorted(set(int(value) for value in sheet_rows))
        first_row, last_row = rows[0], rows[-1]

        if rows != list(range(first_row, last_row + 1)):
            return base

        visible_end = _column_to_a1(len(VISIBLE_COLUMNS))

        return (
            f"{base}&range=A{first_row}:"
            f"{visible_end}{last_row}"
        )

    def sync_dataset(self, tracking_dataset: pd.DataFrame) -> dict[str, str]:
        """Append new Alert_IDs and return one link per province."""

        missing = [
            column
            for column in ALL_COLUMNS
            if column not in tracking_dataset.columns
        ]

        if missing:
            raise GoogleSheetsTrackingValidationError(
                f"Tracking dataset is missing columns: {missing}"
            )

        if tracking_dataset.empty:
            return {}

        if tracking_dataset["Alert_ID"].astype("string").duplicated().any():
            raise GoogleSheetsTrackingValidationError(
                "Tracking dataset contains duplicate Alert_ID values."
            )

        sheet_id = self.ensure_schema()
        existing_rows = self._existing_alert_rows()

        self.update_existing_system_fields(
            tracking_dataset=tracking_dataset,
            existing_row_map=existing_rows,
        )

        new_data = tracking_dataset[
            ~tracking_dataset["Alert_ID"]
            .astype("string")
            .isin(existing_rows.keys())
        ].copy()

        if not new_data.empty:
            matrix = [
                [
                    _clean_cell_value(row[column])
                    for column in ALL_COLUMNS
                ]
                for _, row in new_data.iterrows()
            ]

            title = _quote_sheet_title(self.config.worksheet_title)
            end_col = _column_to_a1(len(ALL_COLUMNS))

            cached_values = self._read_all_values()
            first_new_sheet_row = len(cached_values) + 1

            self.service.spreadsheets().values().append(
                spreadsheetId=self.config.spreadsheet_id,
                range=f"{title}!A:{end_col}",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": matrix},
            ).execute(num_retries=GOOGLE_API_NUM_RETRIES)

            for offset, (_, new_row) in enumerate(new_data.iterrows()):
                alert_id = str(new_row["Alert_ID"]).strip()
                existing_rows[alert_id] = first_new_sheet_row + offset

            cached_values.extend([list(row) for row in matrix])
            self._set_cached_values(cached_values)

        links: dict[str, str] = {}

        for province, province_data in tracking_dataset.groupby(
            "Province",
            sort=False,
            dropna=False,
        ):
            province_name = str(province).strip()
            row_numbers: list[int] = []

            for alert_id in province_data["Alert_ID"].astype(str).tolist():
                sheet_row = existing_rows.get(alert_id)

                if sheet_row is None:
                    raise GoogleSheetsTrackingError(
                        "Alert_ID not found after Google Sheets sync: "
                        f"{alert_id}"
                    )

                row_numbers.append(sheet_row)

            links[province_name] = self._build_follow_up_link(
                sheet_id=sheet_id,
                sheet_rows=row_numbers,
            )

        return links

    def read_all(self) -> pd.DataFrame:
        values = self._read_all_values()

        if not values:
            return pd.DataFrame(columns=ALL_COLUMNS)

        rows: list[dict[str, Any]] = []

        for raw_row in values[1:]:
            padded = list(raw_row) + [""] * (
                len(ALL_COLUMNS) - len(raw_row)
            )
            record = dict(
                zip(
                    ALL_COLUMNS,
                    padded[: len(ALL_COLUMNS)],
                )
            )

            if str(record.get("Alert_ID", "")).strip():
                rows.append(record)

        return pd.DataFrame(rows, columns=ALL_COLUMNS)

    def read_salesman_responses(
        self,
        only_with_reason: bool = True,
    ) -> pd.DataFrame:
        """Read Reason responses keyed by Alert_ID from this worksheet."""

        data = self.read_all()

        if only_with_reason and not data.empty:
            data = data[
                data["Reason"]
                .astype("string")
                .fillna("")
                .str.strip()
                != ""
            ].copy()

        columns = [
            "Alert_ID",
            "Alert Date",
            "Product",
            "Region",
            "Province",
            "Customer ID",
            "Customer Name",
            "Reason",
            "Activity",
            "Last Purchase Date",
        ]

        return data[columns].copy().reset_index(drop=True)

    def update_activity_by_alert_id(
        self,
        evaluations: Iterable[Mapping[str, Any]],
    ) -> int:
        """Write system-derived Activity/Last Purchase Date by Alert_ID."""

        evaluations = list(evaluations)
        self.ensure_schema()
        row_map = self._existing_alert_rows()
        title = _quote_sheet_title(self.config.worksheet_title)
        activity_col = _column_to_a1(ALL_COLUMNS.index("Activity") + 1)
        purchase_col = _column_to_a1(
            ALL_COLUMNS.index("Last Purchase Date") + 1
        )
        updated_at_col = _column_to_a1(ALL_COLUMNS.index("Updated_At") + 1)
        now_text = pd.Timestamp.now(
            tz=ZoneInfo("Asia/Phnom_Penh")
        ).isoformat()
        value_ranges: list[dict[str, Any]] = []
        changed_rows = 0

        for evaluation in evaluations:
            alert_id = str(evaluation.get("Alert_ID", "")).strip()

            if not alert_id:
                raise GoogleSheetsTrackingValidationError(
                    "Evaluation is missing Alert_ID."
                )

            sheet_row = row_map.get(alert_id)

            if sheet_row is None:
                raise GoogleSheetsTrackingValidationError(
                    "Evaluation Alert_ID does not exist in Google Sheets: "
                    f"{alert_id}"
                )

            changed = False

            if "Activity" in evaluation:
                activity = str(evaluation.get("Activity", "")).strip()

                if activity not in {"", "No Action", "Action Taken"}:
                    raise GoogleSheetsTrackingValidationError(
                        f"Unsupported Activity value for {alert_id}: "
                        f"{activity!r}"
                    )

                value_ranges.append(
                    {
                        "range": f"{title}!{activity_col}{sheet_row}",
                        "values": [[activity]],
                    }
                )
                changed = True

            if (
                "Last_Purchase_Date" in evaluation
                or "Last Purchase Date" in evaluation
            ):
                raw_date = evaluation.get(
                    "Last_Purchase_Date",
                    evaluation.get("Last Purchase Date", ""),
                )

                value_ranges.append(
                    {
                        "range": f"{title}!{purchase_col}{sheet_row}",
                        "values": [[_to_iso_date_text(raw_date)]],
                    }
                )
                changed = True

            if changed:
                value_ranges.append(
                    {
                        "range": f"{title}!{updated_at_col}{sheet_row}",
                        "values": [[now_text]],
                    }
                )
                changed_rows += 1

        if value_ranges:
            self.service.spreadsheets().values().batchUpdate(
                spreadsheetId=self.config.spreadsheet_id,
                body={
                    "valueInputOption": "RAW",
                    "data": value_ranges,
                },
            ).execute(num_retries=GOOGLE_API_NUM_RETRIES)

            cached_values = self._read_all_values()
            for evaluation in evaluations:
                alert_id = str(evaluation.get("Alert_ID", "")).strip()
                sheet_row = row_map.get(alert_id)
                if sheet_row is None:
                    continue
                while len(cached_values) < sheet_row:
                    cached_values.append([])
                raw_row = cached_values[sheet_row - 1]
                while len(raw_row) < len(ALL_COLUMNS):
                    raw_row.append("")
                if "Activity" in evaluation:
                    raw_row[ALL_COLUMNS.index("Activity")] = str(
                        evaluation.get("Activity", "")
                    ).strip()
                if (
                    "Last_Purchase_Date" in evaluation
                    or "Last Purchase Date" in evaluation
                ):
                    raw_date = evaluation.get(
                        "Last_Purchase_Date",
                        evaluation.get("Last Purchase Date", ""),
                    )
                    raw_row[ALL_COLUMNS.index("Last Purchase Date")] = (
                        _to_iso_date_text(raw_date)
                    )
                raw_row[ALL_COLUMNS.index("Updated_At")] = now_text
            self._set_cached_values(cached_values)

        return changed_rows


def get_google_cache_stats() -> dict[str, int]:
    """Return cache sizes for diagnostics during preview testing."""

    return {
        "services": len(_SERVICE_CACHE),
        "workbooks": len(_WORKBOOK_METADATA_CACHE),
        "tabs_with_values": len(_TAB_VALUES_CACHE),
        "schemas": len(_SCHEMA_CACHE),
    }


# ============================================
# REASON / 12-DAY REMINDER POLICY
# ============================================

def _decide_reason_reminder_action(
    activity: str,
    follow_up_state: Mapping[str, Any] | None,
    today: pd.Timestamp,
    reminder_days: int = REASON_REMINDER_DAYS,
) -> tuple[str, int]:
    """Return the next alert decision and Reminder_Count.

    The state describes only the current open online alert cycle (rows after
    the most recent Action Taken event).
    """

    if str(activity).strip() == "Action Taken":
        return "skip_action_taken", 0

    if not follow_up_state or not follow_up_state.get("has_open_events"):
        return "alert_initial", 0

    max_count = pd.to_numeric(
        follow_up_state.get("max_reminder_count", 0),
        errors="coerce",
    )
    if pd.isna(max_count):
        max_count = 0
    max_count = int(max_count)

    reason_event = follow_up_state.get("latest_reason_event")

    if not reason_event:
        # The salesman has not acknowledged the current cycle yet. Alert again
        # today. A new date means a new Alert_ID, while rerunning the same day
        # remains idempotent because Alert_ID is deterministic.
        return "alert_unanswered", max_count

    age_days = _reason_age_days(
        reason_event.get("Reason_Filled_At", ""),
        today=today,
    )

    if age_days is None or age_days < reminder_days:
        return "suppress_reason_wait", max_count

    reason_count = pd.to_numeric(
        reason_event.get("Reminder_Count", 0),
        errors="coerce",
    )
    if pd.isna(reason_count):
        reason_count = 0
    reason_count = int(reason_count)

    if max_count > reason_count:
        # A 12-day reminder event has already been created after that Reason,
        # but the salesman has not answered the new reminder yet. Keep alerting
        # without incrementing Reminder_Count again.
        return "alert_unanswered", max_count

    return "alert_reason_reminder", max_count + 1


def apply_reason_reminder_policy(
    alert_customers: pd.DataFrame,
    today_tracking: pd.DataFrame,
    product: str,
    province_regions: Mapping[str, str],
    reminder_days: int = REASON_REMINDER_DAYS,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Apply Reason acknowledgement/reminder logic after CRT/TPP qualification."""

    if reminder_days <= 0:
        raise GoogleSheetsTrackingValidationError(
            "reminder_days must be greater than zero."
        )

    if alert_customers is None:
        raise GoogleSheetsTrackingValidationError(
            "alert_customers cannot be None."
        )

    summary = {
        "business_candidates": int(len(alert_customers)),
        "action_taken_suppressed": 0,
        "reason_wait_suppressed": 0,
        "initial_alerts": 0,
        "unanswered_realerts": 0,
        "12_day_reminders": 0,
        "final_alerts": 0,
    }

    if alert_customers.empty:
        return alert_customers.copy(), summary

    required_tracking = [
        "customer_id",
        "activity",
        "latest_purchase_date",
    ]
    missing = [
        column
        for column in required_tracking
        if column not in today_tracking.columns
    ]
    if missing:
        raise GoogleSheetsTrackingValidationError(
            "today_tracking is missing columns required by the Reason "
            f"reminder policy: {missing}"
        )

    product_code = _normalize_product(product)
    today = _cambodia_today()

    activity_data = today_tracking[required_tracking].copy()
    activity_data["customer_id"] = (
        activity_data["customer_id"].map(_normalize_customer_id)
    )
    activity_data = activity_data.drop_duplicates(
        subset=["customer_id"],
        keep="last",
    )
    activity_lookup = {
        str(row["customer_id"]): row
        for _, row in activity_data.iterrows()
    }

    regional_spreadsheets = get_configured_regional_spreadsheets()
    service_account_file = get_service_account_file()
    latest_by_province_customer = {}

    candidate_provinces = set(
        alert_customers["province"]
        .astype("string")
        .str.strip()
        .dropna()
        .tolist()
    )

    action_taken_provinces = set(
        today_tracking.loc[
            today_tracking["activity"]
            .astype("string")
            .str.strip()
            == "Action Taken",
            "province",
        ]
        .astype("string")
        .str.strip()
        .dropna()
        .tolist()
    ) if "province" in today_tracking.columns else set()

    provinces = sorted(
        candidate_provinces
        | action_taken_provinces
    )

    for province in provinces:
        province_name = str(province).strip()
        region_name = str(
            province_regions.get(province_name, "")
        ).strip().upper()
        spreadsheet_id = regional_spreadsheets.get(region_name)
        if not spreadsheet_id:
            continue

        tracker = GoogleSheetsAlertTracker(
            GoogleSheetsTrackingConfig(
                spreadsheet_id=spreadsheet_id,
                service_account_file=service_account_file,
                worksheet_title=_regional_tab_title(
                    product_code,
                    province_name,
                ),
                protect_reason_only=True,
            )
        )

        stamped = tracker.stamp_new_reason_timestamps()
        if stamped:
            print(
                f"{product_code} | {province_name}: "
                f"stamped {stamped:,} new Reason timestamp(s)."
            )

        history = tracker.read_all()
        if history.empty:
            continue

        history["Customer ID"] = history["Customer ID"].map(
            _normalize_customer_id
        )
        history["_alert_date_sort"] = pd.to_datetime(
            history["Alert Date"],
            errors="coerce",
        )
        history["_row_order"] = range(len(history))
        latest_rows = (
            history
            .sort_values(
                ["_alert_date_sort", "_row_order"],
                kind="stable",
            )
            .groupby("Customer ID", dropna=False)
            .tail(1)
        )

        activity_updates = []
        for _, event in latest_rows.iterrows():
            customer_id = _normalize_customer_id(event["Customer ID"])
            current_tracking = activity_lookup.get(customer_id)
            if current_tracking is None:
                continue
            if str(current_tracking["activity"]).strip() != "Action Taken":
                continue
            alert_id = str(event.get("Alert_ID", "")).strip()
            if not alert_id:
                continue
            activity_updates.append({
                "Alert_ID": alert_id,
                "Activity": "Action Taken",
                "Last_Purchase_Date": current_tracking["latest_purchase_date"],
            })

        if activity_updates:
            tracker.update_activity_by_alert_id(activity_updates)

        for customer_id, customer_history in history.groupby(
            "Customer ID",
            dropna=False,
            sort=False,
        ):
            customer_id = _normalize_customer_id(customer_id)
            ordered = customer_history.sort_values(
                ["_alert_date_sort", "_row_order"],
                kind="stable",
            ).copy()

            action_mask = (
                ordered["Activity"]
                .astype("string")
                .fillna("")
                .str.strip()
                == "Action Taken"
            )

            if action_mask.any():
                last_action_position = max(
                    position
                    for position, is_action
                    in enumerate(action_mask.tolist())
                    if is_action
                )
                open_cycle = ordered.iloc[
                    last_action_position + 1:
                ].copy()
            else:
                open_cycle = ordered.copy()

            if open_cycle.empty:
                latest_by_province_customer[
                    (province_name, customer_id)
                ] = {
                    "has_open_events": False,
                    "latest_reason_event": None,
                    "max_reminder_count": 0,
                }
                continue

            reason_mask = (
                open_cycle["Reason"]
                .astype("string")
                .fillna("")
                .str.strip()
                != ""
            )

            latest_reason_event = None
            if reason_mask.any():
                latest_reason_event = (
                    open_cycle.loc[reason_mask]
                    .tail(1)
                    .iloc[0]
                    .to_dict()
                )

            reminder_counts = pd.to_numeric(
                open_cycle["Reminder_Count"],
                errors="coerce",
            ).fillna(0)

            latest_by_province_customer[
                (province_name, customer_id)
            ] = {
                "has_open_events": True,
                "latest_reason_event": latest_reason_event,
                "max_reminder_count": int(
                    reminder_counts.max()
                ),
            }

    rows_to_alert = []

    for _, source_row in alert_customers.iterrows():
        row = source_row.copy()
        customer_id = _normalize_customer_id(row["customer_id"])
        province_name = str(row["province"]).strip()
        current_tracking = activity_lookup.get(customer_id)
        activity = (
            str(current_tracking["activity"]).strip()
            if current_tracking is not None
            else "No Action"
        )
        follow_up_state = latest_by_province_customer.get(
            (province_name, customer_id)
        )
        decision, reminder_count = _decide_reason_reminder_action(
            activity=activity,
            follow_up_state=follow_up_state,
            today=today,
            reminder_days=reminder_days,
        )

        if decision == "skip_action_taken":
            summary["action_taken_suppressed"] += 1
            continue

        if decision == "suppress_reason_wait":
            summary["reason_wait_suppressed"] += 1
            continue

        if decision == "alert_initial":
            summary["initial_alerts"] += 1

        elif decision == "alert_unanswered":
            summary["unanswered_realerts"] += 1

        elif decision == "alert_reason_reminder":
            summary["12_day_reminders"] += 1

        row["_reminder_count"] = reminder_count
        rows_to_alert.append(row)

    if rows_to_alert:
        filtered = pd.DataFrame(rows_to_alert).reset_index(drop=True)
    else:
        filtered = alert_customers.iloc[0:0].copy()

    summary["final_alerts"] = int(len(filtered))
    return filtered, summary


# ============================================
# MASTER + REGIONAL ORCHESTRATION
# ============================================

def _validate_single_product(tracking_dataset: pd.DataFrame) -> str:
    products = sorted(
        set(
            tracking_dataset["Product"]
            .astype("string")
            .fillna("")
            .str.strip()
            .str.upper()
            .tolist()
        )
        - {""}
    )

    if len(products) != 1:
        raise GoogleSheetsTrackingValidationError(
            "sync_tracking_dataset expects one product per pipeline run. "
            f"Found: {products}"
        )

    return products[0]


def sync_tracking_dataset(
    tracking_dataset: pd.DataFrame,
    config: GoogleSheetsTrackingConfig | None = None,
) -> dict[str, str]:
    """Sync configured Google tracking destinations.

    The regional salesman workbooks are the operational requirement.

    The private MASTER Alert_Data is optional:
    - If ``config`` is passed, that MASTER config is used.
    - Otherwise ``GOOGLE_SHEETS_WRITE_MASTER`` controls whether MASTER is used.
    - When MASTER is disabled, regional R1-R6 writes continue normally.

    Returns
    -------
    dict[str, str]
        Province -> province/product regional tab link.
    """

    if tracking_dataset is None:
        raise GoogleSheetsTrackingValidationError(
            "tracking_dataset cannot be None."
        )

    if tracking_dataset.empty:
        return {}

    missing = [
        column
        for column in ALL_COLUMNS
        if column not in tracking_dataset.columns
    ]

    if missing:
        raise GoogleSheetsTrackingValidationError(
            f"Tracking dataset is missing columns: {missing}"
        )

    product = _validate_single_product(
        tracking_dataset
    )

    # ------------------------------------------------
    # Credentials are required for regional workbooks
    # even when the MASTER is intentionally disabled.
    # ------------------------------------------------
    if config is not None:
        service_account_file = (
            config.service_account_file
        )
        master_config = config
    else:
        service_account_file = (
            get_service_account_file()
        )
        master_config = (
            get_optional_master_config()
        )

    # ----------------------------------------
    # 1) Optional private centralized history
    # ----------------------------------------
    if master_config is None:

        print(
            "\nMASTER Google Sheet sync skipped."
        )

        print(
            "Regional Google Sheets will continue."
        )

    else:

        print(
            "\nSyncing private MASTER Alert_Data..."
        )

        master_tracker = (
            GoogleSheetsAlertTracker(
                master_config
            )
        )

        master_tracker.sync_dataset(
            tracking_dataset
        )

        print(
            "MASTER Alert_Data sync complete."
        )

    # ----------------------------------------
    # 2) Salesman-facing regional workbooks
    # ----------------------------------------
    regional_spreadsheets = (
        get_configured_regional_spreadsheets()
    )

    if not regional_spreadsheets:
        raise GoogleSheetsTrackingValidationError(
            "No regional Google spreadsheets are configured. "
            "Add at least one GOOGLE_SHEETS_R#_SPREADSHEET_ID "
            "to .env."
        )

    follow_up_links: dict[
        str,
        str,
    ] = {}

    for (
        region,
        province,
    ), province_data in tracking_dataset.groupby(
        [
            "Region",
            "Province",
        ],
        sort=False,
        dropna=False,
    ):

        region_name = str(
            region
        ).strip().upper()

        province_name = str(
            province
        ).strip()

        spreadsheet_id = (
            regional_spreadsheets.get(
                region_name
            )
        )

        if not spreadsheet_id:

            print(
                "Google regional workbook not configured; "
                f"skipping {product} | "
                f"{region_name} | "
                f"{province_name}"
            )

            continue

        tab_title = (
            _regional_tab_title(
                product,
                province_name,
            )
        )

        regional_config = (
            GoogleSheetsTrackingConfig(
                spreadsheet_id=(
                    spreadsheet_id
                ),
                service_account_file=(
                    service_account_file
                ),
                worksheet_title=(
                    tab_title
                ),
                protect_reason_only=True,
            )
        )

        print(
            "Syncing regional Google Sheet: "
            f"{product} | "
            f"{region_name} | "
            f"{province_name}"
        )

        regional_tracker = (
            GoogleSheetsAlertTracker(
                regional_config
            )
        )

        province_links = (
            regional_tracker.sync_dataset(
                province_data.copy()
            )
        )

        link = (
            province_links.get(
                province_name
            )
        )

        if not link:
            raise GoogleSheetsTrackingError(
                "Regional Google Sheet did not "
                "return a follow-up link for "
                f"{product} | "
                f"{region_name} | "
                f"{province_name}"
            )

        follow_up_links[
            province_name
        ] = link

    return follow_up_links



def read_salesman_responses(
    only_with_reason: bool = True,
    config: GoogleSheetsTrackingConfig | None = None,
) -> pd.DataFrame:
    """Read responses from the private MASTER Alert_Data worksheet.

    This operation requires MASTER access. Regional-only testing can run
    without it, but this master reader cannot.
    """

    master_config = (
        config
        or
        get_optional_master_config()
    )

    if master_config is None:
        raise GoogleSheetsTrackingValidationError(
            "MASTER Google Sheet is currently disabled or not configured. "
            "Set GOOGLE_SHEETS_WRITE_MASTER=true and restore service-account "
            "access before using read_salesman_responses()."
        )

    tracker = GoogleSheetsAlertTracker(
        config=master_config
    )

    return tracker.read_salesman_responses(
        only_with_reason=only_with_reason
    )