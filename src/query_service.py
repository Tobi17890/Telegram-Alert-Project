"""Functions for loading and executing SQL files."""

from pathlib import Path

import pandas as pd

from src.config import SQL_DIRECTORY


def load_sql_query(sql_filename: str) -> str:
    """
    Read and return SQL text from the project's sql directory.
    """

    sql_file_path = SQL_DIRECTORY / sql_filename

    if not sql_file_path.exists():
        raise FileNotFoundError(
            f"SQL file does not exist: {sql_file_path}"
        )

    return sql_file_path.read_text(encoding="utf-8")


def fetch_dataframe(
    connection,
    sql_filename: str
) -> pd.DataFrame:
    """
    Execute a SELECT query from a SQL file and return a DataFrame.
    """

    query = load_sql_query(sql_filename)
    cursor = connection.cursor()

    try:
        cursor.execute(query)

        if cursor.description is None:
            raise RuntimeError(
                f"The query in {sql_filename} did not return any columns."
            )

        columns = [
            column[0]
            for column in cursor.description
        ]

        rows = cursor.fetchall()

        dataframe = pd.DataFrame(
            [tuple(row) for row in rows],
            columns=columns
        )

        return dataframe

    finally:
        cursor.close()


"""Functions for reading and executing SQL query files."""

from pathlib import Path

import pandas as pd

from src.config import SQL_DIRECTORY


def load_sql_query(sql_filename: str) -> str:
    """
    Read SQL text from the project's SQL directory.
    """

    sql_file_path = SQL_DIRECTORY / sql_filename

    if not sql_file_path.exists():
        raise FileNotFoundError(
            f"SQL file does not exist: {sql_file_path}"
        )

    return sql_file_path.read_text(encoding="utf-8")


def fetch_dataframe(
    connection,
    sql_filename: str
) -> pd.DataFrame:
    """
    Execute a SQL query and return all results as a DataFrame.
    """

    query = load_sql_query(sql_filename)
    cursor = connection.cursor()

    try:
        cursor.execute(query)

        if cursor.description is None:
            raise RuntimeError(
                f"The query in {sql_filename} returned no columns."
            )

        columns = [
            column[0]
            for column in cursor.description
        ]

        rows = cursor.fetchall()

        return pd.DataFrame(
            [tuple(row) for row in rows],
            columns=columns
        )

    finally:
        cursor.close()


def fetch_dataframe_in_batches(
    connection,
    sql_filename: str,
    batch_size: int = 20_000
) -> pd.DataFrame:
    """
    Fetch a large SQL result in batches.

    The complete result is still returned as one DataFrame,
    but rows are downloaded from SQL Server in smaller batches.
    """

    if batch_size <= 0:
        raise ValueError("batch_size must be greater than zero.")

    query = load_sql_query(sql_filename)
    cursor = connection.cursor()

    dataframes: list[pd.DataFrame] = []
    total_rows = 0

    try:
        cursor.execute(query)

        if cursor.description is None:
            raise RuntimeError(
                f"The query in {sql_filename} returned no columns."
            )

        columns = [
            column[0]
            for column in cursor.description
        ]

        while True:
            rows = cursor.fetchmany(batch_size)

            if not rows:
                break

            batch_dataframe = pd.DataFrame(
                [tuple(row) for row in rows],
                columns=columns
            )

            dataframes.append(batch_dataframe)

            total_rows += len(batch_dataframe)

            print(
                f"Fetched {total_rows:,} rows..."
            )

    finally:
        cursor.close()

    if not dataframes:
        return pd.DataFrame(columns=columns)

    return pd.concat(
        dataframes,
        ignore_index=True
    )