# Vault layout

Fits the existing structure rather than replacing it. Only `01 - Projects/Job Search`
is written by the sync; everything else stays yours.

```
00 - Inbox
01 - Projects
   Project CV                       ← the two CV variants live here already
   Job Search                       ← written by `funnel sync`, one-way
      _dashboard.md                    the weekly read
      applications/
         kestrel-markets-senior-product-analyst.md
         orchard-pay-growth-analyst.md
      artifacts/
         kestrel-markets-note.md            approved drafts, kept for reuse
02 - Knowledge
   AI · Business · Programming
03 - Skills
04 - Decisions                      ← one note per irreversible call, see template
05 - Research
06 - Templates                      ← the two templates below
99 - Archive
```

## How the two systems divide

The database owns **state**: what was captured, scored, decided, applied to, and
what happened next. The vault owns **thinking**: why a role was interesting, what
came up in a call, what to prepare.

The sync is one-way, database to vault, with a single exception — the `verdict:`
field in a note's frontmatter is read back. So a posting can be decided from the
phone, in Obsidian, on the train, and the deck will agree.

Do not edit anything else in `applications/`; the next sync overwrites it. Notes
go under the `## My notes` heading, which the renderer preserves.

## Dataview queries worth having

Put these in `_dashboard.md`:

````
```dataview
TABLE company, fit, stage, comp_usd
FROM "01 - Projects/Job Search/applications"
WHERE verdict = "yes" AND stage = "not applied"
SORT fit DESC
```
````

That query is the whole problem in five lines: everything judged worth applying
to, that has not been applied to yet.

````
```dataview
TABLE company, stage, captured
FROM "01 - Projects/Job Search/applications"
WHERE stage = "applied" AND date(today) - date(captured) > dur(7 days)
```
````
