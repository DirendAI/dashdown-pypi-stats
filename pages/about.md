---
title: About & data source
sidebar_position: 3
icon: ℹ️
---

# About this dashboard

This dashboard reads PyPI download stats from the **free, public ClickHouse dataset**
behind [ClickPy](https://clickpy.clickhouse.com) — ClickHouse's own PyPI analytics site.
It's built from the official PyPI download logs (one row per file fetched from PyPI,
enriched with installer, Python version, OS and country — the same data described in the
[*Analyzing PyPI package downloads*](https://packaging.python.org/en/latest/guides/analyzing-pypi-package-downloads/)
guide), **pre-aggregated** into small daily rollup tables and served with **no billing**.

Latest data available: **<Value data={freshness} column="latest_date" format="date" />**
(the dataset is refreshed daily).

## Why it's free

- **Pre-aggregated tables.** ClickHouse maintains rollups like `pypi_downloads_per_day`,
  `…_by_version`, `…_by_python`, `…_by_system`, `…_by_country` and
  `…_by_installer_by_type`. Each project's slice is tiny, so a query reads kilobytes.
- **A public read-only endpoint.** The `play` user on `sql-clickhouse.clickhouse.com`
  answers SQL over HTTPS with no key and no bill.
- **Nothing to meter.** The only limit is politeness, so every query here caches for 24 h
  (`cache_ttl: 86400`) — which also keeps us well within the service's fair-use limits.

## How the dashboard talks to it

The dashboard connects through **Dashdown's native `clickhouse` connector** (the
`clickpy` entry in `sources.yaml`, driven by `clickhouse-connect` — ClickHouse's
official client). Package names and dates from the filter bar reach any SQL only
via Dashdown's `${param}` substitution, which always embeds them as escaped
literals — so a value like `flask' OR 1=1--` is treated as a literal package name
and simply matches nothing:

```sql
SELECT date AS day, sum(count) AS downloads
FROM pypi.pypi_downloads_per_day
WHERE project = '${project}' AND date BETWEEN '${date_start}' AND '${date_end}'
GROUP BY day ORDER BY day
```

Every chart query is **snapshot-first Python** (`queries/*.py`): it serves from the
local Parquet caches when they can answer the request and only falls back to ClickPy
live — cache-or-live logic that spans two connectors (see
[`clickpy.py`](../clickpy.py)). The daily series reads a per-day snapshot that covers
*any* window inside it; the breakdowns (version / Python / OS / installer / file type /
country) and the KPI uniq-counts read per-window snapshots pre-aggregated for the
period presets — a custom date range is what sends them live.

## Package metadata (PyPI JSON API)

The **About the package** facts and **release history** on the explorer — and the
metadata table on Compare — come from a second free source: the
[PyPI JSON API](https://docs.pypi.org/api/json/) (`https://pypi.org/pypi/<package>/json`),
no key, served from PyPI's CDN. It supplies the summary, author, license, latest
version, dependency list, release dates, and known vulnerabilities in the latest
release (PyPI's [OSV](https://osv.dev) integration). Unlike the download tables this
metadata covers the package's **whole life**, so the period filter doesn't apply to
those sections. Responses cache for 24 h, same as everything else.

## The package picker

The **Package** search on the explorer (and the multi-select on Compare) is a
`<Combobox>` — it type-searches server-side over a small local catalog,
`data/pypi_projects.parquet`, holding **every package registered on PyPI** (snapshotted
from the PyPI Simple index). It works offline and misses nothing; refresh it any time
with `python scripts/build_cache.py`. That script also snapshots, for the **top 5,000
packages**, per-day downloads plus every breakdown and KPI pre-aggregated per preset
window — so for a popular package and a preset period the whole page is served
locally. Only less-common packages and custom date ranges query ClickHouse live.

## A note on the numbers

Raw download counts include automated traffic — CI pipelines and mirroring tools. That's
why the **Installer** breakdown shows a large `uv`/mirror share and the **OS** chart is
Linux-heavy. The counts are directional, not exact. ClickPy keeps roughly the **last six
months** of daily data, which is why the period presets stop at 90 days.
