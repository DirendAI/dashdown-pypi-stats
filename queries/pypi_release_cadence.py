import pathlib
import sys

import pandas as pd
from dashdown import query

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from clickpy import project  # noqa: E402
from pypi_api import fetch_meta, releases  # noqa: E402


@query(connector="main", cache_ttl=86400)
def pypi_release_cadence(params, connect):
    """Releases per quarter over the package's whole life, zero-filled so quiet
    quarters show as gaps in the bar chart rather than vanishing."""
    doc = fetch_meta(project(params))
    rows = releases(doc) if doc else []
    if not rows:
        return pd.DataFrame(columns=["quarter", "releases"])
    quarters = pd.PeriodIndex(pd.to_datetime([r["released"] for r in rows]), freq="Q")
    counts = quarters.value_counts().sort_index()
    full = pd.period_range(quarters.min(), quarters.max(), freq="Q")
    counts = counts.reindex(full, fill_value=0)
    return pd.DataFrame({
        "quarter": [f"{p.year} Q{p.quarter}" for p in full],
        "releases": counts.to_numpy(),
    })
