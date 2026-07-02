#!/usr/bin/env python3
"""Build the local Parquet caches under data/ — CI-friendly (no prompts, non-zero
exit on any failure). Run it on a schedule (cron / CI) to keep the caches fresh:

    python scripts/build_cache.py                 # defaults: top 5000, 130 days
    python scripts/build_cache.py --top 10000 --days 200

ClickPy data is fetched through the project's `clickpy` connector (sources.yaml —
Dashdown's native `clickhouse` connector), so the script shares the dashboard's
endpoint config and the same ${param} escaping the app uses.

It produces these files, all read through the `main` parquet connector:

  data/pypi_projects.parquet     every package name on PyPI (Simple index, PEP 691)
                                 — backs the searchable <Combobox> filters
  data/pypi_top_packages.parquet the top N packages by all-time downloads (name,
                                 downloads) — a ranked catalog snapshot; membership
                                 gate for every other snapshot
  data/pypi_daily_cache.parquet  per-day downloads for those top N packages over the
                                 last --days days — serves the explorer's daily
                                 series and KPI total locally (see clickpy.daily_series),
                                 so popular-package views spend no ClickPy quota
  data/pypi_break_*.parquet      per-package breakdowns (version / python / system /
                                 installer / filetype / country), pre-aggregated for
                                 each global-date preset window (7d/30d/90d/month) —
                                 per-day granularity would be 40–55M rows for the
                                 version/country dimensions, so only the preset
                                 windows are snapshotted; custom ranges go live
                                 (see clickpy.breakdown)
  data/pypi_window_kpis.parquet  exact uniq version/country counts per package per
                                 preset window — the explorer's KPI row

--days must comfortably exceed the longest global date preset (90 days) so cached
windows always cover it; 130 leaves slack for "this month" plus rebuild lag.

Quota: the `play` user is limited to 300 queries per rolling hour; a full build
spends ~170. Run it at most once per hour, and don't share the hour with other
heavy ClickPy work (a mid-build QUOTA_EXCEEDED aborts with a non-zero exit).
"""
import argparse
import datetime as dt
import sys
from pathlib import Path

import duckdb
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from clickpy import ch  # noqa: E402

from dashdown.data.registry import load_connectors  # noqa: E402
from dashdown.render.pipeline import _substitute_params  # noqa: E402

SIMPLE_URL = "https://pypi.org/simple/"
_UA = "dashdown-pypi-explorer/1.0 (+https://clickpy.clickhouse.com)"
DATA = ROOT / "data"

_CONNECTORS = load_connectors(ROOT / "sources.yaml", ROOT)


def _connect(name, sql, params=None):
    """Mirror the `connect` contract Dashdown hands Python queries (queries/*.py):
    ${param} placeholders go through the framework's one blessed escaping."""
    final = _substitute_params(sql, params) if params is not None else sql
    return _CONNECTORS[name].query(final)


def _in_literal(names: list[str]) -> str:
    """An escaped `'a', 'b', …` IN-list literal. Built by hand because Dashdown's
    `IN (${param})` expansion caps at MAX_IN_VALUES=1000 (a DoS guard for
    URL-crafted filter values) and silently drops the rest — fatal for the 5,000-name
    batches this script sends."""
    return ", ".join("'" + n.replace("\\", "\\\\").replace("'", "''") + "'" for n in names)


def _write(df: pd.DataFrame, name: str, select: str) -> None:
    # duckdb reads the pandas frame `df` directly (replacement scan) and writes
    # Parquet natively — no pyarrow needed. Written to a temp name and renamed so
    # a dashboard serving from data/ never reads a half-written file.
    out = DATA / name
    tmp = DATA / f".{name}.tmp"
    duckdb.sql(f"COPY ({select}) TO '{tmp}' (FORMAT parquet)")
    tmp.replace(out)
    print(f"  wrote {len(df):,} rows → {out}  ({out.stat().st_size/1024:.0f} KiB)")


def build_names() -> None:
    print("Fetching the full package index from PyPI (Simple API, JSON)…")
    resp = requests.get(
        SIMPLE_URL,
        headers={"Accept": "application/vnd.pypi.simple.v1+json", "User-Agent": _UA},
        timeout=120,
    )
    resp.raise_for_status()
    df = pd.DataFrame({"name": sorted(p["name"] for p in resp.json()["projects"])})
    _write(df, "pypi_projects.parquet", "SELECT name FROM df")


