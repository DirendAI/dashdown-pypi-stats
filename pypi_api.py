"""Helpers for the PyPI JSON API (https://pypi.org/pypi/<name>/json).

Free and unauthenticated, served from PyPI's CDN — it returns the package's
*metadata* (summary, license, latest version, dependency list, release history,
known vulnerabilities), complementing the ClickPy download counts. Everything
here is whole-of-life data: the header period filter does not apply.

Documents are memoised in-process for an hour so the several queries on one
page share a single HTTP round-trip per package; the ``@query(cache_ttl=…)``
layer above handles day-scale caching of the derived tables.
"""
import json
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

import certifi

_UA = "dashdown-pypi-stats/1.0 (analytics dashboard; gregor.hren@dirend.ai)"
# python.org macOS builds ship no system CAs — verify against certifi's bundle,
# same as the clickhouse connector in sources.yaml.
_CTX = ssl.create_default_context(cafile=certifi.where())
_TTL_OK = 3600  # a fetched document (including a definite 404) holds for an hour
_TTL_ERR = 60  # a network failure retries soon — don't pin an outage for an hour
_cache: dict = {}  # name -> (monotonic stamp, ttl, doc-or-None)


def fetch_meta(name: str):
    """The package's JSON API document as a dict, or None when the package
    doesn't exist or the API is unreachable."""
    now = time.monotonic()
    hit = _cache.get(name)
    if hit and now - hit[0] < hit[1]:
        return hit[2]
    url = f"https://pypi.org/pypi/{urllib.parse.quote(name, safe='')}/json"
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10, context=_CTX) as resp:
            doc, ttl = json.load(resp), _TTL_OK
    except urllib.error.HTTPError as e:
        # 404 = the package genuinely doesn't exist — cache that like a hit.
        doc, ttl = None, _TTL_OK if e.code == 404 else _TTL_ERR
    except Exception:
        doc, ttl = None, _TTL_ERR
    _cache[name] = (now, ttl, doc)
    return doc


def releases(doc) -> list:
    """(version, released, files) — one row per release that has at least one
    uploaded file, newest first. `released` is the ISO date of the version's
    earliest upload."""
    out = []
    for version, files in (doc.get("releases") or {}).items():
        stamps = [f["upload_time_iso_8601"] for f in files if f.get("upload_time_iso_8601")]
        if stamps:
            out.append({"version": version, "released": min(stamps)[:10], "files": len(files)})
    out.sort(key=lambda r: r["released"], reverse=True)
    return out


def runtime_deps(info) -> int:
    """Count of direct runtime dependencies — requires_dist entries minus the
    ones gated behind an extra (`; extra == "test"` and friends)."""
    return sum(1 for d in (info.get("requires_dist") or []) if "extra ==" not in d)


def license_of(info) -> str:
    """A short license label: the PEP 639 expression when present, else the
    trove classifier, else the raw `license` field when it isn't a whole
    license text pasted in."""
    expr = (info.get("license_expression") or "").strip()
    if expr:
        return expr
    for c in info.get("classifiers") or []:
        if c.startswith("License ::"):
            return c.split("::")[-1].strip()
    raw = (info.get("license") or "").strip()
    return raw if len(raw) <= 60 else raw[:57] + "…"


def dev_status(info) -> str:
    """The Development Status trove classifier, e.g. '5 - Production/Stable'."""
    for c in info.get("classifiers") or []:
        if c.startswith("Development Status ::"):
            return c.split("::")[-1].strip()
    return ""


def author_of(info) -> str:
    """Author (or maintainer) display name, parsed out of the email field when
    that's the only place it lives ('Jane Doe <jane@…>' → 'Jane Doe')."""
    for key in ("author", "maintainer"):
        name = (info.get(key) or "").strip()
        if name:
            return name
    for key in ("author_email", "maintainer_email"):
        raw = (info.get(key) or "").split("<")[0].strip().strip('"')
        if raw:
            return raw
    return ""


def project_url(info, *labels) -> str:
    """The first matching entry in project_urls (case-insensitive), e.g.
    project_url(info, 'repository', 'source', 'source code', 'github')."""
    urls = {str(k).strip().lower(): v for k, v in (info.get("project_urls") or {}).items()}
    for label in labels:
        if urls.get(label):
            return urls[label]
    return ""
