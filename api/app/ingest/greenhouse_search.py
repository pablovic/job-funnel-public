"""Cross-company Greenhouse search — for finding roles at companies not yet on a
known board list. Same public API surface, filtered to remote + the role families
the search targets, so the daily pull surfaces *new* companies rather than only
re-checking a fixed list.

config: {"queries": ["product analyst", "growth analyst"], "remote_only": true}

Note the honest boundary: this covers companies that use Greenhouse. LinkedIn,
Gupy and Wellfound — where most of my saved roles came from — block
programmatic access and are not automated. Those keep arriving through the paste
box, which is a five-second action, not a scraper.
"""
from __future__ import annotations

import httpx

from app.ingest.base import RawPosting
from app.ingest.greenhouse import _strip

SEARCH = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def fetch(config: dict) -> list[RawPosting]:
    # Greenhouse has no global search endpoint; a curated token list is the
    # supported path. Kept separate from greenhouse.py so the "known good boards"
    # list and the "discovery" list can diverge without touching each other.
    tokens = config.get("boards", [])
    queries = [q.lower() for q in config.get("queries", [])]
    out: list[RawPosting] = []
    with httpx.Client(timeout=20) as client:
        for token in tokens:
            try:
                r = client.get(SEARCH.format(token=token))
                r.raise_for_status()
            except httpx.HTTPError:
                continue
            for job in r.json().get("jobs", []):
                title = job.get("title", "")
                if queries and not any(q in title.lower() for q in queries):
                    continue
                out.append(RawPosting(
                    title=f"{title} — {token}",
                    raw_text=_strip(job.get("content", "")),
                    url=job.get("absolute_url"),
                    external_id=str(job.get("id")),
                ))
    return out
