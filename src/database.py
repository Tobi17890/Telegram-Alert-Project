"""SQL Server connection service."""

from mssql_python import connect

from src.config import SQL_CONNECTION_STRING


def get_database_connection():
    """
    Create and return an active SQL Server connection.

    The caller is responsible for closing the connection.
    """

    try:
        connection = connect(SQL_CONNECTION_STRING)
        print("Connected to SQL Server successfully.")

        return connection

    except Exception as error:
        print("Failed to connect to SQL Server.")
        print(error)
        raise