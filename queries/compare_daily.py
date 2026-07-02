import pathlib
import sys

from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import multi_daily_series, packages, window  # noqa: E402


@query(connector="clickpy", cache_ttl=86400)
def compare_daily(params, connect):
    """Daily downloads for the selected packages, overlaid (multi-select Combobox).
    Snapshot-first: served from the local parquet cache when every selected package
    and the whole window are covered (see clickpy.multi_daily_series)."""
    pkgs = packages(params)
    start, end = window(params)
    return multi_daily_series(pkgs, start, end, connect)
