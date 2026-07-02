---
connector: clickpy
cache_ttl: 21600
---
-- Latest date present in the dataset (measured via the always-busy `pip` project).
SELECT max(date) AS latest_date
FROM pypi.pypi_downloads_per_day
WHERE project = 'pip'
