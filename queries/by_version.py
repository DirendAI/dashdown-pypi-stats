import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import breakdown, project, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def by_version(params, connect):
    """Top released versions by downloads in the window. Snapshot-first: preset
    windows for top packages come from the local cache, anything else goes live."""
    proj = project(params)
    start, end = window(params)
    return breakdown(connect, proj, start, end,
        cache_sql="SELECT version, downloads FROM pypi_break_version "
                  "WHERE project = ${proj} AND win = ${win} "
                  "ORDER BY downloads DESC LIMIT 15",
        live_sql="SELECT version, sum(count) AS downloads "
                 "FROM pypi.pypi_downloads_per_day_by_version "
                 "WHERE project = ${project} AND date BETWEEN ${start} AND ${end} AND version != '' "
                 "GROUP BY version ORDER BY downloads DESC LIMIT 15")
