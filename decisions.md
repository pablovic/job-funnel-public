# Decisions

Every judgment call in this project, why I made it, and what I gave up. Most of these are trade-offs, not right answers. Writing them down is how I keep myself honest about which is which.

---

## Scope

### 1. Automate the reading, not the deciding

**Decision:** the system filters, scores and explains. I decide yes / maybe / no, and I submit every application myself.

**Why:** my bottleneck was the hours of reading that ended in an obvious no, not the quality of my judgment. Automating the judgment would have solved a problem I didn't have. Separately, my labels are the only ground truth the scorer can ever be measured against. If the system wrote them, it would be grading itself.

**Gave up:** a "fully automatic" story. The honest version is better in an interview anyway.

### 2. No LinkedIn scraping

**Decision:** LinkedIn, Gupy and Wellfound roles come in through a paste box. Only sources with public APIs are pulled automatically.

**Why:** those sites block programmatic access, and scraping them breaks their terms and risks the account. A five-second paste is a better trade than a fragile scraper that could get me banned from the main place I job hunt.

**Gave up:** coverage. A large share of what I see still arrives by hand.

### 3. Single user, no login

**Decision:** no authentication, no `user_id` anywhere.

**Why:** it's a personal tool and a portfolio piece. Multi-user support would add a week of work that nobody, including me, would use.

---

## Filtering and scoring

### 4. A rules scorer instead of an LLM

**Decision:** the default scorer is a weighted keyword model with six explicit dimensions. The code can call an LLM provider, but it's off by default.

**Why:** three reasons. It costs nothing and has no rate limit. Every point of the score traces back to a matched keyword, which I can defend line by line. And an earlier hand-built rules scorer already separated my clear rejections well. Where an LLM would help most, the "yes vs. maybe" band, is exactly where I open and read the posting myself anyway.

**Gave up:** nuance on oddly written postings, and prose explanations. I get "keyword match on: sql, growth, ab_testing" instead of a paragraph.

### 5. Three filters, each more expensive than the last

**Decision:** rules (automatic) → Decide (seconds per role) → close read (minutes per role).

**Why:** a two-step flow forced a bad choice. Either every "yes" in the quick pass became an application without a proper read, or I read everything properly and the quick pass saved nothing. The third step gives "maybe" somewhere to land. Without it, "maybe" quietly meant "never".

### 6. "Remote" is not enough: filter on *where* you can work from

**Decision:** a geography rule that keeps roles open globally or to Latin America, and rejects roles restricted to other countries. A posting that says nothing about location is never rejected for it.

**Why:** a large share of "remote" postings are really "US remote" and require living in the US. They looked like matches and wasted the most time. Treating "unknown" as eligible means the rule only removes roles that clearly say no.

### 7. Unpublished pay scores 5 out of 10, not 0

**Decision:** the comp dimension gives a neutral score when a posting doesn't publish salary.

**Why:** silence isn't evidence about pay. Scoring it as zero would have pushed down most good roles, because most companies don't publish ranges.

### 8. Flag thin postings instead of trusting their score

**Decision:** postings shorter than 400 characters, or from sources that send no description (Jobgether), get a visible flag.

**Why:** domain and craft are 56% of the score and both come from reading the description. Without text, a good role scores low for the wrong reason. A flag that says "this score is partial" is more honest than a precise-looking number.

### 9. Filter by role family on the title only

**Decision:** a role must match a target family (data, analytics, BI, product, growth, experimentation...) in its title.

**Why:** company boards publish everything. A food company posts dishwasher jobs, a data company posts sales jobs. Before this rule, those only got dropped if they happened to pay below my floor, which is an accident, not a criterion. The title is the most reliable field.

---

## Data

### 10. Event-sourced applications

**Decision:** each stage change (applied, screening, technical, rejected...) is a new row. Nothing is ever updated in place.

**Why:** it costs one join and turns questions like "how many days until the first response?" into a query instead of archaeology.

### 11. Dropped roles are archived, not deleted

**Decision:** "Drop" on the close-read screen sets a status and can be undone.

**Why:** the gap between "roles I liked" and "roles I applied to" is one of the most useful things the funnel shows. Deleting drops would erase it.

### 12. Backfill my real history from a spreadsheet

**Decision:** a `backfill` command imports the applications I had already tracked by hand before the app existed.

**Why:** the funnel is only useful with real data in it. Starting from zero would have meant weeks before it said anything. The import had to handle Windows file encodings, different date formats and inconsistent salary text, which turned out to be most of the work.

---

## Infrastructure

### 13. GitHub Actions for the daily search, not a local scheduler

**Decision:** the weekday pull runs as a scheduled GitHub Actions workflow.

**Why:** a Windows scheduled task would have worked, but only when my laptop was on, and it would have taught me nothing transferable. GitHub Actions is the standard tool for this, and learning it was part of the point: cron syntax in UTC, encrypted secrets, run summaries, and failing loudly when something breaks.

**Gave up:** nothing meaningful. It's free at this volume. One thing to know: GitHub pauses scheduled workflows after 60 days without repository activity.

### 14. Move the database to Neon

**Decision:** Postgres moved from a local Docker container to Neon's free tier.

**Why:** a workflow running on GitHub's machines can't reach a database on my laptop. A hosted database was required for the automation, and Neon's free tier is enough for this size.

**Gave up:** speed. Every query now crosses the internet. That exposed a real performance bug (see `reports/engineering.md`).

### 15. One commit per source, and one broken source never stops the others

**Decision:** the daily pull processes each source in its own transaction. If one fails, it's rolled back and reported, and the rest continue. The job only fails if *every* source fails.

**Why:** public APIs go down. A Tuesday-morning outage at one source shouldn't throw away what the other six found.

### 16. Use the app from my phone through the same server

**Decision:** the browser talks to the API through the Next.js server (`/api/...`), instead of calling the API directly.

**Why:** on a phone, `localhost` means the phone. Routing through the server that's already running on my computer made the app work on my phone over home Wi-Fi with no CORS changes and no public deployment, so my data never left my own network.

**Gave up:** use outside my home network. That's a deliberate limit for now.

---

## What I deliberately didn't do

- **A/B test my CV versions.** At my volume the test can't reach significance; the funnel would need on the order of a thousand applications per version. Reading a 6% vs. 9% difference on twenty applications as a winner is exactly the mistake I wanted to avoid.
- **Deploy publicly.** A public URL would need a login to protect my application history. That's real work with no benefit for a single user.
- **Add every job board at once.** Each new source brings its own quirks (Jobgether taught me that). Sources get added one at a time, with tests.
