"""One-way render of the database into the Obsidian vault, plus a narrow reader
for the one field a person edits in Obsidian: the verdict in frontmatter.

Direction matters. Two-way sync between a database and a folder of markdown is a
conflict-resolution project, and this is a job search. Postgres owns state;
Obsidian owns thinking and reading."""
from __future__ import annotations

import re
from pathlib import Path

import yaml
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import settings

FRONTMATTER = re.compile(r"^---\n(.*?)\n---\n", re.S)


def _vault() -> Path:
    cfg = settings()
    if not cfg.obsidian_vault:
        raise RuntimeError("OBSIDIAN_VAULT is not set")
    return Path(cfg.obsidian_vault) / cfg.obsidian_folder


def write_application_note(row: dict) -> Path:
    """One note per opportunity, in 01 - Projects/Job Search/applications."""
    folder = _vault() / "applications"
    folder.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", f"{row['company']}-{row['title']}".lower()).strip("-")[:70]
    path = folder / f"{slug}.md"

    fm = {
        "id": str(row["id"]), "company": row["company"], "role": row["title"],
        "url": row.get("url"), "fit": row.get("fit"), "verdict": row.get("verdict") or "",
        "stage": row.get("current_stage") or "not applied", "cv": row.get("recommended_cv"),
        "comp_usd": row.get("comp_usd_year_max"), "captured": str(row["captured_at"])[:10],
        "tags": ["job-search", f"stage/{row.get('current_stage') or 'inbox'}"],
    }
    body = [
        "---", yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip(), "---", "",
        f"# {row['title']} — {row['company']}", "",
        "## Why it scored this way", "", row.get("rationale") or "_not scored yet_", "",
        "## Gaps to prepare", "",
    ]
    for g in row.get("gaps") or []:
        body.append(f"- **{g.get('requirement')}** ({g.get('severity', 'unknown')}) — {g.get('quote', '')[:160]}")
    body += ["", "## My notes", "", "", "## Log", "", "- [ ] applied", "- [ ] followed up (day 7)", ""]
    path.write_text("\n".join(body), encoding="utf-8")
    return path


def read_verdicts() -> dict[str, str]:
    """Labels set by hand in Obsidian frontmatter, pulled back into the database.
    The only field read back — everything else in the note is for the human."""
    out: dict[str, str] = {}
    for p in (_vault() / "applications").glob("*.md"):
        m = FRONTMATTER.match(p.read_text(encoding="utf-8"))
        if not m:
            continue
        fm = yaml.safe_load(m.group(1)) or {}
        if fm.get("verdict") in {"yes", "maybe", "no"}:
            out[str(fm.get("id"))] = fm["verdict"]
    return out


def sync(db: Session) -> dict:
    rows = db.execute(text("""
        select o.id, o.title, o.url, o.captured_at, o.status,
               c.name as company, s.fit, s.rationale, s.gaps,
               j.comp_usd_year_max, j.extraction->>'recommended_cv' as recommended_cv,
               l.verdict, st.current_stage
        from opportunities o
        left join job_details j on j.opportunity_id = o.id
        left join companies c on c.id = j.company_id
        left join labels l on l.opportunity_id = o.id
        left join lateral (select fit, rationale, gaps from scores
                           where opportunity_id = o.id order by created_at desc limit 1) s on true
        left join applications a on a.opportunity_id = o.id
        left join v_application_state st on st.application_id = a.id
        where o.status <> 'rejected_by_rules'
    """)).mappings().all()
    written = [str(write_application_note(dict(r))) for r in rows]
    return {"written": len(written), "folder": str(_vault())}
