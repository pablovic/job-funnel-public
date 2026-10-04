"""Remotive — the discovery source. This is the finder that surfaces companies
the search does NOT already know, as opposed to greenhouse.py which re-polls a known
watchlist.

Public API, free, no key: https://remotive.com/api/remote-jobs
Confirmed live 2026, remote-only listings, keyword + category filters.

Their terms, honored here:
  - Attribution required: the job's Remotive URL is kept as the canonical link.
  - Cache, don't hammer: they ask for no more than a few requests per day, which
    is exactly the weekday-cron cadence — never call this synchronously per page.
  - Do not republish their jobs to other boards. We don't; this is a private
    personal funnel, not a public listing.

config: {"search": "product analyst", "category": "data", "limit": 40}

The enrichment surface: widen or narrow `search`, add categories. When a role
here comes from a company worth watching, add that company's board token to the
greenhouse_boards source — discovery promotes into the watchlist.
"""
from __future__ import annotations

import html
import re

import httpx

from app.ingest.base import RawPosting

API = "https://remotive.com/api/remote-jobs"


def _strip(raw_html: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", raw_html or "")).split())


def fetch(config: dict) -> list[RawPosting]:
    params = {}
    if config.get("search"):
        params["search"] = config["search"]
    if config.get("category"):
        params["category"] = config["category"]
    if config.get("limit"):
        params["limit"] = config["limit"]

    try:
        with httpx.Client(timeout=20, headers={"User-Agent": "job-funnel/personal"}) as client:
            r = client.get(API, params=params)
            r.raise_for_status()
            jobs = r.json().get("jobs", [])
    except (httpx.HTTPError, ValueError):
        return []

    return [parse_job(j) for j in jobs]


def parse_job(job: dict) -> RawPosting:
    """Split out so it can be unit-tested without a network call."""
    company = job.get("company_name", "")
    title = job.get("title", "")
    # Prepend company + salary text into the raw body so the normalizer and the
    # published-salary rule see them even when the HTML description omits them.
    header = f"{title} at {company}."
    if job.get("salary"):
        header += f" Salary: {job['salary']}."
    if job.get("candidate_required_location"):
        header += f" Location: {job['candidate_required_location']}."
    body = header + "\n\n" + _strip(job.get("description", ""))
    return RawPosting(
        title=f"{title} — {company}",
        raw_text=body,
        url=job.get("url"),                       # canonical Remotive URL (attribution)
        external_id=str(job.get("id", "")),
        company=company,
        salary=job.get("salary", "") or "",
        location=job.get("candidate_required_location", "") or "",
    )
