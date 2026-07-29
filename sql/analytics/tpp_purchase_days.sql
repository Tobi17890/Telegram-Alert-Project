-- Perform data cleaning and aggregation on the billing data from the zsd_billing_cmc_tpp table 
-- And store the results in a temporary table (valid_purchase_rows) for further analysis.
WITH valid_purchase_rows AS (
    SELECT
        NULLIF(LTRIM(RTRIM([Sold-to-party ID])), N'') AS customer_id,
        NULLIF(LTRIM(RTRIM([Sold-to-party Name])), N'') AS customer_name,
        NULLIF(LTRIM(RTRIM([Sales District])), N'') AS province,
        [Billing Date] AS purchase_date,
        [Net Amount] AS purchase_quantity
    FROM [hana].[zsd_billing_cmc_tpp]
    WHERE
        [Billing Date] IS NOT NULL
        AND [Net Amount] IS NOT NULL
        AND [Net Amount] > 0
        AND NULLIF(LTRIM(RTRIM([Sold-to-party ID])), N'') IS NOT NULL
)
SELECT
    customer_id,
    MAX(customer_name) AS customer_name,
    MAX(province) AS province,
    purchase_date,
    SUM(purchase_quantity) AS purchase_quantity
FROM valid_purchase_rows
GROUP BY
    customer_id,
    purchase_date
ORDER BY
    customer_id,
    purchase_date;