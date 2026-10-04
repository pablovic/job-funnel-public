"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import type { ApplicationRow, Stage } from "@/lib/types";

/**
 * Las postulaciones enviadas, con la etapa editable en la misma fila.
 *
 * Cambiar la etapa NO pisa la anterior: agrega un evento. La tabla
 * `application_events` guarda la historia entera, y por eso "cuantos dias
 * tardaron en contestar" es una consulta y no arqueologia. El costo es que una
 * etapa mal elegida se corrige eligiendo la correcta, no borrando: el intento
 * equivocado queda registrado, que es lo honesto.
 */
const STAGES: Stage[] = [
  "applied", "ack", "screening", "technical", "onsite",
  "offer", "rejected", "withdrawn", "ghosted",
];

// Que significa cada una, para no tener que acordarse.
const MEANING: Record<Stage, string> = {
  applied: "Sent. Nothing back yet.",
  ack: "They acknowledged it — usually an automatic email.",
  screening: "A person wrote, or a first call is booked.",
  technical: "A take-home, a challenge or a technical interview.",
  onsite: "Final round, panel, meeting the team.",
  offer: "They made an offer.",
  rejected: "They said no.",
  withdrawn: "You pulled out.",
  ghosted: "Silence long enough to call it dead.",
};

export function PipelineTable({ rows }: { rows: ApplicationRow[] }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [failed, setFailed] = useState<string | null>(null);

  const setStage = async (r: ApplicationRow, stage: Stage) => {
    if (busy || stage === r.current_stage) return;
    setBusy(r.application_id);
    setFailed(null);
    try {
      // Sin occurred_at: el servidor usa ahora. Para una etapa que acaba de
      // pasar es lo correcto; una fecha vieja se carga por la API.
      await api.post(`/applications/${r.application_id}/events`, { stage });
      router.refresh();
    } catch {
      setFailed(r.application_id);
    } finally {
      setBusy(null);
    }
  };

  return (
    <table>
      <thead>
        <tr>
          <th>applied</th>
          <th>role</th>
          <th>company</th>
          <th>stage</th>
          <th>cv</th>
          <th className="num">pay</th>
          <th>answered</th>
          <th className="num">days</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.application_id}>
            <td>{r.applied_at.slice(0, 10)}</td>
            <td>
              {/* El link al detalle: por que ese puntaje, gaps, el aviso. */}
              <Link href={`/opportunity/${r.opportunity_id}`}>{r.title}</Link>
              {r.url && (
                <>
                  {" "}
                  <a href={r.url} target="_blank" rel="noreferrer" className="ext">
                    ↗
                  </a>
                </>
              )}
            </td>
            <td>{r.company ?? "—"}</td>
            <td>
              <select
                className={`stage-pick s-${r.current_stage}`}
                value={r.current_stage ?? "applied"}
                disabled={busy === r.application_id}
                title={MEANING[(r.current_stage ?? "applied") as Stage]}
                onChange={(e) => setStage(r, e.target.value as Stage)}
              >
                {STAGES.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
              {failed === r.application_id && <span className="flag"> no se pudo guardar</span>}
            </td>
            <td>{r.cv_variant}</td>
            <td className="num">
              {r.pay_usd_year ? `$${Math.round(r.pay_usd_year / 1000)}k` : "—"}
            </td>
            <td>{r.first_response_at ? r.first_response_at.slice(0, 10) : "silent"}</td>
            <td className="num">
              {r.days_to_response != null ? r.days_to_response : "—"}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
