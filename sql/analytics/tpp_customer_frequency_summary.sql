/*
Phase 2 optimization for the Telegram purchase-frequency alert.

Purpose:
- Filter valid TPP purchases in SQL Server.
- Collapse same-day purchases into one customer purchase day.
- Calculate previous purchase date and gap days with LAG().
- Aggregate the result into one row per customer.
- Return only the customer-level base summary to Python.

Python will still calculate:
- days_since_last_purchase using Cambodia time
- customer_category
- customer_status
- purchase_probability_percent

This query is read-only. It does not INSERT, UPDATE, DELETE,
CREATE, ALTER, DROP, or modify any database object.
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
        purchase_quantity,

        LAG(purchase_date) OVER (
            PARTITION BY customer_id
            ORDER BY purchase_date
        ) AS previous_purchase_date

    FROM purchase_days
),

ranked_purchase_days AS (
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

        purchase_quantity,

        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY purchase_date DESC
        ) AS latest_purchase_rank

    FROM purchase_days_with_previous_date
)

SELECT
    customer_id,

    MAX(
        CASE
            WHEN latest_purchase_rank = 1
                THEN customer_name
        END
    ) AS customer_name,

    MAX(
        CASE
            WHEN latest_purchase_rank = 1
                THEN province
        END
    ) AS province,

    COUNT(*) AS valid_purchase_days,

    MIN(purchase_date) AS first_purchase_date,
    MAX(purchase_date) AS latest_purchase_date,

    SUM(purchase_quantity) AS total_positive_quantity,

    COUNT(gap_days) AS number_of_gaps,

    COALESCE(
        SUM(gap_days),
        0
    ) AS total_gap_days,

    ROUND(
        AVG(
            CAST(gap_days AS FLOAT)
        ),
        2
    ) AS average_gap_days

FROM ranked_purchase_days

GROUP BY
    customer_id

ORDER BY
    customer_id;
