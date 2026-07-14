import os
from pathlib import Path
from dotenv import load_dotenv, find_dotenv

# Function to get required environment variable, raises ValueError if not found
def get_required_env(name: str) -> str:
    value = os.getenv(name)

    if value is None or value.strip() == "":
        raise ValueError(f"Missing environment variable: {name}")

    return value

# Function to load settings from environment variables
def load_settings() -> dict:
    load_dotenv(find_dotenv(), override=True)

    return {
        "file_path": Path(get_required_env("EXCEL_FILE_PATH")),
        "sheet_name": get_required_env("SHEET_NAME"),
        "date_column": get_required_env("DATE_COLUMN"),
        "customer_column": get_required_env("CUSTOMER_COLUMN"),
        "bot_token": get_required_env("FATHER_BOT_TOKEN"),
        "chat_id": get_required_env("CHAT_ID"),
    }