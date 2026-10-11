"use client";

import { useState } from "react";
import { IconChevron, IconWarn } from "@/components/Icons";
import { ScoreRing } from "@/components/ScoreRing";
import {
  contributions,
  cvLabel,
  cvReason,
  dimTier,
  geoLabel,
  money,
  remoteLabel,
  seniorityLabel,
} from "@/lib/scoring";
import type { Opportunity } from "@/lib/types";

/**
 * Lo mínimo para dibujar algo: id y título. Todo lo demás puede faltar mientras
 * llega el detalle completo (la lista trae casi todo; las tarjetas de
 * Applications traen casi nada).
 */
export type DetailInput = Pick<Opportunity, "id" | "title"> & Partial<Opportunity>;

/**
 * Una oportunidad, explicada. Es el contenido del panel lateral y también el de
 * la página completa /opportunity/[id].
 *
 * El orden sigue la idea original del deck: primero lo que leyó el modelo
 * (puntaje, qué falta, qué CV mandar), y al final el texto completo, para
 * confirmar y no para descubrir.
 */
export function OpportunityDetail({
  o,
  loading = false,
}: {
  o: DetailInput;
  /** El detalle completo todavía está viajando (falta el texto del aviso). */
  loading?: boolean;
}) {
  // La API siempre manda `dimensions` (aunque sea null). Si la clave ni existe,
  // es porque solo tenemos la vista previa y el resto está en camino.
  const known = "dimensions" in o;
  const parts = contributions(o.dimensions ?? null);
  const total = parts.reduce((sum, p) => sum + p.points, 0);
  const words = [...(o.domain_tags ?? []), ...(o.tech_tags ?? [])];
  const gaps = o.gaps ?? [];
  const flags = o.rule_flags ?? [];
  const pay = money({
    comp_usd_year_min: o.comp_usd_year_min ?? null,
    comp_usd_year_max: o.comp_usd_year_max ?? null,
  });

  return (
    <div className="dt">
      {/* ------------------------------------------------------------ datos */}
      {known && (
        <ul className="dt-facts" aria-label="Posting facts">
          {o.verdict && (
            <li className="fact fact-status" data-v={o.verdict}>
              {o.verdict}
              {o.applied && " · applied"}
              {o.status === "archived" && " · dropped"}
            </li>
          )}
          <li className="fact">{remoteLabel(o.remote)}</li>
          {seniorityLabel(o.seniority) && <li className="fact">{seniorityLabel(o.seniority)}</li>}
          <li className="fact" data-gap={pay === "not published" || undefined}>
            {pay === "not published" ? "Pay not published" : pay}
          </li>
          {geoLabel(o.geo_scope) && <li className="fact">{geoLabel(o.geo_scope)}</li>}
          {o.captured_at && <li className="fact">Captured {o.captured_at.slice(0, 10)}</li>}
        </ul>
      )}

      {/* ------------------------------------------- lo que leyó el modelo */}
      {!known ? (
        <div className="dt-skeleton" aria-busy="true">
          <i /> <i /> <i />
        </div>
      ) : (
        <div className="dt-grid">
          <section className="dt-card" aria-labelledby="dt-score-h">
            <header className="dt-score-head">
              <ScoreRing value={o.fit} size={64} />
              <div>
                <h3 id="dt-score-h">Where the score comes from</h3>
                <p>
                  {parts.length
                    ? "What the scorer read in each dimension, how much it weighs, and the points it added."
                    : "This posting was never scored."}
                </p>
              </div>
            </header>

            {parts.length > 0 && (
              <>
                <ol className="dt-dims">
                  {parts.map((p) => (
                    <li key={p.key} className="dt-dim" data-tier={dimTier(p.value)}>
                      <div className="dt-dim-top">
                        <strong>{p.label}</strong>
                        <span className="dt-dim-val">
                          {p.value}
                          <small>/10</small>
                        </span>
                        <span className="dt-dim-pts">+{p.points.toFixed(1)}</span>
                      </div>
                      <div className="meter" aria-hidden="true">
                        <i style={{ width: `${p.value * 10}%` }} />
                      </div>
                      <p className="dt-dim-read">{p.reading}</p>
                      <p className="dt-dim-meaning">
                        {p.meaning} {Math.round(p.weight * 100)}% of the total.
                      </p>
                    </li>
                  ))}
                </ol>
                <p className="dt-total">
                  <span>fit</span>
                  <b>{Math.round(total)}</b>
                </p>
              </>
            )}
          </section>

          <div className="dt-side">
            <section className="dt-card" aria-labelledby="dt-send-h">
              <h3 id="dt-send-h">Send</h3>
              <p className="dt-cv">{cvLabel(o.recommended_cv)}</p>
              <p className="dt-why">
                {cvReason({ recommended_cv: o.recommended_cv ?? null, seniority: o.seniority ?? null })}
              </p>
            </section>

            {gaps.length > 0 && (
              <section className="dt-card" aria-labelledby="dt-gaps-h">
                <h3 id="dt-gaps-h">Gaps to prepare</h3>
                <p className="dt-hint">
                  Requirements you do not meet, each with the sentence that asked for it. These
                  are the questions to have an answer ready for.
                </p>
                <ul className="dt-gaps">
                  {gaps.map((g, i) => (
                    <li className="gap-item" key={`${g.requirement}-${i}`}>
                      <strong>{g.requirement}</strong>
                      {g.severity && <span className="sev">{g.severity}</span>}
                      <p>{g.quote}</p>
                    </li>
                  ))}
                </ul>
              </section>
            )}

            {flags.length > 0 && (
              <ul className="dt-flags">
                {flags.map((f) => (
                  <li key={f}>
                    <IconWarn size={16} />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      )}

      {known && o.rationale && <p className="dt-rationale">{o.rationale}</p>}

      {known && parts.length > 0 && (
        <p className="dt-caveat">
          This is the free scorer: it matches keywords, it does not read. A high domain score can
          come from one word in a company boilerplate paragraph, and a posting written in prose
          without tool names will score low on craft whatever it actually needs. Treat the
          breakdown as a reason to look, never as the verdict — that one is yours.
        </p>
      )}

      {words.length > 0 && (
        <section className="dt-section" aria-labelledby="dt-words-h">
          <h3 id="dt-words-h">Words it matched</h3>
          <ul className="dt-words">
            {words.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </section>
      )}

      <PostingText key={o.id} text={o.raw_text} loading={loading} />
    </div>
  );
}

/** El texto del aviso. Largo por naturaleza: se muestra recortado y se abre a pedido. */
function PostingText({ text, loading }: { text?: string | null; loading: boolean }) {
  const [open, setOpen] = useState(false);

  if (!text) {
    return loading ? (
      <section className="dt-section" aria-busy="true">
        <h3>The posting</h3>
        <div className="dt-skeleton dt-skeleton-text">
          <i /> <i /> <i /> <i />
        </div>
      </section>
    ) : null;
  }

  const long = text.length > 1500 || text.split("\n").length > 20;
  return (
    <section className="dt-section" aria-labelledby="dt-posting-h">
      <h3 id="dt-posting-h">The posting</h3>
      <div className="dt-body" data-collapsed={long && !open ? "true" : undefined}>
        {text}
      </div>
      {long && (
        <button
          type="button"
          className="link-btn"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? "Show less" : "Show the full posting"}
          <IconChevron size={16} up={open} />
        </button>
      )}
    </section>
  );
}
