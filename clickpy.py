"""Helpers for the free, public ClickHouse PyPI dataset (ClickPy).

No API key, no billing: the `play` read-only user on ClickHouse's public service
exposes the whole `pypi` database of pre-aggregated download tables. All SQL runs
through the project's `clickpy` connector (sources.yaml — Dashdown's native
`clickhouse` connector), and values reach the SQL only via Dashdown's ${param}
substitution, so a package name from the filter box is always a data value and
can never be SQL. Results arrive typed (Date/UInt64), no text-format casting.
"""
import datetime as _dt

import pandas as pd


def ch(connect, sql, **binds) -> pd.DataFrame:
    """Run SQL on the `clickpy` connector and return a DataFrame. `binds` values
    substitute ${name} placeholders through Dashdown's injection-safe escaping —
    never string-concatenated. A comma-joined value inside `IN (${name})` expands
    to a quoted literal list."""
    return connect("clickpy", sql, params=binds).to_pandas()


def pick(params, key, default) -> str:
    """Read a package-name param, falling back to `default` when the box is empty."""
    return (params.get(key) or "").strip() or default


def project(params, default="clickhouse-connect") -> str:
    """The searched package, falling back to a sensible default when the box is empty."""
    return pick(params, "project", default)


def packages(params, key="packages", default=("numpy", "pandas", "polars"), cap=6):
    """Parse a multi-select Combobox value (a comma-joined string) into a capped list of
    package names, falling back to `default` when nothing is selected. PyPI names never
    contain commas, so a plain split is safe."""
    raw = (params.get(key) or "").strip()
    names = [p.strip() for p in raw.split(",") if p.strip()]
    return (names or list(default))[:cap]


_CACHE_LAG_DAYS = 3  # tolerate ClickPy's ~1-day data lag plus a daily cache rebuild


def daily_series(proj, start, end, connect) -> pd.DataFrame:
    """Per-day downloads for one package over [start, end] — the single-package
    view of `multi_daily_series` (day, downloads)."""
    return multi_daily_series([proj], start, end, connect)[["day", "downloads"]]


def multi_daily_series(projects, start, end, connect) -> pd.DataFrame:
    """Per-day downloads (project, day, downloads) for several packages over
    [start, end]. Served from the local data/pypi_daily_cache.parquet snapshot
    (built by scripts/build_cache.py) when it covers every package and the whole
    window — spending no ClickPy quota — else one live ClickPy query for all of
    them. The snapshot holds only the top packages, so any long-tail selection
    sends the whole batch live."""
    df = _cached_daily(projects, start, end, connect)
    if df is None:
        df = ch(
            connect,
            "SELECT project, date AS day, sum(count) AS downloads "
            "FROM pypi.pypi_downloads_per_day "
            "WHERE project IN (${projects}) AND date BETWEEN ${start} AND ${end} "
            # day-major order: the chart's x axis follows row order, and a series
            # that starts late (a new package) must not drag its first day ahead
            # of the others' earlier days.
            "GROUP BY project, day ORDER BY day, project",
            projects=",".join(projects), start=start, end=end)
    return df


def _cached_daily(projects, start, end, connect):
    """The cached daily series, or None when the snapshot can't serve this request:
    a package isn't in it (membership = pypi_top_packages, the catalog the daily
    cache is built from in the same run), the window starts before it, or it has
    gone stale (no rebuild within _CACHE_LAG_DAYS of the window's end)."""
    pkgs = ",".join(projects)
    try:
        known = connect(
            "main",
            "SELECT count(DISTINCT name) AS n FROM pypi_top_packages WHERE name IN (${pkgs})",
            params={"pkgs": pkgs},
        ).to_pandas()
        if int(known["n"].iloc[0]) != len(set(projects)):
            return None
        bounds = connect(
            "main", "SELECT min(day) AS lo, max(day) AS hi FROM pypi_daily_cache",
        ).to_pandas()
        lo, hi = str(bounds["lo"].iloc[0])[:10], str(bounds["hi"].iloc[0])[:10]
        fresh_floor = (_dt.date.fromisoformat(end) - _dt.timedelta(days=_CACHE_LAG_DAYS)).isoformat()
        if lo > start or hi < fresh_floor:
            return None
        return connect(
            "main",
            "SELECT project, day, downloads FROM pypi_daily_cache "
            "WHERE project IN (${pkgs}) AND day BETWEEN ${start} AND ${end} "
            "ORDER BY day, project",  # day-major — see multi_daily_series
            params={"pkgs": pkgs, "start": start, "end": end},
        ).to_pandas()
    except Exception:
        return None  # snapshot absent or unreadable


