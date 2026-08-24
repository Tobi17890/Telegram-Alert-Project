SELECT DISTINCT
    [Sold-to-party ID] AS [Sold-to-party],
    [Sold-to-party Name] AS [Sold-to-party Name],
    CASE 
        WHEN [Sold-to-party ID] LIKE 'INTER-%' THEN 'Internal'
        ELSE 'External'
    END AS [Customer Type]
FROM [hana].[zsd_billing_cmc_tpp]
ORDER BY [Sold-to-party];