--Replace all of this with budget_policy_id. Didn't add until after ran project
SELECT
    u.usage_date,
    u.sku_name,
    SUM(u.usage_quantity) AS dbus,
    FIRST(lp.pricing.default) AS list_price,
    SUM(u.usage_quantity) * FIRST(lp.pricing.default) AS dollar_dbus_list
FROM system.billing.usage u
INNER JOIN system.billing.list_prices lp ON u.sku_name = lp.sku_name
    AND u.usage_start_time >= lp.price_start_time
    AND (
        u.usage_end_time <= lp.price_end_time
        or lp.price_end_time is null
    )
WHERE u.usage_metadata.budget_policy_id = 'cfe4a01e-a9cd-4399-b72f-94e96ae6e68d' or u.usage_metadata.endpoint_name = 'ka-e698d7b0-endpoint' or (u.usage_metadata.endpoint_name = 'databricks-gpt-oss-20b' and u.identity_metadata.run_as = 'zach.jacobson@databricks.com') or u.usage_metadata.dlt_pipeline_id = '3699de9d-e43d-429e-bf2d-1958a19c3d49' or u.usage_metadata.dlt_pipeline_id = '8040bfbc-db9c-4d49-9591-9e7aac6cf955' or u.usage_metadata.dlt_pipeline_id = 'efe1e47b-47a4-4423-9720-cc6e17091f0f' or u.usage_metadata.dlt_pipeline_id = '94b36ec0-8a02-4aa0-8125-432b8b0ed74b' or u.usage_metadata.app_id = '46c74b21-a8e0-4cd1-a30e-e8bf10549f8c'
GROUP BY u.usage_date, u.sku_name
ORDER BY u.usage_date, u.sku_name DESC;
