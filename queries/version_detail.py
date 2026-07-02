import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import breakdown, project, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def version_detail(params, connect):
    """Per-version table with each version's share of downloads (share of the top
    25, matching the table it feeds). Snapshot-first like the other breakdowns."""
    proj = project(params)
    start, end = window(params)
    df = breakdown(connect, proj, start, end,
        cache_sql="SELECT version, downloads FROM pypi_break_version "
                  "WHERE project = ${proj} AND win = ${win} "
                  "ORDER BY downloads DESC LIMIT 25",
        live_sql="SELECT version, sum(count) AS downloads "
                 "FROM pypi.pypi_downloads_per_day_by_version "
                 "WHERE project = ${project} AND date BETWEEN ${start} AND ${end} AND version != '' "
                 "GROUP BY version ORDER BY downloads DESC LIMIT 25")
    total = df["downloads"].sum() if len(df) else 0
    # The percent formatter appends "%" without scaling, so share is 0–100.
    df["share"] = (df["downloads"] / total * 100).round(1) if total else 0.0
    return df
