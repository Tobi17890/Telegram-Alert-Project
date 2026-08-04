"""Run customer purchase alert pipelines."""

from src.pipelines.tpp_purchase_frequency_pipeline import (
    tpp_run_purchase_frequency_pipeline,
)

from src.pipelines.crt_purchase_frequency_pipeline import (
    run_crt_purchase_frequency_pipeline,
)


# ============================================
# WHICH PRODUCTS TO RUN
# ============================================

RUN_TPP = False

RUN_CRT = True


def main() -> None:

    # ========================================
    # TPP
    # ========================================

    if RUN_TPP:

        print(
            "\n"
            + "=" * 70
        )

        print(
            "STARTING TPP PIPELINE"
        )

        print(
            "=" * 70
        )

        tpp_run_purchase_frequency_pipeline()


    # ========================================
    # CRT
    # ========================================

    if RUN_CRT:

        print(
            "\n"
            + "=" * 70
        )

        print(
            "STARTING CRT PIPELINE"
        )

        print(
            "=" * 70
        )

        run_crt_purchase_frequency_pipeline()


    print(
        "\n"
        + "=" * 70
    )

    print(
        "ALL ENABLED PIPELINES COMPLETED"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()