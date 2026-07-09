import pandas as pd
from pathlib import Path


def load_excel_sheet(file_path: str | Path, sheet_name: str) -> pd.DataFrame:
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"Excel file not found: {file_path}")

    return pd.read_excel(file_path, sheet_name=sheet_name)


def filter_last_one_year(df: pd.DataFrame, date_column: str):
    df = df.copy()

    df[date_column] = pd.to_datetime(
        df[date_column],
        errors="coerce",
        dayfirst=True
    )

    latest_date = df[date_column].max()

    if pd.isna(latest_date):
        raise ValueError(f"No valid date found in column: {date_column}")

    start_date = latest_date - pd.DateOffset(years=1)

    df_last_year = df[
        (df[date_column] >= start_date) &
        (df[date_column] <= latest_date)
    ].copy()

    return df_last_year, start_date, latest_date


def find_customer(
    df: pd.DataFrame,
    customer_column: str,
    customer_name: str,
    exact_match: bool = False
) -> pd.DataFrame:
    values = df[customer_column].astype(str).str.strip()

    if exact_match:
        mask = values.str.lower() == customer_name.strip().lower()
    else:
        mask = values.str.contains(
            customer_name,
            case=False,
            na=False,
            regex=False
        )

    return df.loc[mask].copy()