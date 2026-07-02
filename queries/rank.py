import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import ch, in_top_catalog, project  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def rank(params, connect):
    """All-time download rank across every PyPI package (1 = most downloaded),
    competition-ranked: 1 + the number of packages with strictly more downloads.
    Snapshot-first: a package in the top-N catalog is ranked by its position
    there; the long tail costs one live ClickPy count over per-project totals.
    All-time on purpose — the header period doesn't apply (the Counter's label
    says so), because no per-window rank source exists short of ranking all
    ~600k packages per window."""
    proj = project(params)
    if in_top_catalog(proj, connect):
        try:
            return connect(
                "main",
                "SELECT count(*) + 1 AS rank FROM pypi_top_packages "
                "WHERE downloads > (SELECT downloads FROM pypi_top_packages WHERE name = ${proj})",
                params={"proj": proj},
            ).to_pandas()
        except Exception:
            pass  # snapshot unreadable → live
    return ch(connect,
        "SELECT count() + 1 AS rank "
        "FROM (SELECT project, sum(count) AS total FROM pypi.pypi_downloads GROUP BY project) "
        "WHERE total > (SELECT sum(count) FROM pypi.pypi_downloads WHERE project = ${project})",
        project=proj)
