WITH valid_delivery_rows AS (

    SELECT
        NULLIF(
            LTRIM(RTRIM([Sold-to-party ID])),
            ''
        ) AS customer_id,

        NULLIF(
            LTRIM(RTRIM([Sold-to-party Name])),
            ''
        ) AS customer_name,

        NULLIF(
            LTRIM(RTRIM([Sales District])),
            ''
        ) AS province,

        [Billing Date] AS delivery_date,

        [Del Qty] AS delivery_quantity

    FROM [hana].[zsd_billing_cmc_crt]

    WHERE
        [Billing Date] IS NOT NULL

        AND [Del Qty] IS NOT NULL

        AND [Del Qty] > 0

        AND NULLIF(
            LTRIM(RTRIM([Sold-to-party ID])),
            ''
        ) IS NOT NULL
),


-- ============================================
-- STEP 1
-- ONE ROW PER CUSTOMER PER DELIVERY DATE
-- ============================================

purchase_days AS (

    SELECT
        customer_id,

        MAX(customer_name) AS customer_name,

        MAX(province) AS province,

        delivery_date,

        SUM(delivery_quantity) AS delivery_quantity

    FROM valid_delivery_rows

    GROUP BY
        customer_id,
        delivery_date
),


-- ============================================
-- STEP 2A
-- FIND PREVIOUS DELIVERY DATE
-- ============================================

delivery_days_with_previous AS (

    SELECT
        customer_id,
        customer_name,
        province,
        delivery_date,
        delivery_quantity,

        LAG(delivery_date) OVER (
            PARTITION BY customer_id
            ORDER BY delivery_date
        ) AS previous_delivery_date

    FROM purchase_days
),


-- ============================================
-- STEP 2B
-- MARK START OF NEW CRT PURCHASE EVENT
-- ============================================
--
-- SAME EVENT:
-- 0 or 1 day from previous delivery
--
-- NEW EVENT:
-- 2 days or more
-- ============================================

delivery_days_with_event_start AS (

    SELECT
        customer_id,
        customer_name,
        province,
        delivery_date,
        delivery_quantity,

        CASE

            WHEN previous_delivery_date IS NULL
                THEN 1

            WHEN DATEDIFF(
                DAY,
                previous_delivery_date,
                delivery_date
            ) >= 2
                THEN 1

            ELSE 0

        END AS new_event_flag

    FROM delivery_days_with_previous
),


-- ============================================
-- STEP 2C
-- ASSIGN PURCHASE EVENT NUMBER
-- ============================================

delivery_days_with_event_number AS (

    SELECT
        customer_id,
        customer_name,
        province,
        delivery_date,
        delivery_quantity,

        SUM(new_event_flag) OVER (
            PARTITION BY customer_id
            ORDER BY delivery_date
            ROWS UNBOUNDED PRECEDING
        ) AS purchase_event_number

    FROM delivery_days_with_event_start
),


-- ============================================
-- STEP 2D
-- ONE ROW PER CRT PURCHASE EVENT
-- ============================================

purchase_events AS (

    SELECT
        customer_id,

        MAX(customer_name) AS customer_name,

        MAX(province) AS province,

        purchase_event_number,

        MIN(delivery_date) AS event_start_date,

        MAX(delivery_date) AS event_end_date,

        COUNT(*) AS delivery_days_in_event,

        SUM(delivery_quantity) AS event_delivery_quantity

    FROM delivery_days_with_event_number

    GROUP BY
        customer_id,
        purchase_event_number
),


-- ============================================
-- STEP 3
-- CALCULATE GAP BETWEEN PURCHASE EVENTS
-- ============================================

purchase_events_with_gap AS (

    SELECT
        customer_id,
        customer_name,
        province,
        purchase_event_number,

        event_start_date,
        event_end_date,

        event_end_date AS purchase_event_date,

        delivery_days_in_event,
        event_delivery_quantity,

        LAG(event_end_date) OVER (
            PARTITION BY customer_id
            ORDER BY event_end_date
        ) AS previous_purchase_event_date

    FROM purchase_events
),


-- ============================================
-- STEP 3B
-- ADD GAP DAYS
-- ============================================

purchase_events_with_gap_days AS (

    SELECT
        customer_id,
        customer_name,
        province,
        purchase_event_number,

        event_start_date,
        event_end_date,
        purchase_event_date,

        previous_purchase_event_date,

        CASE

            WHEN previous_purchase_event_date IS NULL
                THEN NULL

            ELSE DATEDIFF(
                DAY,
                previous_purchase_event_date,
                purchase_event_date
            )

        END AS gap_days,

        delivery_days_in_event,
        event_delivery_quantity

    FROM purchase_events_with_gap
),


-- ============================================
-- STEP 4A
-- RANK EVENTS SO WE CAN TAKE
-- NAME + PROVINCE FROM LATEST EVENT
-- ============================================

ranked_purchase_events AS (

    SELECT
        *,

        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY purchase_event_date DESC
        ) AS latest_event_rank

    FROM purchase_events_with_gap_days
)


-- ============================================
-- STEP 4B
-- ONE SUMMARY ROW PER CUSTOMER
-- ============================================

SELECT
    customer_id,

    MAX(
        CASE
            WHEN latest_event_rank = 1
                THEN customer_name
        END
    ) AS customer_name,

    MAX(
        CASE
            WHEN latest_event_rank = 1
                THEN province
        END
    ) AS province,

    COUNT(*) AS valid_purchase_events,

    MIN(
        purchase_event_date
    ) AS first_purchase_date,

    MAX(
        purchase_event_date
    ) AS latest_purchase_date,

    SUM(
        event_delivery_quantity
    ) AS total_del_qty,

    COUNT(
        gap_days
    ) AS number_of_gaps,

    COALESCE(
        SUM(
            gap_days
        ),
        0
    ) AS total_gap_days,

    ROUND(
        AVG(
            CAST(
                gap_days AS FLOAT
            )
        ),
        2
    ) AS average_gap_days

FROM ranked_purchase_events

GROUP BY
    customer_id

ORDER BY
    customer_id;