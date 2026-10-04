"""Greenhouse job boards. Public JSON API, no key, no scraping, no terms
violation — which is exactly why this is the first automated source and LinkedIn
is not. The good slice of the market for this search (USD-paying product companies with
direct applications) posts here.

config: {"boards": ["company-a", "company-b"]}
"""
from __future__ import annotations

import html
import re

import httpx

from app.ingest.base import RawPosting

BOARD = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs?content=true"


def _strip(raw_html: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw_html)).split())


def fetch(config: dict) -> list[RawPosting]:
    out: list[RawPosting] = []
    with httpx.Client(timeout=20) as client:
        for token in config.get("boards", []):
            try:
                r = client.get(BOARD.format(token=token))
                r.raise_for_status()
            except httpx.HTTPError:
                continue
            for job in r.json().get("jobs", []):
                offices = ", ".join(o.get("name", "") for o in job.get("offices", []) or [])
                out.append(RawPosting(
                    title=f"{job['title']} — {token}",
                    raw_text=_strip(job.get("content", "")),
                    url=job.get("absolute_url"),
                    external_id=str(job.get("id")),
                    company=token,
                    location=job.get("location", {}).get("name", "") or offices,
                ))
    return out
