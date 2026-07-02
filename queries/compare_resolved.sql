---
connector: main
---
-- Resolved selection + period for the compare page prose. SQL (not Python) so the
-- ${date_start}/${date_end} references make the page date-aware → the header date
-- control shows. `packages` is the multi-select Combobox's comma-joined value.
SELECT
  -- The combobox joins selections without spaces ("numpy,pandas"); re-space for prose/title.
  COALESCE(NULLIF(replace('${packages}', ',', ', '), ''), 'numpy, pandas, polars') AS packages,
  COALESCE(TRY_CAST(NULLIF('${date_start}', '') AS DATE), CURRENT_DATE - 30) AS start_date,
  COALESCE(TRY_CAST(NULLIF('${date_end}',   '') AS DATE), CURRENT_DATE)      AS end_date
