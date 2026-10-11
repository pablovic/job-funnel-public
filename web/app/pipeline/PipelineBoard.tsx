"use client";

import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { Avatar } from "@/components/Avatar";
import { IconExternal } from "@/components/Icons";
import { KanbanBoard, type KanbanColumn, type Tone } from "@/components/KanbanBoard";
import { OpportunityDrawer } from "@/components/OpportunityDrawer";
import { ScoreRing } from "@/components/ScoreRing";
import { api } from "@/lib/api";
import { refreshCounts } from "@/lib/counts";
import { cvLabel, roleName } from "@/lib/scoring";
import type { ApplicationRow, Stage } from "@/lib/types";
import { useKanban } from "@/lib/useKanban";

/**
 * Las postulaciones enviadas, una columna por etapa.
 *
 * Mover una tarjeta a otra columna NO pisa la etapa anterior: agrega un evento.
 * La tabla `application_events` guarda la historia entera, y por eso "cuantos
 * dias tardaron en contestar" es una consulta y no arqueologia. El costo es que
 * una etapa mal elegida se corrige eligiendo la correcta, no borrando: el intento
 * equivocado queda registrado, que es lo honesto.
 */
const STAGES: { id: Stage; title: string; tone: Tone; quiet?: boolean; hint: string }[] = [
  { id: "applied", title: "Applied", tone: "ink", hint: "Sent. Nothing back yet." },
  { id: "ack", title: "Ack", tone: "act", hint: "They acknowledged it — usually an automatic email." },
  { id: "screening", title: "Screening", tone: "moss", hint: "A person wrote, or a first call is booked." },
  { id: "technical", title: "Technical", tone: "moss", hint: "A take-home, a challenge or a technical interview." },
  { id: "onsite", title: "Onsite", tone: "moss", hint: "Final round, panel, meeting the team." },
  { id: "offer", title: "Offer", tone: "moss", hint: "They made an offer." },
  { id: "rejected", title: "Rejected", tone: "brick", quiet: true, hint: "They said no." },
  { id: "withdrawn", title: "Withdrawn", tone: "brick", quiet: true, hint: "You pulled out." },
  { id: "ghosted", title: "Ghosted", tone: "muted", quiet: true, hint: "Silence long enough to call it dead." },
];

const COLUMNS: KanbanColumn[] = STAGES.map(({ id, title, tone, quiet, hint }) => ({
  id,
  title,
  tone,
  quiet,
  hint,
}));

const getId = (r: ApplicationRow) => r.application_id;
const getColumn = (r: ApplicationRow): string => r.current_stage ?? "applied";
// Acá cualquier etapa vale desde cualquier otra: un rechazo puede revertirse, una
// postulación puede saltar de "applied" a "technical" si se saltearon pasos.
const canMove = () => null;

export function PipelineBoard({
  rows,
  fits,
}: {
  rows: ApplicationRow[];
  /** opportunity_id -> puntaje, para dibujar el anillo (puede faltar). */
  fits: Record<string, number | null>;
}) {
  const router = useRouter();
  const [openId, setOpenId] = useState<string | null>(null);

  const onMove = useCallback(
    async (r: ApplicationRow, _from: string, to: string) => {
      try {
        // Sin occurred_at: el servidor usa ahora. Para una etapa que acaba de
        // pasar es lo correcto; una fecha vieja se carga por la API.
        await api.post(`/applications/${r.application_id}/events`, { stage: to });
      } finally {
        router.refresh();
        refreshCounts();
      }
    },
    [router],
  );

  const { columnOf, move, busy, notice, dismiss } = useKanban({
    items: rows,
    getId,
    getColumn,
    canMove,
    onMove,
  });

  const openRow = rows.find((r) => r.application_id === openId);

  return (
    <>
      <KanbanBoard
        dense
        columns={COLUMNS}
        items={rows}
        getId={getId}
        getLabel={(r) => roleName(r.title, r.company)}
        columnOf={columnOf}
        canMove={canMove}
        move={move}
        busy={busy}
        notice={notice}
        onDismissNotice={dismiss}
        onOpen={(r) => setOpenId(r.application_id)}
        renderCard={(r) => <Card r={r} fit={fits[r.opportunity_id] ?? null} onOpen={() => setOpenId(r.application_id)} />}
      />

      <OpportunityDrawer
        id={openRow ? openRow.opportunity_id : null}
        preview={
          openRow
            ? {
                id: openRow.opportunity_id,
                title: openRow.title,
                company: openRow.company,
                url: openRow.url,
              }
            : undefined
        }
        onClose={() => setOpenId(null)}
        actions={
          openRow ? (
            <label className="stage-select">
              <span>Stage</span>
              <select
                value={columnOf(openRow)}
                disabled={busy.includes(openRow.application_id)}
                title={STAGES.find((s) => s.id === columnOf(openRow))?.hint}
                onChange={(e) => move(openRow, e.target.value)}
              >
                {STAGES.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.title}
                  </option>
                ))}
              </select>
            </label>
          ) : undefined
        }
      />
    </>
  );
}

function Card({ r, fit, onOpen }: { r: ApplicationRow; fit: number | null; onOpen: () => void }) {
  return (
    <>
      <div className="k-top">
        <Avatar name={r.company} size="sm" />
        <div className="k-title">
          <button type="button" className="k-open" onClick={onOpen}>
            {roleName(r.title, r.company)}
          </button>
          <p className="k-co">
            <span>{r.company ?? "—"}</span>
            {r.url && (
              <a
                className="k-ext"
                href={r.url}
                target="_blank"
                rel="noreferrer"
                title="Open the posting"
                aria-label="Open the posting in a new tab"
              >
                <IconExternal size={14} />
              </a>
            )}
          </p>
        </div>
      </div>

      <div className="k-mid">
        <ul className="k-chips">
          <li className="chip">{cvLabel(r.cv_variant)}</li>
          {r.pay_usd_year ? <li className="chip">{`$${Math.round(r.pay_usd_year / 1000)}k`}</li> : null}
        </ul>
        {fit != null && <ScoreRing value={fit} size={40} />}
      </div>

      <footer className="k-foot k-foot-stack">
        <span className="k-date">Applied {r.applied_at.slice(0, 10)}</span>
        {r.first_response_at ? (
          <span className="k-date">
            Answered {r.first_response_at.slice(0, 10)}
            {r.days_to_response != null && ` · ${r.days_to_response} d`}
          </span>
        ) : (
          <span className="k-date k-silent">Silent</span>
        )}
      </footer>
    </>
  );
}
