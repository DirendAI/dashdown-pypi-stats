import pathlib
import sys
from datetime import date

import pandas as pd
from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import ch, daily_series, in_top_catalog, matched_window, project, window  # noqa: E402


def _one(df, col):
    return int(df[col].fillna(0).iloc[0]) if len(df) else 0


def _uniq_counts(proj, start, end, connect):
    """Distinct versions/countries in the window. Exact counts per preset window
    live in the pypi_window_kpis snapshot; anything it can't serve goes live
    (uniq counts don't aggregate from capped per-dimension caches)."""
    win = matched_window(start, end, connect)
    if win and in_top_catalog(proj, connect):
        try:
            rows = connect(
                "main",
                "SELECT versions, countries FROM pypi_window_kpis "
                "WHERE project = ${proj} AND win = ${win}",
                params={"proj": proj, "win": win},
            ).to_pandas()
            # No row = the package genuinely had no download rows in that window.
            return (_one(rows, "versions"), _one(rows, "countries"))
        except Exception:
            pass  # snapshot unreadable → live
    b = dict(project=proj, start=start, end=end)
    versions = ch(connect,
        "SELECT uniqExact(version) AS versions FROM pypi.pypi_downloads_per_day_by_version "
        "WHERE project = ${project} AND date BETWEEN ${start} AND ${end} AND version != ''", **b)
    countries = ch(connect,
        "SELECT uniqExact(country_code) AS countries FROM pypi.pypi_downloads_per_day_by_version_by_country "
        "WHERE project = ${project} AND date BETWEEN ${start} AND ${end} AND country_code != ''", **b)
    return (_one(versions, "versions"), _one(countries, "countries"))


@query(connector="clickpy", cache_ttl=86400)
def kpis(params, connect):
    """One-row KPI strip: total downloads, average/day, distinct versions & countries.
    Snapshot-first end to end: the total comes from the per-day daily cache (any
    window it covers), the uniq counts from the preset-window KPI cache."""
    proj = project(params)
    start, end = window(params)

    series = daily_series(proj, start, end, connect)
    versions, countries = _uniq_counts(proj, start, end, connect)

    downloads = int(series["downloads"].fillna(0).sum()) if len(series) else 0
    ndays = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
    return pd.DataFrame([{
        "downloads": downloads,
        "avg_daily": round(downloads / max(ndays, 1)),
        "versions": versions,
        "countries": countries,
    }])
