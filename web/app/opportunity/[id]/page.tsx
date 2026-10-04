import Link from "next/link";
import { notFound } from "next/navigation";
import { api } from "@/lib/api";
import { contributions, cvReason, money } from "@/lib/scoring";
import type { Opportunity } from "@/lib/types";

/**
 * One opportunity, explained.
 *
 * The deck answers "should I look at this". This page answers the question that
 * comes after a yes: *why* did it score what it scored, what is missing, and
 * which CV goes out. Every number here is decomposed rather than asserted —
 * a fit of 50 that is 20 points of domain and 2 of craft is a different
 * proposition from the same 50 split evenly, and the difference changes what
 * you write in the application.
 */
export const dynamic = "force-dynamic";

export default async function OpportunityPage({
  params,
}: {
  // Next 15: params llega como promesa y hay que esperarla.
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let o: Opportunity;
  try {
    o = await api.get<Opportunity>(`/opportunities/${id}`);
  } catch {
    notFound();
  }

  const parts = contributions(o.dimensions);
  const total = parts.reduce((sum, p) => sum + p.points, 0);

  return (
    <main className="triage">
      <article className="posting">
        <h2>{o.title}</h2>
        <p className="where">
          {o.company ?? "unknown company"} — {o.remote ?? "remote unknown"} —{" "}
          {money(o)}
          {o.url && (
            <>
              {" — "}
              <a href={o.url} target="_blank" rel="noreferrer">
                open posting ↗
              </a>
            </>
          )}
        </p>

        {/* ---------------------------------------------- de dónde sale el puntaje */}
        <h3 className="section-head">Where the score comes from</h3>

        {parts.length === 0 ? (
          <p className="hint">This posting was never scored.</p>
        ) : (
          <>
            <table className="breakdown">
              <thead>
                <tr>
                  <th>dimension</th>
                  <th className="num">score</th>
                  <th>share</th>
                  <th className="num">points</th>
                </tr>
              </thead>
              <tbody>
                {parts.map((p) => (
                  <tr key={p.key}>
                    <td>
                      <strong>{p.label}</strong>
                      <p className="meaning">{p.meaning}</p>
                    </td>
                    <td className="num">{p.value}</td>
                    <td className="share">
                      <span className="bar">
                        <i style={{ width: `${p.value * 10}%` }} />
                      </span>
                      <em>{Math.round(p.weight * 100)}% of the total</em>
                    </td>
                    <td className="num strong">{p.points.toFixed(1)}</td>
                  </tr>
                ))}
                <tr className="sum">
                  <td colSpan={3}>fit</td>
                  <td className="num strong">{Math.round(total)}</td>
                </tr>
              </tbody>
            </table>

            {o.rationale && <p className="rationale">{o.rationale}</p>}

            <p className="caveat">
              This is the free scorer: it matches keywords, it does not read. A
              high domain score can come from one word in a company boilerplate
              paragraph, and a posting written in prose without tool names will
              score low on craft whatever it actually needs. Treat the breakdown
              as a reason to look, never as the verdict — that one is yours.
            </p>
          </>
        )}

        {/* ---------------------------------------------- qué falta */}
        {(o.gaps ?? []).length > 0 && (
          <>
            <h3 className="section-head">Gaps to prepare</h3>
            <p className="hint">
              Requirements you do not meet, each with the sentence that asked for
              it. These are the questions to have an answer ready for.
            </p>
            {(o.gaps ?? []).map((g, i) => (
              <div className="gap-item" key={`${g.requirement}-${i}`}>
                <strong>{g.requirement}</strong>
                {g.severity && <span className="sev">{g.severity}</span>}
                <p>{g.quote}</p>
              </div>
            ))}
          </>
        )}

        {/* ---------------------------------------------- el aviso */}
        {o.raw_text && (
          <>
            <h3 className="section-head">The posting</h3>
            <div className="body">{o.raw_text}</div>
          </>
        )}
      </article>

      <aside className="rail">
        <div className="fit">{o.fit != null ? Math.round(o.fit) : "—"}</div>
        <div className="bar">
          <i style={{ width: `${o.fit ?? 0}%` }} />
        </div>

        {o.verdict && (
          <p className={`badge v-${o.verdict}`}>
            {o.verdict}
            {o.applied && " · applied"}
          </p>
        )}

        <h3>Send</h3>
        <p className="cv">{o.recommended_cv === "lead" ? "Lead CV" : "IC CV"}</p>
        <p className="why">{cvReason(o)}</p>

        <dl>
          <dt>level</dt>
          <dd>{o.seniority ?? "unknown"}</dd>
          <dt>remote</dt>
          <dd>{o.remote ?? "unknown"}</dd>
          <dt>pay</dt>
          <dd>{money(o)}</dd>
          <dt>captured</dt>
          <dd>{o.captured_at.slice(0, 10)}</dd>
        </dl>

        {o.rule_flags.map((f) => (
          <p key={f} className="flag">
            {f}
          </p>
        ))}

        <p className="hint">
          <Link href="/apply">← back to the list</Link>
        </p>
      </aside>
    </main>
  );
}
