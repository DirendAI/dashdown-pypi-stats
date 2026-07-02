import pathlib
import sys

import pandas as pd
from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import project  # noqa: E402
from pypi_api import author_of, dev_status, fetch_meta, license_of, project_url  # noqa: E402


@query(connector="main", cache_ttl=86400)
def pypi_facts(params, connect):
    """Field/value facts about the package from the PyPI JSON API — author,
    license, Python requirement, links — for the explorer's facts table.
    Empty fields are dropped so the table only shows what the package declares."""
    proj = project(params)
    doc = fetch_meta(proj)
    if doc is None:
        return pd.DataFrame(columns=["field", "value"])
    info = doc.get("info") or {}
    keywords = info.get("keywords") or ""
    if isinstance(keywords, list):
        keywords = ", ".join(keywords)
    facts = [
        ("Author", author_of(info)),
        ("License", license_of(info)),
        ("Requires Python", (info.get("requires_python") or "").strip()),
        ("Development status", dev_status(info)),
        ("Homepage", project_url(info, "homepage", "home") or (info.get("home_page") or "").strip()),
        ("Repository", project_url(info, "repository", "source", "source code", "code", "github")),
        ("Documentation", project_url(info, "documentation", "docs")),
        ("PyPI page", f"https://pypi.org/project/{proj}/"),
        ("Keywords", keywords.strip()[:120]),
    ]
    return pd.DataFrame([{"field": f, "value": v} for f, v in facts if v])
