import pathlib
import sys

import pandas as pd
from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import project  # noqa: E402
from pypi_api import fetch_meta, releases, runtime_deps  # noqa: E402

_COLS = ["summary", "latest_version", "released", "total_releases", "dependencies", "vulnerabilities"]


@query(connector="main", cache_ttl=86400)
def pypi_meta(params, connect):
    """One-row package identity card from the PyPI JSON API: summary, latest
    version + its release date, lifetime release count, direct runtime deps,
    and known vulnerabilities in the latest release. Whole-of-life metadata —
    the header period filter does not apply."""
    doc = fetch_meta(project(params))
    if doc is None:
        return pd.DataFrame(columns=_COLS)
    info = doc.get("info") or {}
    rels = releases(doc)
    latest = info.get("version") or ""
    released = next((r["released"] for r in rels if r["version"] == latest), "")
    return pd.DataFrame([{
        "summary": (info.get("summary") or "").strip(),
        "latest_version": latest,
        "released": released,
        "total_releases": len(rels),
        "dependencies": runtime_deps(info),
        "vulnerabilities": len(doc.get("vulnerabilities") or []),
    }])
