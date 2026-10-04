# Job Funnel: Turning My Job Search Into a Pipeline

*I built this to fix a real bottleneck in my own job search, and to teach myself the engineering side of data work: APIs, a web front end, CI/CD, scheduled jobs and a cloud database. The numbers here are my own before-and-after, not a controlled study, and I've tried to be clear about what the tool can and can't claim. Every judgment call is in `decisions.md`; what broke along the way is in `reports/engineering.md`.*

## The short version

My problem was never finding job postings. It was **evaluating them**. I was saving 11–15 roles a week and spending about **4 hours** reviewing them, even with Claude helping me read. Most of that time went into postings that turned out to be an obvious no: "remote" roles that actually required living in the US, staffing agencies, pay below what I need.

So I built a pipeline that does that reading for me. Every weekday morning it pulls new roles from public job APIs, **filters out the ones I can't or shouldn't take, scores the rest**, and lines them up in a deck I can clear one keystroke at a time. The decision stays with me.

The practical result: **from 11–15 roles a week to a pool of 30–35, reviewed in 30–60 minutes instead of 4 hours.** That's more than twice the volume, in a quarter of the time or less.

## 1. The bottleneck was reading, not judging

Before building anything, I looked at where my time actually went. My yes/no calls were quick once I knew the facts. What took hours was getting to the facts: scrolling a long posting to find out, at the bottom, that it was "US only" or came through an agency.

That changed what I built. A tool that made better decisions for me would have solved a problem I didn't have. What I needed was a tool that **ends the obvious no's before I ever see them**, and puts the useful facts for the rest (pay, level, where I can work from, what I'm missing) at the top.

## 2. Three filters, each more expensive than the last

The pipeline is built around one idea: spend the cheapest effort first.

- **Filter 1: rules and a score (automatic, zero cost).** Hard rules drop staffing agencies, onsite or hybrid roles, pay below my floor, roles outside my target families, and roles restricted to countries I can't work from. Everything that survives gets a 0–100 fit score from six weighted dimensions.
- **Filter 2: the deck (seconds per role).** One posting at a time: yes, maybe or no, with a single keystroke, or a tap on my phone.
- **Filter 3: the close read (minutes per role).** The yeses and maybes get read properly, and only then do I apply or drop.

The third step mattered more than I expected. In my first version there were only two, and "maybe" had nowhere to go, so in practice it meant "never". Giving maybes their own place to land, and making "drop" reversible, is what made the quick pass trustworthy.

## 3. "Remote" was the biggest trap

The single most useful rule wasn't about skills or pay. It was about **geography**. A large share of postings labeled "remote" really mean "remote within the US". They look like matches and survive every other filter, which made them the most expensive no's of all.

The rule keeps roles open globally or to Latin America and rejects roles restricted elsewhere. One design choice I'm glad I made: **a posting that says nothing about location is never rejected for it.** The rule only removes roles that clearly say no, so it can't silently cost me a good one.

## 4. A score I can defend line by line

I deliberately used a **rules-based scorer, not an LLM**. Six dimensions with explicit weights: domain (28%), craft (28%), comp (18%), level fit (14%), channel (7%) and language (5%). It costs nothing, runs instantly, and every point traces back to a matched keyword or a parsed field.

Two choices made it more honest than a naive keyword count:

- **Unpublished pay scores neutral, not zero.** Most companies don't publish ranges. Treating silence as "low pay" would have buried most good roles.
- **Thin postings get a flag instead of a confident number.** One of my sources sends no job description at all. Without text, domain and craft (56% of the score) collapse toward zero, so a good role from that source scores low for the wrong reason. The app says "this score is partial" rather than pretending to be precise.

The score is for **sorting and discarding**, not deciding. That's the right job for a keyword model, and I'd rather say so plainly than oversell it.

## 5. It runs without me

The search runs as a **GitHub Actions workflow every weekday at 08:00**, against a Postgres database hosted on Neon. Each run writes a short summary I can read without opening the logs. In one recent run it checked 302 postings across 7 sources: 286 were roles it had already seen, 11 were filtered out by the rules, and 5 were new. That ratio is the point. Deduplication and filtering are what keep the deck short enough to clear in one sitting.

It's built to survive bad mornings: each source runs and saves on its own, so if one API is down, the others still deliver, and the run reports exactly which source failed. Tests run automatically on every change, so a mistake gets caught before it reaches the daily search.

## What I'd do next

1. **Add sources one at a time.** Ashby and Lever company boards first (they work like the Greenhouse boards I already use), then Himalayas. Each source has its own quirks, so each comes with its own tests.
2. **Widen the keyword queries** for BI and data science roles, which match my background but are under-covered today.
3. **Measure the scorer against my own labels.** Every yes/maybe/no I make is ground truth. With enough of them, I can check whether the score actually ranks roles the way I do, and tune the weights with evidence instead of instinct.

## What this project can and can't say

I want to be straight about this part.

- **The time savings are my own before-and-after.** Same kind of search, same person, before and after the tool. It's a real change in my week, but it isn't a controlled comparison, and some of the improvement comes simply from having a routine.
- **More roles isn't the same as better outcomes.** The tool shows me more of the right kind of role faster. Whether that turns into more interviews is a separate question, and it will take months of data to answer.
- **The funnel can't pick my best CV.** At my volume, a fair comparison between two CV versions would need on the order of a thousand applications per version. The funnel is good at spotting leaks (roles I liked but never applied to), not at A/B conclusions. I built it knowing that, and I'd rather name the limit than declare a winner from twenty applications.
- **Some sources are partial.** Roles from sources that don't send a description are scored on metadata only, and the app flags them. For those, I always open the original posting before deciding.

The honest summary: this didn't make me a better judge of jobs. It gave me back the hours I was spending to *get to* the judgment, and that's what I set out to fix.
