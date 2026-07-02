---
connector: main
---
-- Echoes the resolved package + period for the page prose. It is SQL (not Python) on
-- purpose: referencing ${date_start}/${date_end} here is what tells Dashdown the page is
-- date-aware, so the project-wide date control appears in the header. Runs on the local
-- DuckDB/Parquet connector (constant expressions, no table scan).
SELECT
  -- Default must be a top-catalog package so the first page load serves from the
  -- local snapshots instantly (and it's the very driver this dashboard queries with).
  COALESCE(NULLIF('${project}', ''), 'clickhouse-connect') AS project,
  COALESCE(TRY_CAST(NULLIF('${date_start}', '') AS DATE), CURRENT_DATE - 30) AS start_date,
  COALESCE(TRY_CAST(NULLIF('${date_end}',   '') AS DATE), CURRENT_DATE)      AS end_date
