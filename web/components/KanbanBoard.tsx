"use client";

import { useMemo, useState, type ReactNode } from "react";
import { IconInfo, IconKebab } from "@/components/Icons";
import type { Notice } from "@/lib/useKanban";

/**
 * El tablero (kanban): columnas con tarjetas que se arrastran de una a otra.
 *
 * Es genérico a propósito: /apply y /pipeline usan este mismo componente y solo
 * le cambian las columnas, las tarjetas y las reglas. Acá no hay nada que sepa
 * qué es una postulación.
 *
 * Arrastrar usa lo que ya trae el navegador (drag and drop de HTML5): cero
 * librerías. Tiene una limitación conocida: en pantallas táctiles no se puede
 * arrastrar. Por eso cada tarjeta tiene también un menú "Move to…" (los tres
 * puntitos), que además sirve para quien no usa mouse.
 */
export type Tone = "ink" | "act" | "moss" | "ochre" | "brick" | "muted";

export interface KanbanColumn {
  id: string;
  title: string;
  /** Qué significa estar en esta columna. Va en el (i) y en la columna vacía. */
  hint: string;
  tone: Tone;
  /** Las columnas de cierre se dibujan apagadas. */
  quiet?: boolean;
}

interface Props<T> {
  columns: KanbanColumn[];
  items: T[];
  getId: (t: T) => string;
  getLabel: (t: T) => string;
  columnOf: (t: T) => string;
  canMove: (t: T, from: string, to: string) => string | null;
  move: (t: T, to: string) => void;
  busy: string[];
  notice: Notice | null;
  onDismissNotice: () => void;
  /** El contenido de la tarjeta. El tablero le pone el borde, el arrastre y el menú. */
  renderCard: (t: T, ctx: { column: KanbanColumn; busy: boolean }) => ReactNode;
  /** Columnas angostas, para tableros con muchas (Applications tiene nueve). */
  dense?: boolean;
  /** Abre el detalle. Se dispara al hacer clic en cualquier parte de la tarjeta que no sea un botón. */
  onOpen?: (t: T) => void;
}

export function KanbanBoard<T>({
  columns,
  items,
  getId,
  getLabel,
  columnOf,
  canMove,
  move,
  busy,
  notice,
  onDismissNotice,
  renderCard,
  dense,
  onOpen,
}: Props<T>) {
  const [dragId, setDragId] = useState<string | null>(null);
  const [overCol, setOverCol] = useState<string | null>(null);

  const byId = useMemo(() => new Map(items.map((t) => [getId(t), t])), [items, getId]);
  const dragging = dragId ? byId.get(dragId) : undefined;

  const cards = useMemo(() => {
    const map: Record<string, T[]> = Object.fromEntries(columns.map((c) => [c.id, []]));
    for (const t of items) (map[columnOf(t)] ??= []).push(t);
    return map;
  }, [items, columns, columnOf]);

  /** Qué pasaría si se soltara la tarjeta que se está arrastrando acá. */
  const verdictFor = (col: KanbanColumn): "ok" | "no" | "same" | null => {
    if (!dragging) return null;
    const from = columnOf(dragging);
    if (from === col.id) return "same";
    return canMove(dragging, from, col.id) ? "no" : "ok";
  };

  return (
    <>
      <div className="board" data-dense={dense || undefined}>
        {columns.map((col, i) => {
          const list = cards[col.id] ?? [];
          const over = overCol === col.id ? verdictFor(col) : null;
          return (
            <section
              key={col.id}
              className="kb-col"
              data-tone={col.tone}
              data-quiet={col.quiet || undefined}
              data-over={over === "ok" || over === "no" ? over : undefined}
              aria-labelledby={`kb-${col.id}`}
            >
              <header className="kb-head">
                <span className="kb-dot" aria-hidden="true" />
                <h2 id={`kb-${col.id}`}>{col.title}</h2>
                <span className="kb-count">{list.length}</span>
                {/* El tooltip de la última columna abre hacia la izquierda para no salirse. */}
                <span className="has-tip kb-info" data-end={i >= columns.length - 2 || undefined}>
                  <button type="button" aria-label={`What “${col.title}” means`}>
                    <IconInfo size={16} />
                  </button>
                  <span className="tip" role="tooltip">
                    {col.hint}
                  </span>
                </span>
              </header>

              <div
                className="kb-body"
                onDragOver={(e) => {
                  if (!dragging) return;
                  // Se acepta soltar en cualquier columna: si no se puede, move()
                  // explica por qué, que enseña más que un cursor prohibido.
                  e.preventDefault();
                  e.dataTransfer.dropEffect = "move";
                  if (overCol !== col.id) setOverCol(col.id);
                }}
                onDragLeave={(e) => {
                  if (!e.currentTarget.contains(e.relatedTarget as Node | null)) {
                    setOverCol((c) => (c === col.id ? null : c));
                  }
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  const t = dragging ?? byId.get(e.dataTransfer.getData("text/plain"));
                  setDragId(null);
                  setOverCol(null);
                  if (t) move(t, col.id);
                }}
              >
                {list.length === 0 ? (
                  <p className="kb-empty">{col.hint}</p>
                ) : (
                  list.map((t) => {
                    const id = getId(t);
                    const isBusy = busy.includes(id);
                    const here = columnOf(t);
                    return (
                      <article
                        key={id}
                        className="k-card"
                        draggable
                        data-dragging={dragId === id || undefined}
                        data-busy={isBusy || undefined}
                        data-openable={onOpen ? true : undefined}
                        // Toda la tarjeta abre el detalle, menos lo que ya es un botón o
                        // un enlace (el título, el ícono de afuera, los botones, los tres
                        // puntitos). Así no hace falta ninguna capa encima que tape el texto.
                        onClick={
                          onOpen
                            ? (e) => {
                                if ((e.target as HTMLElement).closest("button, a, select, label")) return;
                                onOpen(t);
                              }
                            : undefined
                        }
                        onDragStart={(e) => {
                          e.dataTransfer.effectAllowed = "move";
                          e.dataTransfer.setData("text/plain", id);
                          setDragId(id);
                        }}
                        onDragEnd={() => {
                          setDragId(null);
                          setOverCol(null);
                        }}
                      >
                        {renderCard(t, { column: col, busy: isBusy })}

                        {/* Los tres puntitos: un <select> transparente encima del ícono.
                            Abre el selector nativo del sistema (que en el celular es el
                            más cómodo) y no hay un menú propio que se pueda cortar. */}
                        <label className="k-move" title="Move to…">
                          <IconKebab size={18} />
                          <select
                            aria-label={`Move “${getLabel(t)}” to…`}
                            value=""
                            disabled={isBusy}
                            onChange={(e) => {
                              const to = e.target.value;
                              if (to) move(t, to);
                            }}
                          >
                            <option value="" disabled>
                              Move to…
                            </option>
                            {columns.map((c) => (
                              <option key={c.id} value={c.id} disabled={c.id === here || !!canMove(t, here, c.id)}>
                                {c.title}
                                {c.id === here ? " (here)" : ""}
                              </option>
                            ))}
                          </select>
                        </label>
                      </article>
                    );
                  })
                )}
              </div>
            </section>
          );
        })}
      </div>

      {/* El aviso (por qué no se pudo mover, o que falló el guardado). */}
      <div className="toast-zone" role="status" aria-live="polite">
        {notice && (
          <p className="toast" data-kind={notice.kind}>
            <span>{notice.text}</span>
            <button type="button" onClick={onDismissNotice} aria-label="Dismiss">
              ×
            </button>
          </p>
        )}
      </div>
    </>
  );
}
