"use client";

import { useCallback, useEffect, useState } from "react";
import useSWR from "swr";
import { api, fetcher } from "@/lib/api";
import type { Opportunity, Verdict } from "@/lib/types";

/**
 * The deck. One posting at a time, decided with a single keystroke.
 *
 * Design constraint from the problem itself: the bottleneck was never judgement
 * quality, it was that reading thirty postings in a browser exhausts the person
 * before they apply to any. So the deck shows the model's read *first* — score,
 * gaps, recommended CV — and the full text second, for confirming rather than
 * discovering. Twenty postings should take ten minutes.
 */
export function TriageDeck() {
  const { data, mutate, isLoading } = useSWR<Opportunity[]>(
    "/opportunities?unlabeled=true&limit=50",
    fetcher,
  );
  const [i, setI] = useState(0);
  const [busy, setBusy] = useState(false);
  const current = data?.[i];

  const decide = useCallback(
    async (verdict: Verdict) => {
      if (!current || busy) return;
      setBusy(true);
      // Optimistic: the next card appears immediately. A person deciding at
      // speed should never wait on a round trip.
      setI((n) => n + 1);
      try {
        await api.post(`/opportunities/${current.id}/label`, { verdict });
        mutate();
      } finally {
        setBusy(false);
      }
    },
    [current, busy, mutate],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.target instanceof HTMLInputElement) return;
      const map: Record<string, Verdict> = { y: "yes", m: "maybe", n: "no" };
      if (map[e.key]) { e.preventDefault(); decide(map[e.key]); }
      if (e.key === "j") setI((n) => n + 1);
      if (e.key === "k") setI((n) => Math.max(0, n - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [decide]);

  if (isLoading) return <p className="hint">Loading the deck.</p>;

  if (!current) {
    return (
      <div className="empty">
        <h2>Nothing left to decide.</h2>
        <p>
          Everything scored has a verdict. Paste a posting to add one, or wait for
          tomorrow&apos;s pull. The next useful move is applying to what you marked yes.
        </p>
        <a href="/pipeline">Open applications</a>
      </div>
    );
  }

  const money =
    current.comp_usd_year_max
      ? `$${Math.round((current.comp_usd_year_min ?? 0) / 1000)}k–${Math.round(current.comp_usd_year_max / 1000)}k`
      : "not published";

  return (
    <div className="triage">
      <article className="posting">
        <h2>{current.title}</h2>
        <p className="where">
          {current.company ?? "unknown company"} — {current.remote} — {money}
          {current.url && <> — <a href={current.url} target="_blank" rel="noreferrer">open posting</a></>}
        </p>
        <div className="body">{current.rationale}</div>
      </article>

      <aside className="rail">
        <div className="fit">{current.fit != null ? Math.round(current.fit) : "—"}</div>
        <div className="bar"><i style={{ width: `${current.fit ?? 0}%` }} /></div>

        <dl style={{ marginTop: "1.25rem" }}>
          {Object.entries(current.dimensions ?? {}).map(([k, v]) => (
            <div key={k} style={{ display: "contents" }}>
              <dt>{k.replace("_", " ")}</dt>
              <dd>{v}</dd>
            </div>
          ))}
          <dt>send</dt>
          <dd>{current.recommended_cv === "lead" ? "Lead CV" : "IC CV"}</dd>
        </dl>

        {current.rule_flags.map((f) => (
          <p key={f} className="flag">{f}</p>
        ))}

        {(current.gaps ?? []).length > 0 && <h3>Gaps to prepare</h3>}
        {(current.gaps ?? []).map((g) => (
          <div className="gap-item" key={g.requirement}>
            <strong>{g.requirement}</strong>
            <p>{g.quote}</p>
          </div>
        ))}

        <div className="decide">
          <button data-v="yes" onClick={() => decide("yes")}>Yes</button>
          <button data-v="maybe" onClick={() => decide("maybe")}>Maybe</button>
          <button data-v="no" onClick={() => decide("no")}>No</button>
        </div>
        <p className="hint">
          <kbd>y</kbd> <kbd>m</kbd> <kbd>n</kbd> to decide, <kbd>j</kbd> <kbd>k</kbd> to move.
          {" "}{(data?.length ?? 0) - i} left.
        </p>
      </aside>
    </div>
  );
}
