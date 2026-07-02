import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import breakdown, project, top_slices, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def by_system(params, connect):
    """Operating system of the installing machine (Linux / Windows / Darwin / …).
    Snapshot-first: preset windows for top packages come from the local cache.
    The long tail collapses into 'other' so the donut's labels stay legible."""
    proj = project(params)
    start, end = window(params)
    df = breakdown(connect, proj, start, end,
        cache_sql="SELECT os, downloads FROM pypi_break_system "
                  "WHERE project = ${proj} AND win = ${win} "
                  "ORDER BY downloads DESC LIMIT 8",
        live_sql="SELECT if(system = '', 'unknown', system) AS os, sum(count) AS downloads "
                 "FROM pypi.pypi_downloads_per_day_by_version_by_system "
                 "WHERE project = ${project} AND date BETWEEN ${start} AND ${end} "
                 "GROUP BY os ORDER BY downloads DESC LIMIT 8")
    return top_slices(df, "os")
