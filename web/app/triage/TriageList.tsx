"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import useSWR, { mutate } from "swr";
import { Avatar } from "@/components/Avatar";
import { DimensionChips } from "@/components/DimensionChips";
import { IconCash, IconDoc, IconGlobe, IconLevel, IconPin, IconSearch, IconWarn } from "@/components/Icons";
import { LeakBar } from "@/components/LeakBar";
import { OpportunityDrawer } from "@/components/OpportunityDrawer";
import { PageHead } from "@/components/PageHead";
import { ScoreRing } from "@/components/ScoreRing";
import { VerdictButtons } from "@/components/VerdictButtons";
import { api, fetcher } from "@/lib/api";
import { KEY_DECIDE, refreshCounts } from "@/lib/counts";
import {
  cvLabel,
  geoLabel,
  money,
  remoteLabel,
  roleName,
  seniorityLabel,
  timeAgo,
} from "@/lib/scoring";
import type { Opportunity, Verdict } from "@/lib/types";

/**
 * Decide: la lista de lo que falta decidir.
 *
 * Antes era un mazo: un aviso por vez. Ahora es una lista que se recorre con el
 * scroll, pero conserva lo que hacía rápido al mazo:
 *
 *   y / m / n   deciden la fila resaltada y pasan a la siguiente
 *   j / k       bajan y suben
 *   Enter       abre el panel con el detalle (y adentro, y / m / n siguen valiendo)
 *
 * Restricción de diseño que viene del problema mismo: el cuello de botella
 * nunca fue el criterio, fue que leer treinta avisos agota antes de aplicar a
 * alguno. Por eso la fila muestra primero la lectura del modelo (puntaje y las
 * seis dimensiones) y el texto completo queda para confirmar, no para descubrir.
 */
const KEYS: Record<string, Verdict> = { y: "yes", m: "maybe", n: "no" };

/** Lo que dura la animación de salida de una fila (ver .opp-item en el CSS). */
const LEAVE_MS = 260;
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

type SortKey = "fit" | "new";

const haystack = (o: Opportunity) =>
  [o.company, o.title, o.seniority, o.geo_scope, ...o.tech_tags, ...o.domain_tags]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();

