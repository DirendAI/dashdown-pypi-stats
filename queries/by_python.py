import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import breakdown, project, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def by_python(params, connect):
    """Downloads by Python minor version (3.12, 3.11, …). Snapshot-first: preset
    windows for top packages come from the local cache, anything else goes live."""
    proj = project(params)
    start, end = window(params)
    return breakdown(connect, proj, start, end,
        cache_sql="SELECT python_version, downloads FROM pypi_break_python "
                  "WHERE project = ${proj} AND win = ${win} "
                  "ORDER BY downloads DESC LIMIT 12",
        live_sql="SELECT if(python_minor = '', 'unknown', python_minor) AS python_version, sum(count) AS downloads "
                 "FROM pypi.pypi_downloads_per_day_by_version_by_python "
                 "WHERE project = ${project} AND date BETWEEN ${start} AND ${end} "
                 "GROUP BY python_version ORDER BY downloads DESC LIMIT 12")