def matched_window(start, end, connect):
    """The snapshot window key ('7d' / '30d' / '90d' / 'month') that can answer a
    request for [start, end] — both edges within _CACHE_LAG_DAYS of the cached
    window — or None. Window metadata (win, win_start, win_end) rides in
    data/pypi_window_kpis.parquet, rebuilt nightly by scripts/build_cache.py."""
    try:
        wins = connect(
            "main", "SELECT DISTINCT win, win_start, win_end FROM pypi_window_kpis",
        ).to_pandas()
    except Exception:
        return None  # snapshot absent or unreadable
    s, e = _dt.date.fromisoformat(start), _dt.date.fromisoformat(end)
    best, best_diff = None, None
    for row in wins.itertuples():
        ds = abs((_dt.date.fromisoformat(str(row.win_start)[:10]) - s).days)
        de = abs((_dt.date.fromisoformat(str(row.win_end)[:10]) - e).days)
        if ds <= _CACHE_LAG_DAYS and de <= _CACHE_LAG_DAYS and (best_diff is None or ds + de < best_diff):
            best, best_diff = str(row.win), ds + de
    return best


def in_top_catalog(proj, connect) -> bool:
    """Whether the package is in the top-N catalog the snapshots are built from."""
    try:
        n = connect(
            "main", "SELECT count(*) AS n FROM pypi_top_packages WHERE name = ${proj}",
            params={"proj": proj},
        ).to_pandas()
        return int(n["n"].iloc[0]) > 0
    except Exception:
        return False


def top_slices(df, label_col, n=5, other="other") -> pd.DataFrame:
    """Collapse a breakdown's long tail into a single `other` slice so a donut
    keeps at most n+1 legible labels instead of spraying near-zero callouts."""
    if len(df) <= n + 1:
        return df
    df = df.sort_values("downloads", ascending=False)
    tail_total = int(df.iloc[n:]["downloads"].sum())
    other_row = pd.DataFrame([{label_col: other, "downloads": tail_total}])
    return pd.concat([df.iloc[:n], other_row], ignore_index=True)


def breakdown(connect, proj, start, end, cache_sql, live_sql) -> pd.DataFrame:
    """Serve a per-package breakdown from the local preset-window snapshot
    (data/pypi_break_*.parquet) when the package is in the top-N catalog and
    [start, end] matches a snapshot window — spending no ClickPy quota — else
    queried live. cache_sql reads the snapshot with ${proj}/${win}; live_sql
    hits ClickPy with ${project}/${start}/${end}."""
    win = matched_window(start, end, connect)
    if win and in_top_catalog(proj, connect):
        try:
            return connect(
                "main", cache_sql, params={"proj": proj, "win": win},
            ).to_pandas()
        except Exception:
            pass  # snapshot unreadable → live
    return ch(connect, live_sql, project=proj, start=start, end=end)


# The header presets deliberately stop at 90 days (see dashdown.yaml) because an
# unbounded window means a far larger live scan on ClickPy — but presets only
# constrain the UI. The data API accepts any ISO dates in a crafted URL, so the
# same ceiling is enforced here, where every query resolves its window.
_MAX_WINDOW_DAYS = 92  # last_90_days plus a little slack


def window(params, days=30):
    """Resolve the header date range to ISO strings, defaulting to the last `days` days
    when the global filter has no value yet. The span is clamped to _MAX_WINDOW_DAYS
    (keeping the requested end date), mirroring the UI's 90-day preset cap."""
    today = _dt.date.today()

    def parse(value, fallback):
        try:
            return _dt.date.fromisoformat((value or "").strip())
        except ValueError:
            return fallback

    start = parse(params.get("date_start"), today - _dt.timedelta(days=days))
    end = parse(params.get("date_end"), today)
    if end < start:
        start, end = end, start
    if (end - start).days > _MAX_WINDOW_DAYS:
        start = end - _dt.timedelta(days=_MAX_WINDOW_DAYS)
    return start.isoformat(), end.isoformat()
