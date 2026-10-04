# Engineering Notes: What Broke, and What It Taught Me

*My background is analytics: SQL, BI, data science. This project was where I learned the parts around the analysis: building an API, a web app, automated tests, a scheduled job and a cloud database. These are the problems that taught me the most, written up honestly, including the ones I caused myself. The design choices behind them are in `decisions.md`.*

## The short version

Most of what I learned didn't come from building features. It came from things breaking in ways I didn't expect. The app slowed to **45 seconds per page** the day I moved the database to the cloud. The automated job **failed on GitHub while working fine on my laptop**. My own deck **silently skipped every other posting**. One data source **sent job postings with no description at all**. Each one taught me something I now check for by default.

## 1. The page that took 45 seconds: the N+1 query problem

The day I moved the database from my laptop to a hosted Postgres on Neon, one page, the list of roles to apply to, went from instant to **45 seconds**. Other pages were fine.

The cause was a classic: the **N+1 query problem**. To build that list, the code ran one query for the list and then about five more *per posting* (its score, its company, its label, whether I'd applied). With around a hundred postings, that's roughly 500 queries. On my laptop each query took about a millisecond, so nobody noticed. Against a cloud database, each one is a round trip over the internet, around 90 milliseconds. 500 × 90 ms ≈ 45 seconds, which is exactly what the logs showed.

The fix was to load related data in bulk: one query per *kind* of data instead of one per posting. I tested it against a scratch database with 160 postings. The output was identical, and loading that page went from **345 queries to 6**.

**What I took from it:** the code wasn't slower; the distance was longer. "Fast enough" depends on where the database lives, and moving infrastructure can expose a bug that was there all along.

## 2. "It works on my machine" — GitHub disagreed

The first runs of the scheduled job on GitHub failed twice, for two different reasons, while everything worked on my laptop.

- **The install failed on a clean machine.** My laptop's Docker setup had hidden a packaging problem: on a fresh install, Python's packaging tool found two top-level folders and refused to guess which one was the app. One line in `pyproject.toml` telling it explicitly fixed it.
- **"No such command: pull-all."** The workflow was running the version of the code in the repository, and I hadn't pushed my latest changes. Obvious in hindsight, but it changed how I work: GitHub runs what's committed, not what's on my disk.

**What I took from it:** a CI machine is the most honest test environment I have, because it starts from nothing every time. Now the tests run on every push, and I run them locally before pushing.

## 3. Designing a job that fails honestly

A job that runs at 8 a.m. with nobody watching has to answer one question clearly: did it work? I made three choices so the answer is never ambiguous:

- **Each source runs and saves on its own.** If one public API is down, its work is rolled back and reported, and the other sources still deliver. The job only fails if *every* source fails.
- **A failure can't hide behind a pipe.** The workflow copies the output into a run summary. Without the right shell setting, a crash in the first command would be masked by the success of the second. One setting (`pipefail`) makes the step fail when it should.
- **Tests that simulate bad mornings:** a source that throws an error, a source that returns nothing, no sources at all. A quiet day is not a failure; a broken source is not a total failure.

**What I took from it:** for unattended jobs, the error handling *is* the feature.

## 4. My deck was skipping every other posting

For a while, postings I hadn't decided on kept "reappearing" after a reload, as if I'd missed them. I had: the deck was **silently skipping every other card**.

When I decided on a posting, two things happened. The list removed the decided posting, so the next one moved into its place, *and* the position counter moved forward one. Two steps per decision. Every second posting got jumped over without ever being shown.

The fix was one line: remove the decided card and leave the position alone. Finding it took much longer than fixing it.

**What I took from it:** the most dangerous bugs don't crash; they quietly give you a wrong number. I only caught it because the progress count didn't match what I'd seen.

## 5. A source that tells the truth by leaving things out

One job API (Jobgether) returns titles, companies, pay and location, but **no job description**. My scorer reads the description for two of its six dimensions, which are 56% of the score. So every role from that source scored low, not because it was a bad fit, but because there was nothing to read.

I handled it in two places. The adapter builds a header from all the metadata the source *does* send, so pay, level and geography still score correctly. And any posting without a real description gets a visible "partial score" flag. A test ties the two together, so if someone changes the marker text in one place, the test fails loudly instead of the flag quietly disappearing.

**What I took from it:** a score that looks precise but isn't is worse than no score. Be explicit when the data is incomplete.

## 6. Real data is messier than test data

To give the funnel history from day one, I imported the applications I'd tracked by hand in a spreadsheet. It became the most heavily tested part of the project (42 tests), because real data fought back at every step:

- **Encoding:** Excel on Windows doesn't save CSV files as UTF-8 by default, so accented characters came out garbled until the importer tried several encodings.
- **Dates:** 03/04 could be March 4th or April 3rd. The importer looks for evidence in the file itself (a day above 12) to decide the format, instead of guessing.
- **Salary:** some cells held the amount I asked for, others the range a posting offered, in different currencies and formats.

**What I took from it:** most of data engineering is deciding what to do with the rows that don't fit, and making those decisions visible instead of silent.

## 7. Two smaller lessons

- **`localhost` means "this device".** When I opened the app on my phone, pages loaded but buttons did nothing: the phone was trying to reach an API on the phone. Routing every request through the web server running on my computer fixed it, with no security changes and nothing exposed to the internet.
- **Secrets never touch the code.** The database password lives only in a local `.env` file (excluded from git) and in GitHub's encrypted secrets. Logs mask it automatically.

## What I take away

Before this project, I would have said the hard part of building software is writing it. Now I'd say it's knowing how it fails: under latency, on a clean machine, with nobody watching, with data that doesn't match the spec. Each of those failures made the system better, and each is now a test or a habit rather than a surprise.
