"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useState } from "react";
import { Avatar } from "@/components/Avatar";
import { IconExternal } from "@/components/Icons";
import { KanbanBoard, type KanbanColumn } from "@/components/KanbanBoard";
import { OpportunityDrawer } from "@/components/OpportunityDrawer";
import { ScoreRing } from "@/components/ScoreRing";
import { api } from "@/lib/api";
import { refreshCounts } from "@/lib/counts";
import { cvLabel, money, roleName } from "@/lib/scoring";
import type { Opportunity } from "@/lib/types";
import { useKanban } from "@/lib/useKanban";

/**
 * El tablero de /apply, con el tercer filtro adentro.
 *
 * El embudo tiene tres filtros, no dos:
 *   1. automatico  — reglas (staffing, presencial, US-only, familia de puesto)
 *   2. rapido      — Decide, un vistazo, y/m/n
 *   3. atento      — aca: se lee el aviso de verdad y recien ahi se decide
 *
 * El "si" del tercer filtro es "Applied" (registra la postulacion y la manda a
 * Applications). El "no" es "Dropped", que archiva sin borrar: siempre se puede
 * deshacer, porque un boton destructivo de un solo clic en una lista que se
 * recorre cansado es una forma segura de perder una vacante buena.
 *
 * La columna "Maybe" existe porque decidir "mas o menos" tiene que llevar a algun
 * lado. En Decide un maybe es "no me alcanzan cinco segundos para saber"; aca
 * se le dan los cinco minutos y se convierte en un si o en un no.
 */
type Col = "maybe" | "to_apply" | "applied" | "dropped";

const COLUMNS: KanbanColumn[] = [
  {
    id: "maybe",
    title: "Maybe",
    tone: "ochre",
    hint: "Five seconds was not enough in Decide. Open the posting and settle it: Yes moves it to To apply, Dropped files it away. A maybe you never come back to is a no you never admitted.",
  },
  {
    id: "to_apply",
    title: "To apply",
    tone: "act",
    hint: "Marked yes. Read the posting properly, then log it as applied or drop it. Open a card to see how its score was built.",
  },
  {
    id: "applied",
    title: "Applied",
    tone: "moss",
    hint: "Logged as sent. What happens next is tracked in Applications.",
  },
  {
    id: "dropped",
    title: "Dropped",
    tone: "brick",
    quiet: true,
    hint: "Passed the quick filter, did not survive a close read. Kept, not deleted: drag it back to undo.",
  },
];

const getId = (o: Opportunity) => o.id;

const getColumn = (o: Opportunity): Col => {
  if (o.status === "archived") return "dropped";
  if (o.applied) return "applied";
  return o.verdict === "maybe" ? "maybe" : "to_apply";
};

/** Las reglas de qué se puede mover adónde. null = se puede; un texto = por qué no. */
const canMove = (o: Opportunity, from: string, to: string): string | null => {
  if (from === "applied") return "Already logged as applied. Change its stage in Applications.";
  if (to === "applied") {
    return from === "dropped" ? "Undo the drop first, then log it as applied." : null;
  }
  if (to === "maybe") {
    if (from === "dropped" && o.verdict === "maybe") return null;
    return "A yes is a decision: it does not go back to maybe. Drop it if you changed your mind.";
  }
  // A to_apply o a dropped
  return null;
};