def build_top(top: int) -> list[str]:
    print(f"Fetching top {top:,} packages by all-time downloads from ClickPy…")
    # LIMIT takes a bare numeric literal, so the argparse int is inlined, not bound.
    df = ch(_connect,
            "SELECT project AS name, sum(count) AS downloads FROM pypi.pypi_downloads "
            f"GROUP BY name ORDER BY downloads DESC LIMIT {int(top)}")
    _write(df, "pypi_top_packages.parquet",
           "SELECT name, downloads FROM df ORDER BY downloads DESC")
    return df["name"].tolist()


def build_daily(names: list[str], days: int) -> None:
    """Fetch the per-day series for `names` in chunks. ClickPy's read-only user
    silently truncates results past one output block (max_result_rows with
    result_overflow_mode=break, observed at 65,409 rows), so each chunk stays
    well under that, and a final 1-row server-side count — immune to truncation —
    verifies nothing was dropped."""
    print(f"Fetching {days}-day daily series for {len(names):,} packages…")
    days = int(days)  # inlined below — today() - N needs a bare integer
    chunk = max(1, 45_000 // days)
    frames = []
    for i in range(0, len(names), chunk):
        batch = names[i:i + chunk]
        frames.append(ch(_connect,
            "SELECT project, date AS day, sum(count) AS downloads "
            "FROM pypi.pypi_downloads_per_day "
            f"WHERE project IN ({_in_literal(batch)}) AND date >= today() - {days} "
            "GROUP BY project, day ORDER BY project, day"))
        print(f"  chunk {i // chunk + 1}/{-(-len(names) // chunk)}: {len(frames[-1]):,} rows")
    df = pd.concat(frames, ignore_index=True)

    check = ch(_connect,
        "SELECT count() AS rows, uniqExact(project) AS projects "
        "FROM (SELECT project, date FROM pypi.pypi_downloads_per_day "
        f"      WHERE project IN ({_in_literal(names)}) AND date >= today() - {days} "
        "      GROUP BY project, date)")
    want_rows, want_projects = int(check["rows"].iloc[0]), int(check["projects"].iloc[0])
    got_projects = df["project"].nunique()
    # A new day's data can land mid-run, so allow up to one day of row drift.
    if got_projects != want_projects or abs(len(df) - want_rows) > want_projects:
        sys.exit(f"Daily cache incomplete: got {len(df):,} rows / {got_projects:,} projects, "
                 f"server has {want_rows:,} rows / {want_projects:,} projects — not writing.")
    _write(df, "pypi_daily_cache.parquet",
           "SELECT project, day, downloads FROM df ORDER BY project, day")


# One entry per breakdown snapshot: the ClickPy rollup table, the SELECT
# expression + output column (mirroring the live SQL in queries/ exactly, empty
# labels included), an extra WHERE, and how many top values to keep per package
# (≥ the largest LIMIT any page query asks of it).
_BREAKS = {
    "version": dict(
        table="pypi.pypi_downloads_per_day_by_version",
        expr="version", label="version", where="AND version != ''", top=25),
    "python": dict(
        table="pypi.pypi_downloads_per_day_by_version_by_python",
        expr="if(python_minor = '', 'unknown', python_minor)", label="python_version",
        where="", top=12),
    "system": dict(
        table="pypi.pypi_downloads_per_day_by_version_by_system",
        expr="if(system = '', 'unknown', system)", label="os", where="", top=8),
    "installer": dict(
        table="pypi.pypi_downloads_per_day_by_version_by_installer_by_type",
        expr="if(installer = '', 'unknown', installer)", label="installer",
        where="", top=8),
    "filetype": dict(
        table="pypi.pypi_downloads_per_day_by_version_by_file_type",
        expr="if(type = '', 'unknown', type)", label="file_type", where="", top=8),
    "country": dict(
        table="pypi.pypi_downloads_per_day_by_version_by_country",
        expr="if(country_code = '', '??', country_code)", label="country",
        where="", top=12),
}

# ClickPy's read-only user runs max_result_rows=1000 with result_overflow_mode=break,
# enforced at *block* boundaries: a single-block result always arrives complete, a
# multi-block one silently truncates after the first block. The breakdown fetches
# therefore return ONE ROW PER PACKAGE (the top-k as an array, exploded locally) —
# ≤ _CHUNK rows per query is structurally a single block. `LIMIT n BY` is unusable
# here: it streams many small blocks and truncates around ~14k rows.
_CHUNK = 1500


def _preset_windows(today: dt.date) -> dict[str, tuple[str, str]]:
    """The global date filter's preset windows, resolved like clickpy.window()."""
    return {
        "7d": ((today - dt.timedelta(days=7)).isoformat(), today.isoformat()),
        "30d": ((today - dt.timedelta(days=30)).isoformat(), today.isoformat()),
        "90d": ((today - dt.timedelta(days=90)).isoformat(), today.isoformat()),
        "month": (today.replace(day=1).isoformat(), today.isoformat()),
    }


def _chunks(names: list[str]):
    for i in range(0, len(names), _CHUNK):
        yield names[i:i + _CHUNK]


def build_windows(names: list[str]) -> None:
    """Snapshot the per-package breakdowns and KPI uniq-counts for each preset
    window. Each package's top-k arrives as one array row (single-block-safe, and
    atomic per project), and each dimension×window is verified against a 1-row
    server-side project count."""
    wins = _preset_windows(dt.date.today())
    for dim, spec in _BREAKS.items():
        print(f"Fetching '{dim}' breakdown for {len(names):,} packages × {len(wins)} windows…")
        frames = []
        for win, (ws, we) in wins.items():
            rows = []
            for batch in _chunks(names):
                arr = ch(_connect,
                    "SELECT project, arraySlice(arrayReverseSort(x -> x.1, "
                    f"  groupArray((downloads, {spec['label']}))), 1, {spec['top']}) AS top "
                    f"FROM (SELECT project, {spec['expr']} AS {spec['label']}, sum(count) AS downloads "
                    f"      FROM {spec['table']} "
                    f"      WHERE project IN ({_in_literal(batch)}) "
                    f"      AND date BETWEEN '{ws}' AND '{we}' {spec['where']} "
                    f"      GROUP BY project, {spec['label']}) "
                    "GROUP BY project ORDER BY project")
                for r in arr.itertuples():
                    rows.extend((r.project, label, int(dl)) for dl, label in r.top)
            df = pd.DataFrame(rows, columns=["project", spec["label"], "downloads"])
            want = int(ch(_connect,
                f"SELECT uniqExact(project) AS projects FROM {spec['table']} "
                f"WHERE project IN ({_in_literal(names)}) "
                f"AND date BETWEEN '{ws}' AND '{we}' {spec['where']}")["projects"].iloc[0])
            got = df["project"].nunique()
            # A new day's data can land mid-run, so allow a little project drift.
            if abs(got - want) > max(len(names) // 100, 10):
                sys.exit(f"'{dim}' {win} snapshot incomplete: got {got:,} projects, "
                         f"server has {want:,} — not writing.")
            df.insert(1, "win", win)
            df.insert(2, "win_start", ws)
            df.insert(3, "win_end", we)
            frames.append(df)
        df = pd.concat(frames, ignore_index=True)
        # An all-empty window frame (e.g. this-month right after a month rolls
        # over, before ClickPy has the new days) is object-dtype and would poison
        # the concat — DuckDB then samples an INT32 and overflows. Pin the dtype.
        df["downloads"] = pd.to_numeric(df["downloads"], errors="coerce").fillna(0).astype("int64")
        _write(df, f"pypi_break_{dim}.parquet",
               f"SELECT project, win, win_start, win_end, {spec['label']}, downloads "
               f"FROM df ORDER BY project, win, downloads DESC")

    print(f"Fetching KPI uniq-counts for {len(names):,} packages × {len(wins)} windows…")
    frames = []
    for win, (ws, we) in wins.items():
        got = []
        for batch in _chunks(names):
            v = ch(_connect,
                   "SELECT project, uniqExact(version) AS versions "
                   "FROM pypi.pypi_downloads_per_day_by_version "
                   f"WHERE project IN ({_in_literal(batch)}) AND date BETWEEN '{ws}' AND '{we}' "
                   "AND version != '' GROUP BY project")
            c = ch(_connect,
                   "SELECT project, uniqExact(country_code) AS countries "
                   "FROM pypi.pypi_downloads_per_day_by_version_by_country "
                   f"WHERE project IN ({_in_literal(batch)}) AND date BETWEEN '{ws}' AND '{we}' "
                   "AND country_code != '' GROUP BY project")
            got.append(v.merge(c, on="project", how="outer"))
        df = pd.concat(got, ignore_index=True)
        df[["versions", "countries"]] = df[["versions", "countries"]].fillna(0).astype(int)
        df.insert(1, "win", win)
        df.insert(2, "win_start", ws)
        df.insert(3, "win_end", we)
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    for col in ("versions", "countries"):  # same empty-window dtype trap as above
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
    _write(df, "pypi_window_kpis.parquet",
           "SELECT project, win, win_start, win_end, versions, countries "
           "FROM df ORDER BY project, win")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--top", type=int, default=5000,
                    help="how many top packages to snapshot (default 5000)")
    ap.add_argument("--days", type=int, default=130,
                    help="how many trailing days of daily data to cache (default 130)")
    args = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    build_names()
    names = build_top(args.top)
    build_daily(names, args.days)
    build_windows(names)
    print("Done.")


if __name__ == "__main__":
    main()
