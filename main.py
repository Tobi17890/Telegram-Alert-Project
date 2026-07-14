"""Main entry point for the Telegram customer alert project."""

from src.database import get_database_connection
from src.query_service import fetch_dataframe


def main() -> None:
    """
    Test SQL Server connectivity and fetch a CRT sample.
    """

    connection = get_database_connection()

    try:
        df_crt = fetch_dataframe(
            connection=connection,
            sql_filename="crt_sample.sql"
        )

        print("\nCRT data sample:")
        print(df_crt.head())

        print(f"\nRows fetched: {len(df_crt):,}")
        print(f"Columns fetched: {len(df_crt.columns):,}")

    finally:
        connection.close()
        print("\nDatabase connection closed.")


if __name__ == "__main__":
    main()