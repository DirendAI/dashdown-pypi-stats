import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import multi_daily_series, packages, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def compare_totals(params, connect):
    """Total downloads per selected package over the window — aggregated from the
    same snapshot-first daily series the overlay chart uses, so it costs no extra
    ClickPy query when the local cache can serve the selection."""
    pkgs = packages(params)
    start, end = window(params)
    df = multi_daily_series(pkgs, start, end, connect)
    return (df.groupby("project", as_index=False)["downloads"].sum()
              .sort_values("downloads", ascending=False, ignore_index=True))
