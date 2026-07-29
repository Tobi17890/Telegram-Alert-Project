SELECT [Billing Date] AS purchase_date,
    --    COUNT(*) AS row_count,
       [Sold-to-party Name] AS customer_name
FROM [hana].[zsd_billing_cmc_tpp]
WHERE [Ship-to-party ID] = '11000771';
-- GROUP BY [Billing Date], [Sold-to-party Name]
-- ORDER BY [Billing Date]; 