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