export function ApplyBoard({ rows }: { rows: Opportunity[] }) {
  const router = useRouter();
  const [openId, setOpenId] = useState<string | null>(null);

  const onMove = useCallback(
    async (o: Opportunity, from: string, to: string) => {
      try {
        if (to === "applied") {
          // Un maybe que se postula antes pasa a yes: es la misma decision del
          // mazo, tomada con mas informacion, asi que se escribe en el mismo lugar.
          if (from === "maybe") await api.post(`/opportunities/${o.id}/label`, { verdict: "yes" });
          await api.post("/applications", {
            opportunity_id: o.id,
            cv_variant: o.recommended_cv ?? "ic",
          });
        } else if (to === "dropped") {
          await api.post(`/opportunities/${o.id}/screen`, { decision: "drop" });
        } else if (to === "to_apply" && from === "maybe") {
          await api.post(`/opportunities/${o.id}/label`, { verdict: "yes" });
        } else if (from === "dropped") {
          // Deshacer. Un maybe descartado que vuelve a To apply se promueve a yes;
          // label() ademas lo saca del archivo (status = labeled).
          if (to === "to_apply" && o.verdict === "maybe") {
            await api.post(`/opportunities/${o.id}/label`, { verdict: "yes" });
          } else {
            await api.post(`/opportunities/${o.id}/screen`, { decision: "keep" });
          }
        }
      } finally {
        // Salga bien o mal, se pide la verdad de nuevo: si algo quedo a medias,
        // el tablero muestra lo que realmente paso.
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

  const openRow = rows.find((r) => r.id === openId);

  return (
    <>
      <KanbanBoard
        columns={COLUMNS}
        items={rows}
        getId={getId}
        getLabel={(o) => roleName(o.title, o.company)}
        columnOf={columnOf}
        canMove={canMove}
        move={move}
        busy={busy}
        notice={notice}
        onDismissNotice={dismiss}
        onOpen={(o) => setOpenId(o.id)}
        renderCard={(o, { column, busy: isBusy }) => (
          <Card o={o} column={column.id as Col} busy={isBusy} move={move} onOpen={() => setOpenId(o.id)} />
        )}
      />

      <OpportunityDrawer
        id={openRow ? openRow.id : null}
        preview={openRow}
        onClose={() => setOpenId(null)}
        actions={
          openRow ? (
            <Actions
              o={openRow}
              column={columnOf(openRow) as Col}
              busy={busy.includes(openRow.id)}
              move={move}
            />
          ) : undefined
        }
      />
    </>
  );
}

/* ===================================================================== tarjeta */

function Card({
  o,
  column,
  busy,
  move,
  onOpen,
}: {
  o: Opportunity;
  column: Col;
  busy: boolean;
  move: (o: Opportunity, to: string) => void;
  onOpen: () => void;
}) {
  const pay = money(o);
  return (
    <>
      <div className="k-top">
        <Avatar name={o.company} size="sm" />
        <div className="k-title">
          <button type="button" className="k-open" onClick={onOpen}>
            {roleName(o.title, o.company)}
          </button>
          <p className="k-co">
            <span>{o.company ?? "Unknown company"}</span>
            {o.url && (
              <a
                className="k-ext"
                href={o.url}
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

      {/* Las etiquetas a la izquierda y el puntaje a la derecha, como en la lista de Decide. */}
      <div className="k-mid">
        <ul className="k-chips">
          <li className="chip">{cvLabel(o.recommended_cv)}</li>
          <li className="chip" data-gap={pay === "not published" || undefined}>
            {pay === "not published" ? "Pay not published" : pay}
          </li>
        </ul>
        <ScoreRing value={o.fit} size={40} />
      </div>

      <footer className="k-foot">
        <span className="k-date">Captured {o.captured_at.slice(0, 10)}</span>
        <Actions o={o} column={column} busy={busy} move={move} compact />
      </footer>
    </>
  );
}

/**
 * Los botones que corresponden a la columna donde está la tarjeta. Los mismos
 * de la tabla de antes (Applied / Drop / Yes / Undo), ahora también como
 * alternativa a arrastrar: en el celular no se puede arrastrar.
 */
function Actions({
  o,
  column,
  busy,
  move,
  compact,
}: {
  o: Opportunity;
  column: Col;
  busy: boolean;
  move: (o: Opportunity, to: string) => void;
  compact?: boolean;
}) {
  const size = compact ? "btn btn-sm" : "btn";
  if (column === "maybe") {
    return (
      <span className="k-actions">
        <button type="button" className={`${size} btn-act`} disabled={busy} onClick={() => move(o, "to_apply")}>
          Yes
        </button>
        <button type="button" className={size} disabled={busy} onClick={() => move(o, "dropped")}>
          Drop
        </button>
      </span>
    );
  }
  if (column === "to_apply") {
    return (
      <span className="k-actions">
        <button type="button" className={`${size} btn-act`} disabled={busy} onClick={() => move(o, "applied")}>
          Applied
        </button>
        <button type="button" className={size} disabled={busy} onClick={() => move(o, "dropped")}>
          Drop
        </button>
      </span>
    );
  }
  if (column === "dropped") {
    return (
      <span className="k-actions">
        <button
          type="button"
          className={size}
          disabled={busy}
          onClick={() => move(o, o.verdict === "maybe" ? "maybe" : "to_apply")}
        >
          Undo
        </button>
      </span>
    );
  }
  // applied: ya no hay nada que decidir acá.
  return (
    <span className="k-actions">
      <Link href="/pipeline" className={`${size} btn-link`}>
        Track it
      </Link>
    </span>
  );
}
