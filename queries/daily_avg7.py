import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import daily_series, project, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def daily_avg7(params, connect):
    """Rolling 7-day mean of daily downloads — the smoothed trend behind the
    "Avg / day" KPI's sparkline. Same snapshot-first source as `daily`
    (clickpy.daily_series), just averaged, so top packages cost nothing extra;
    a long-tail package spends one more live ClickPy query per window."""
    proj = project(params)
    start, end = window(params)
    df = daily_series(proj, start, end, connect)
    df["avg7"] = df["downloads"].rolling(7, min_periods=1).mean().round()
    return df[["day", "avg7"]]
