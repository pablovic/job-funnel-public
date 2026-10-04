"""Source adapters. Each returns raw postings; normalization happens once, in
the pipeline, so a new source is ~30 lines and cannot invent its own schema."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass
class RawPosting:
    title: str
    raw_text: str
    url: str | None = None
    external_id: str | None = None
    # Structured fields the source already provides. These beat regex every time,
    # and they are why the free path costs nothing: for ATS and job-board sources
    # there is essentially nothing left to "extract".
    company: str = ""
    salary: str = ""
    location: str = ""


class Adapter(Protocol):
    def fetch(self, config: dict) -> list[RawPosting]: ...
