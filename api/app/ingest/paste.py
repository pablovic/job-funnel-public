"""The manual source. Not a fallback — the primary one.

Most high-fit postings arrive through a saved list, a newsletter or a message
from someone, and no scraper sees those. The paste box exists so capture takes
five seconds and never depends on a source adapter existing yet."""
from __future__ import annotations

from app.ingest.base import RawPosting


def fetch(config: dict) -> list[RawPosting]:
    return [RawPosting(title=config["title"], raw_text=config["raw_text"], url=config.get("url"))]
