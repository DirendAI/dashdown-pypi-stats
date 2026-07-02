import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import breakdown, project, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def by_filetype(params, connect):
    """Wheel vs source distribution split (bdist_wheel vs sdist).
    Snapshot-first: preset windows for top packages come from the local cache."""
    proj = project(params)
    start, end = window(params)
    df = breakdown(connect, proj, start, end,
        cache_sql="SELECT file_type, downloads FROM pypi_break_filetype "
                  "WHERE project = ${proj} AND win = ${win} "
                  "ORDER BY downloads DESC",
        live_sql="SELECT if(type = '', 'unknown', type) AS file_type, sum(count) AS downloads "
                 "FROM pypi.pypi_downloads_per_day_by_version_by_file_type "
                 "WHERE project = ${project} AND date BETWEEN ${start} AND ${end} "
                 "GROUP BY file_type ORDER BY downloads DESC")
    # Human labels for the donut legend instead of packaging jargon.
    df["file_type"] = df["file_type"].replace({"bdist_wheel": "wheel", "sdist": "source"})
    return df
