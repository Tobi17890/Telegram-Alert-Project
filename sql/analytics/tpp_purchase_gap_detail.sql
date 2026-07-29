/*
Optional Phase 2 audit query.

This returns one row per valid customer purchase day with:
- previous purchase date
- gap days
- summed positive purchase quantity

The daily Telegram pipeline does not fetch this query by default.
Set EXPORT_GAP_DETAIL = True in the pipeline only when the
detail CSV is needed for checking or investigation.

This query is read-only.
*/

WITH valid_purchase_rows AS (
    SELECT
        NULLIF(
            LTRIM(RTRIM([Sold-to-party ID])),
            N''
        ) AS customer_id,

        NULLIF(
            LTRIM(RTRIM([Sold-to-party Name])),
            N''
        ) AS customer_name,

        NULLIF(
            LTRIM(RTRIM([Sales District])),
            N''
        ) AS province,

        [Billing Date] AS purchase_date,
        [Net Amount] AS purchase_quantity

    FROM [hana].[zsd_billing_cmc_tpp]

    WHERE
        [Billing Date] IS NOT NULL
        AND [Net Amount] IS NOT NULL
        AND [Net Amount] > 0
        AND NULLIF(
            LTRIM(RTRIM([Sold-to-party ID])),
            N''
        ) IS NOT NULL
),

purchase_days AS (
    SELECT
        customer_id,
        purchase_date,

        MAX(customer_name) AS customer_name,
        MAX(province) AS province,

        SUM(purchase_quantity) AS purchase_quantity

    FROM valid_purchase_rows

    GROUP BY
        customer_id,
        purchase_date
),

purchase_days_with_previous_date AS (
    SELECT
        customer_id,
        customer_name,
        province,
        purchase_date,

        LAG(purchase_date) OVER (
            PARTITION BY customer_id
            ORDER BY purchase_date
        ) AS previous_purchase_date,

        purchase_quantity

    FROM purchase_days
)

SELECT
    customer_id,
    customer_name,
    province,
    purchase_date,
    previous_purchase_date,

    DATEDIFF(
        DAY,
        previous_purchase_date,
        purchase_date
    ) AS gap_days,

    purchase_quantity

FROM purchase_days_with_previous_date

ORDER BY
    customer_id,
    purchase_date;
