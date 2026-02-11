BEGIN
  -- Iterate over all tables and execute DROP TABLE IF EXISTS for each
  FOR table_rec AS 
    SELECT table_name
    FROM mfg_mid_central_sa.information_schema.tables
    WHERE table_schema = 'qbr_demo' and table_type <> 'VIEW' and table_type <> 'METRIC_VIEW'
  DO
    EXECUTE IMMEDIATE concat('DROP TABLE IF EXISTS mfg_mid_central_sa.qbr_demo.', table_rec.table_name);
  END FOR;
END;


DROP VOLUME mfg_mid_central_sa.qbr_demo.qbr_databricks_platform_demo;

DROP VOLUME mfg_mid_central_sa.qbr_demo.quotes_volume;

DROP FUNCTION mfg_mid_central_sa.qbr_demo.lead_time_predictor;

DROP FUNCTION mfg_mid_central_sa.qbr_demo.parse_email;