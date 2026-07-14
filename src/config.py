"""Application configuration."""

import os
from pathlib import Path

from dotenv import load_dotenv


# Extracting Data/
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Extracting Data/.env
ENV_FILE = PROJECT_ROOT / ".env"

# Extracting Data/sql/
SQL_DIRECTORY = PROJECT_ROOT / "sql"

# Load environment variables
load_dotenv(ENV_FILE)

SQL_CONNECTION_STRING = os.getenv("SQL_CONNECTION_STRING")

if not SQL_CONNECTION_STRING:
    raise RuntimeError(
        "SQL_CONNECTION_STRING was not found.\n"
        f"Check the environment file: {ENV_FILE}"
    )