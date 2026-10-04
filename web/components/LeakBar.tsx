"use client";

import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { FUNNEL_MEANING } from "@/lib/scoring";
import type { Funnel } from "@/lib/types";

/**
 * Surfaced -> shortlisted -> applied -> responded, drawn to scale so the drop
 * is visible before a number is read. It sits on every screen because the
 * failure this whole system exists to fix is invisible otherwise: postings get
 * read, and then not applied to.
 *
 * Cada tramo explica que cuenta al pasar el mouse. Sin eso la barra es bonita y
 * muda: "shortlisted 7" no dice si 7 es de 21 o de 200, ni de donde sale.
 */
export function LeakBar() {
  const { data } = useSWR<Funnel[]>("/analytics/funnel", fetcher, { refreshInterval: 30_000 });
  const f = data?.[0];
  if (!f) return null;

  // Los tres filtros, en orden, y despues el resultado. `kept` es el tramo que
  // hace visible el tercero: cuantas sobrevivieron a la lectura atenta.
  const steps = [
    { label: "surfaced", value: f.surfaced },
    { label: "shortlisted", value: f.shortlisted },
    { label: "kept", value: f.kept ?? f.shortlisted },
    { label: "applied", value: f.applied },
    { label: "answered", value: f.responded },
  ];
  const max = Math.max(1, f.surfaced);

  return (
    <div className="leak" aria-label="Funnel from surfaced postings to answered applications">
      {steps.map((s, i) => {
        const prev = i === 0 ? s.value : steps[i - 1].value;
        const bigDrop = prev > 0 && s.value / prev < 0.4;
        const share = i === 0 || prev === 0 ? null : Math.round((s.value / prev) * 100);
        return (
          <div
            key={s.label}
            className="leak-seg"
            data-drop={bigDrop}
            style={{ flexGrow: Math.max(s.value / max, 0.12) }}
          >
            <span>
              <b>{s.value}</b>
              {s.label}
            </span>
            <div className="tip" role="tooltip">
              <strong>{s.label}</strong>
              <p>{FUNNEL_MEANING[s.label]}</p>
              {share !== null && (
                <p className="tip-num">
                  {share}% of {steps[i - 1].label}
                  {bigDrop && " — the biggest drop in the funnel"}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
