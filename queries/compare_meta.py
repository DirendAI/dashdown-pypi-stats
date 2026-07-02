import pathlib
import sys

import pandas as pd
from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import packages  # noqa: E402
from pypi_api import fetch_meta, license_of, releases, runtime_deps  # noqa: E402


@query(connector="main", cache_ttl=86400)
def compare_meta(params, connect):
    """One PyPI-JSON-API metadata row per compared package, in selection order.
    A package the API doesn't know still gets its row, so the table always
    mirrors the selection."""
    rows = []
    for proj in packages(params):
        doc = fetch_meta(proj)
        info = (doc.get("info") or {}) if doc else {}
        rels = releases(doc) if doc else []
        latest = info.get("version") or ""
        rows.append({
            "project": proj,
            "summary": (info.get("summary") or "").strip(),
            "latest_version": latest,
            "released": next((r["released"] for r in rels if r["version"] == latest), ""),
            "releases": len(rels),
            "dependencies": runtime_deps(info) if doc else None,
            "license": license_of(info),
            "vulnerabilities": len(doc.get("vulnerabilities") or []) if doc else None,
        })
    return pd.DataFrame(rows)
