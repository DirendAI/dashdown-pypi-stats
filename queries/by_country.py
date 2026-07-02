import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import breakdown, project, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def by_country(params, connect):
    """Top countries by downloads (ISO-3166 alpha-2 codes).
    Snapshot-first: preset windows for top packages come from the local cache."""
    proj = project(params)
    start, end = window(params)
    return breakdown(connect, proj, start, end,
        cache_sql="SELECT country, downloads FROM pypi_break_country "
                  "WHERE project = ${proj} AND win = ${win} "
                  "ORDER BY downloads DESC LIMIT 12",
        live_sql="SELECT if(country_code = '', '??', country_code) AS country, sum(count) AS downloads "
                 "FROM pypi.pypi_downloads_per_day_by_version_by_country "
                 "WHERE project = ${project} AND date BETWEEN ${start} AND ${end} "
                 "GROUP BY country ORDER BY downloads DESC LIMIT 12")
