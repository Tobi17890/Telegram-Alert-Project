"""Main entry point for the Telegram customer alert project."""

from src.pipelines.purchase_frequency_pipeline import (
    run_purchase_frequency_pipeline,
)


def main() -> None:
    """
    Run customer purchase-frequency analysis.
    """

    run_purchase_frequency_pipeline()


if __name__ == "__main__":
    main()