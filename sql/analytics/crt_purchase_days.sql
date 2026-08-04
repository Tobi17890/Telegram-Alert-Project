WITH valid_delivery_rows AS (

    SELECT
        NULLIF(
            LTRIM(
                RTRIM([Sold-to-party ID])
            ),
            ''
        ) AS customer_id,

        NULLIF(
            LTRIM(
                RTRIM([Sold-to-party Name])
            ),
            ''
        ) AS customer_name,

        NULLIF(
            LTRIM(
                RTRIM([Sales District])
            ),
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
            LTRIM(
                RTRIM([Sold-to-party ID])
            ),
            ''
        ) IS NOT NULL
)

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

ORDER BY
    customer_id,
    delivery_date;