export function TriageList() {
  const { data, error, isLoading } = useSWR<Opportunity[]>(KEY_DECIDE, fetcher);

  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<SortKey>("fit");
  // La fila resaltada: es a la que le toca "y", "m" o "n". Si no se eligió
  // ninguna (o la elegida ya salió), es la primera.
  const [cursorId, setCursorId] = useState<string | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  // Filas que ya se decidieron y se están yendo (animación + espera de la API).
  const [leaving, setLeaving] = useState<Record<string, Verdict>>({});
  const [decidedCount, setDecidedCount] = useState(0);
  const [saveFailed, setSaveFailed] = useState(false);
  const [said, setSaid] = useState("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = (data ?? []).filter((o) => !q || haystack(o).includes(q));
    return list.sort(
      sort === "fit"
        ? (a, b) => (b.fit ?? 0) - (a.fit ?? 0)
        : (a, b) => b.captured_at.localeCompare(a.captured_at),
    );
  }, [data, query, sort]);

  // Las que todavía esperan decisión (las que se están yendo ya no cuentan).
  const live = useMemo(() => rows.filter((o) => !(o.id in leaving)), [rows, leaving]);
  const cursor = live.find((o) => o.id === cursorId) ?? live[0] ?? null;
  const cursorKey = cursor?.id;

  const decide = useCallback(
    async (o: Opportunity, verdict: Verdict) => {
      if (o.id in leaving) return;

      // Pasar a la que sigue en el mismo instante, como hacía el mazo: quien
      // decide a velocidad no espera un viaje de ida y vuelta a la API.
      const i = live.findIndex((r) => r.id === o.id);
      const next = live[i + 1] ?? live[i - 1] ?? null;
      setSaveFailed(false);
      setLeaving((m) => ({ ...m, [o.id]: verdict }));
      setCursorId(next?.id ?? null);
      if (!next) setDrawerOpen(false);
      setSaid(`Marked ${verdict}: ${o.company ?? o.title}`);

      const started = Date.now();
      try {
        await api.post(`/opportunities/${o.id}/label`, { verdict });
        // Que termine de irse la fila antes de sacarla de la lista.
        await wait(Math.max(0, LEAVE_MS - (Date.now() - started)));
        await mutate<Opportunity[]>(KEY_DECIDE, (cur) => cur?.filter((x) => x.id !== o.id), {
          revalidate: false,
        });
        setDecidedCount((n) => n + 1);
        refreshCounts();
      } catch {
        setSaveFailed(true);
      } finally {
        setLeaving((m) => {
          const rest = { ...m };
          delete rest[o.id];
          return rest;
        });
      }
    },
    [live, leaving],
  );

  // El teclado.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      const t = e.target as HTMLElement | null;
      if (t && (["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName) || t.isContentEditable)) return;
      if (!cursor) return;

      const i = live.findIndex((r) => r.id === cursor.id);
      if (KEYS[e.key]) {
        e.preventDefault();
        decide(cursor, KEYS[e.key]);
      } else if (e.key === "j") {
        setCursorId(live[Math.min(i + 1, live.length - 1)].id);
      } else if (e.key === "k") {
        setCursorId(live[Math.max(i - 1, 0)].id);
      } else if (e.key === "Enter" && t === document.body && !drawerOpen) {
        setDrawerOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [cursor, live, decide, drawerOpen]);

  // Que la fila resaltada siempre esté a la vista.
  useEffect(() => {
    if (cursorKey) document.getElementById(`opp-${cursorKey}`)?.scrollIntoView({ block: "nearest" });
  }, [cursorKey]);

  const open = (o: Opportunity) => {
    setCursorId(o.id);
    setDrawerOpen(true);
  };

  const total = decidedCount + live.length;
  const pct = total ? Math.round((decidedCount / total) * 100) : 0;

  return (
    <>
      <PageHead title="Decide" count={data ? live.length : undefined} countLabel="to decide">
        The quick pass. Read the score, decide in seconds; a maybe gets its close read in Apply.
      </PageHead>

      <LeakBar />

      {/* ---------------------------------------------------------- barra de filtros */}
      <div className="toolbar">
        <label className="search">
          <IconSearch size={18} />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search company, role or tag"
            aria-label="Search postings"
          />
        </label>

        <label className="select">
          <span>Sort</span>
          <select value={sort} onChange={(e) => setSort(e.target.value as SortKey)}>
            <option value="fit">Best fit first</option>
            <option value="new">Newest first</option>
          </select>
        </label>

        {/* El mazo mostraba "10 left": no dice si son 10 de 11 o 10 de 200. La barra
            muestra la proporción antes que el número. */}
        <div className="progress" title={`${decidedCount} decided in this session`}>
          <div className="pbar" aria-hidden="true">
            <i style={{ width: `${pct}%` }} />
          </div>
          <span>
            <b>{live.length}</b> left
          </span>
        </div>

        <p className="keys">
          <kbd>y</kbd> yes <kbd>m</kbd> maybe <kbd>n</kbd> no <kbd>j</kbd>
          <kbd>k</kbd> move <kbd>↵</kbd> open
        </p>
      </div>

      {saveFailed && (
        <div className="notice notice-error" role="alert">
          <IconWarn size={18} />
          <p>Could not save that decision. The posting is back in the list.</p>
          <button type="button" className="btn" onClick={() => setSaveFailed(false)}>
            Dismiss
          </button>
        </div>
      )}

      {/* ---------------------------------------------------------- la lista */}
      {isLoading && (
        <ul className="opp-list" aria-busy="true" aria-label="Loading postings">
          {[0, 1, 2, 3].map((i) => (
            <li key={i} className="opp-skel" />
          ))}
        </ul>
      )}

      {error && !data && (
        <div className="empty">
          <h2>The API is not answering.</h2>
          <p>
            Check that the containers are up: <code>docker compose ps</code> should show{" "}
            <code>db</code> and <code>api</code> running.
          </p>
        </div>
      )}

      {data && data.length === 0 && (
        <div className="empty">
          <h2>Nothing left to decide.</h2>
          <p>
            Everything scored has a verdict. Paste a posting to add one, or wait for tomorrow&apos;s
            pull. The next useful move is applying to what you marked yes.
          </p>
          <Link href="/apply" className="btn btn-primary">
            Open Apply
          </Link>
        </div>
      )}

      {data && data.length > 0 && rows.length === 0 && (
        <div className="empty">
          <h2>No posting matches “{query}”.</h2>
          <button type="button" className="btn" onClick={() => setQuery("")}>
            Clear the search
          </button>
        </div>
      )}

      {rows.length > 0 && (
        <ul className="opp-list">
          {rows.map((o) => (
            <Row
              key={o.id}
              o={o}
              isCursor={cursor?.id === o.id}
              verdict={leaving[o.id]}
              onOpen={open}
              onDecide={decide}
            />
          ))}
        </ul>
      )}

      <p className="sr-only" aria-live="polite">
        {said}
      </p>

      <OpportunityDrawer
        id={drawerOpen && cursor ? cursor.id : null}
        preview={cursor ?? undefined}
        onClose={() => setDrawerOpen(false)}
        actions={
          cursor ? (
            <VerdictButtons onDecide={(v) => decide(cursor, v)} disabled={cursor.id in leaving} />
          ) : undefined
        }
      />
    </>
  );
}

/* ====================================================================== fila */

function Row({
  o,
  isCursor,
  verdict,
  onOpen,
  onDecide,
}: {
  o: Opportunity;
  isCursor: boolean;
  verdict?: Verdict;
  onOpen: (o: Opportunity) => void;
  onDecide: (o: Opportunity, v: Verdict) => void;
}) {
  const geo = geoLabel(o.geo_scope);
  const level = seniorityLabel(o.seniority);
  const pay = money(o);

  return (
    <li className="opp-item" id={`opp-${o.id}`} data-leaving={verdict ? "true" : undefined}>
      <div className="opp-inner">
        {/* La fila entera abre el panel, menos lo que ya es un botón. No hay una capa
            encima del texto: así se puede seleccionar, y las etiquetas siguen
            mostrando su explicación al pasar el mouse. */}
        <article
          className="opp-row"
          data-cursor={isCursor || undefined}
          data-decided={verdict}
          onClick={(e) => {
            if ((e.target as HTMLElement).closest("button, a, select, input")) return;
            onOpen(o);
          }}
        >
          <div className="opp-lead">
            <Avatar name={o.company} />
            <ScoreRing value={o.fit} />
          </div>

          <div className="opp-main">
            <h3 className="opp-title">
              {/* Este botón es la puerta para teclado y lector de pantalla; con el
                  mouse alcanza con hacer clic en cualquier parte de la fila. */}
              <button type="button" className="opp-open" onClick={() => onOpen(o)}>
                <span className="opp-co">{o.company ?? "Unknown company"}</span>
                <span className="opp-sep" aria-hidden="true">
                  —
                </span>
                <span className="opp-role">{roleName(o.title, o.company)}</span>
              </button>
              <time className="opp-ago" dateTime={o.captured_at}>
                {timeAgo(o.captured_at)}
              </time>
            </h3>

            {/* Cada dato lleva su ícono en vez de un separador: si la línea salta de
                renglón en una pantalla angosta, no quedan puntos sueltos al principio. */}
            <ul className="opp-meta" aria-label="Posting facts">
              <li>
                <IconPin size={15} />
                {remoteLabel(o.remote)}
              </li>
              {level && (
                <li>
                  <IconLevel size={15} />
                  {level}
                </li>
              )}
              {geo && (
                <li>
                  <IconGlobe size={15} />
                  {geo}
                </li>
              )}
              <li data-gap={pay === "not published" || undefined}>
                <IconCash size={15} />
                {pay === "not published" ? "Pay not published" : pay}
              </li>
              <li>
                <IconDoc size={15} />
                Send {cvLabel(o.recommended_cv)}
              </li>
            </ul>

            <DimensionChips dimensions={o.dimensions} />

            {o.rule_flags.length > 0 && (
              <ul className="opp-flags">
                {o.rule_flags.map((f) => (
                  <li key={f}>
                    <IconWarn size={14} />
                    {f}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <VerdictButtons onDecide={(v) => onDecide(o, v)} disabled={!!verdict} />
        </article>
      </div>
    </li>
  );
}
