DO $$
DECLARE
    tbl RECORD;
BEGIN
    FOR tbl IN
        SELECT schemaname, tablename
        FROM pg_tables
        WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
    LOOP
        EXECUTE format(
            'GRANT ALL PRIVILEGES ON TABLE %I.%I TO "%s";',
            tbl.schemaname, tbl.tablename, '6f10ae6c-a0cb-46ee-8f8f-f2efed1f24a3'
        );
    END LOOP;
END
$$;