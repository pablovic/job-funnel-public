"""Eval harness. The labeled set is the product's only ground truth, so this is
the only place that can say whether a prompt change helped.

Metrics, and why each one is here:

- **recall on yes+maybe** — the cost asymmetry is not symmetric. Missing a
  great role costs a job; showing one extra posting costs thirty seconds. Recall
  is the gate; precision is a comfort metric.
- **spearman** — rank agreement with the human verdict. The hand-built scorer
  reached 0.67, which separated the clear "no" but not "yes" from "maybe". That
  is the number to beat.
- **hallucination_rate** — share of generations citing text absent from the
  posting. Must be 0 to ship.
- **cost_per_posting / p50_latency** — a scorer nobody can afford to run is a
  scorer that does not exist.
"""
from __future__ import annotations

import json
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path

from scipy.stats import spearmanr

from app.agents import scorer
from app.agents.client import quoted_in_source

VERDICT_RANK = {"no": 0, "maybe": 1, "yes": 2}
BASELINE = {"recall_yes_maybe": 0.90, "spearman": 0.67, "hallucination_rate": 0.0}


@dataclass
class EvalMetrics:
    n: int
    recall_yes_maybe: float
    precision_yes_maybe: float
    spearman: float
    hallucination_rate: float
    cost_per_posting: float
    p50_latency_ms: float
    passed: bool


def run(goldens_path: str | Path, profile: str, threshold: float = 55.0) -> EvalMetrics:
    rows = [json.loads(l) for l in Path(goldens_path).read_text().splitlines() if l.strip()]
    fits, truths, costs, latencies, halluc = [], [], [], [], 0

    for r in rows:
        res, ungrounded = scorer.score(r["raw_text"], r["title"], profile)
        halluc += bool(ungrounded)
        fits.append(res.data["fit"])
        truths.append(VERDICT_RANK[r["verdict"]])
        costs.append(res.cost_usd)
        latencies.append(res.latency_ms)

    predicted_yes = [f >= threshold for f in fits]
    actual_yes = [t >= 1 for t in truths]
    tp = sum(p and a for p, a in zip(predicted_yes, actual_yes))
    fn = sum((not p) and a for p, a in zip(predicted_yes, actual_yes))
    fp = sum(p and (not a) for p, a in zip(predicted_yes, actual_yes))

    m = EvalMetrics(
        n=len(rows),
        recall_yes_maybe=round(tp / (tp + fn), 3) if tp + fn else 0.0,
        precision_yes_maybe=round(tp / (tp + fp), 3) if tp + fp else 0.0,
        spearman=round(float(spearmanr(fits, truths).statistic), 3),
        hallucination_rate=round(halluc / len(rows), 3),
        cost_per_posting=round(statistics.mean(costs), 4),
        p50_latency_ms=round(statistics.median(latencies)),
        passed=False,
    )
    m.passed = (m.recall_yes_maybe >= BASELINE["recall_yes_maybe"]
                and m.spearman >= BASELINE["spearman"]
                and m.hallucination_rate <= BASELINE["hallucination_rate"])
    return m


if __name__ == "__main__":
    import sys
    from app.db import SessionLocal
    from app.pipeline import build_profile

    with SessionLocal() as db:
        metrics = run(sys.argv[1] if len(sys.argv) > 1 else "app/evals/goldens.jsonl", build_profile(db))
    print(json.dumps(asdict(metrics), indent=2))
    raise SystemExit(0 if metrics.passed else 1)
