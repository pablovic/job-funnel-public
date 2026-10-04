"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { contributions, money } from "@/lib/scoring";
import type { Opportunity } from "@/lib/types";

export type Mode = "pending" | "applied" | "dropped" | "maybe";

/**
 * La tabla de /apply, con el tercer filtro adentro.
 *
 * El embudo tiene tres filtros, no dos:
 *   1. automatico  — reglas (staffing, presencial, US-only, familia de puesto)
 *   2. rapido      — el deck, un vistazo, y/m/n
 *   3. atento      — aca: se lee el aviso de verdad y recien ahi se decide
 *
 * El "si" del tercer filtro es "Applied" (registra la postulacion y la manda a
 * Applications). El "no" es "Drop", que archiva sin borrar: siempre se puede
 * deshacer, porque un boton destructivo de un solo clic en una lista que se
 * recorre cansado es una forma segura de perder una vacante buena.
 *
 * El modo "maybe" existe porque decidir "mas o menos" tiene que llevar a algun
 * lado. En el deck un maybe es "no me alcanzan cinco segundos para saber"; aca
 * se le dan los cinco minutos y se convierte en un si o en un no.
 */
export function ApplyTable({ rows, mode }: { rows: Opportunity[]; mode: Mode }) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  // Capa optimista: la fila desaparece al instante y vuelve si el servidor falla.
  const [gone, setGone] = useState<string[]>([]);

  // Cuando llegan datos nuevos del servidor, la capa optimista ya no hace falta.
  // Sin esto, deshacer un drop no volveria a mostrar la fila en esta sesion.
  useEffect(() => {
    setGone((prev) => (prev.length ? [] : prev));
  }, [rows]);

  const act = async (o: Opportunity, what: "applied" | "drop" | "undo" | "yes") => {
    if (busy) return;
    setBusy(o.id);
    setGone((prev) => [...prev, o.id]);
    try {
      if (what === "applied") {
        await api.post("/applications", {
          opportunity_id: o.id,
          cv_variant: o.recommended_cv ?? "ic",
        });
      } else if (what === "yes") {
        // Promover un maybe: es la MISMA decision del deck, tomada con mas
        // informacion, asi que se escribe en el mismo lugar.
        await api.post(`/opportunities/${o.id}/label`, { verdict: "yes" });
      } else {
        await api.post(`/opportunities/${o.id}/screen`, {
          decision: what === "drop" ? "drop" : "keep",
        });
      }
      router.refresh();
    } catch {
      setGone((prev) => prev.filter((x) => x !== o.id));
    } finally {
      setBusy(null);
    }
  };

  const visible = rows.filter((r) => !gone.includes(r.id));
  if (!visible.length) return null;

  return (
    <table className={mode === "pending" || mode === "maybe" ? undefined : "muted-table"}>
      <thead>
        <tr>
          <th className="num">fit</th>
          <th>role</th>
          <th>company</th>
          <th>send</th>
          <th className="num">pay</th>
          <th>posting</th>
          <th className="act-col">{mode === "applied" ? "" : "decide"}</th>
        </tr>
      </thead>
      <tbody>
        {visible.map((r) => (
          <tr key={r.id}>
            <td className="num strong">{r.fit != null ? Math.round(r.fit) : "—"}</td>
            <td className="has-tip">
              {/* El título es el link al detalle: por qué ese puntaje y qué preparar. */}
              <Link href={`/opportunity/${r.id}`}>{r.title}</Link>
              <ScoreCard o={r} />
            </td>
            <td>{r.company ?? "—"}</td>
            <td>{r.recommended_cv === "lead" ? "Lead CV" : "IC CV"}</td>
            <td className="num">{money(r)}</td>
            <td>
              {r.url ? (
                <a href={r.url} target="_blank" rel="noreferrer">
                  open ↗
                </a>
              ) : (
                "—"
              )}
            </td>
            <td className="act-col">
              {mode === "pending" && (
                <span className="row-actions">
                  <button data-a="sent" disabled={busy === r.id} onClick={() => act(r, "applied")}>
                    Applied
                  </button>
                  <button data-a="drop" disabled={busy === r.id} onClick={() => act(r, "drop")}>
                    Drop
                  </button>
                </span>
              )}
              {mode === "maybe" && (
                <span className="row-actions">
                  <button data-a="sent" disabled={busy === r.id} onClick={() => act(r, "yes")}>
                    Yes
                  </button>
                  <button data-a="drop" disabled={busy === r.id} onClick={() => act(r, "drop")}>
                    Drop
                  </button>
                </span>
              )}
              {mode === "dropped" && (
                <span className="row-actions">
                  <button disabled={busy === r.id} onClick={() => act(r, "undo")}>
                    Undo
                  </button>
                </span>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/**
 * La tarjeta que aparece al pasar el mouse. Markup estatico y CSS puro
 * (`:hover` y `:focus-within`): no cuesta un solo listener.
 */
function ScoreCard({ o }: { o: Opportunity }) {
  const parts = contributions(o.dimensions);
  const words = [...o.domain_tags, ...o.tech_tags];

  return (
    <div className="tip tip-score" role="tooltip">
      <div className="tip-head">
        <b>{o.fit != null ? Math.round(o.fit) : "—"}</b>
        <span>out of 100 — how it adds up</span>
      </div>

      {parts.length === 0 ? (
        <p className="tip-num">Never scored.</p>
      ) : (
        <dl className="tip-dims">
          {parts.map((p) => (
            <div key={p.key}>
              <dt>
                {p.label} <em>{p.value}</em>
              </dt>
              <dd>{p.reading}</dd>
              <span className="tip-pts">+{p.points.toFixed(1)}</span>
            </div>
          ))}
        </dl>
      )}

      {words.length > 0 && (
        <>
          <p className="tip-label">Words it matched</p>
          <p className="chips">
            {words.map((w) => (
              <span key={w}>{w}</span>
            ))}
          </p>
        </>
      )}

      {(o.gaps ?? []).length > 0 && (
        <>
          <p className="tip-label">Gaps to prepare</p>
          <ul className="tip-gaps">
            {(o.gaps ?? []).map((g, i) => (
              <li key={`${g.requirement}-${i}`}>{g.requirement}</li>
            ))}
          </ul>
        </>
      )}

      {o.rule_flags.map((f) => (
        <p key={f} className="tip-flag">
          {f}
        </p>
      ))}
    </div>
  );
}
