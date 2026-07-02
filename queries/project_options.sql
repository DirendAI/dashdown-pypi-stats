---
connector: main
cache_ttl: 3600
---
-- Option source for the package <Combobox>. Dashdown wraps this into a
-- `SELECT DISTINCT CAST(name AS VARCHAR) AS value FROM (…) WHERE name ILIKE '%term%'`
-- lookup, ranked prefix-matches-first ("num" → numpy before abnum, exact match on
-- top) and LIMITed, run server-side as you type against the local pypi_projects
-- Parquet catalog (every package on PyPI). Rebuild with scripts/build_cache.py.
SELECT name FROM pypi_projects
