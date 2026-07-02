import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import daily_series, project, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def daily(params, connect):
    """Daily download counts — the hero time series."""
    proj = project(params)
    start, end = window(params)
    return daily_series(proj, start, end, connect)
