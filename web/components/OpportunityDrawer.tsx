"use client";

import Link from "next/link";
import { useEffect, useRef, type ReactNode } from "react";
import useSWR from "swr";
import { Avatar } from "@/components/Avatar";
import { IconClose, IconExternal, IconFullPage } from "@/components/Icons";
import { OpportunityDetail, type DetailInput } from "@/components/OpportunityDetail";
import { fetcher } from "@/lib/api";
import { roleName } from "@/lib/scoring";
import type { Opportunity } from "@/lib/types";

/**
 * El panel que se desliza desde la derecha al hacer clic en una oportunidad.
 *
 * - La cruz de arriba a la izquierda lo cierra. También Esc y un clic afuera.
 * - Es `position: fixed`: se dibuja sobre toda la ventana sin importar dónde esté
 *   en el HTML, así que no hace falta ningún "portal" ni librería extra.
 * - Dibuja al instante con lo que ya trajo la lista (`preview`) y pide el
 *   detalle completo por detrás: lo único que falta al principio es el texto
 *   del aviso, que la lista no manda a propósito (serían megabytes).
 * - `actions` son los botones que correspondan a la pantalla desde donde se
 *   abrió: Yes / Maybe / No en Decide, la etapa en Applications, etc.
 */
export function OpportunityDrawer({
  id,
  preview,
  onClose,
  actions,
}: {
  id: string | null;
  preview?: DetailInput;
  onClose: () => void;
  actions?: ReactNode;
}) {
  const open = id !== null;
  const panelRef = useRef<HTMLElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);

  const { data, error, isLoading, mutate } = useSWR<Opportunity>(
    id ? `/opportunities/${id}` : null,
    fetcher,
  );

  // Con lo que haya: el detalle completo si ya llegó, si no la vista previa.
  const o: DetailInput | undefined = data ?? (preview && preview.id === id ? preview : undefined);

  // Esc cierra.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  // Mientras está abierto, la página de atrás no se desplaza. Al cerrar, el foco
  // vuelve a donde estaba (la fila o tarjeta que se tocó).
  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    const root = document.documentElement;
    // Al bloquear el desplazamiento desaparece la barra de la derecha (en Windows
    // ocupa ~17 px) y la página de atrás se ensancharía de golpe. Se le devuelve ese
    // ancho como margen para que no se mueva nada.
    root.style.setProperty("--sbw", `${window.innerWidth - root.clientWidth}px`);
    root.classList.add("has-drawer");
    panelRef.current?.focus();
    return () => {
      root.classList.remove("has-drawer");
      root.style.removeProperty("--sbw");
      if (before && document.contains(before)) before.focus({ preventScroll: true });
    };
  }, [open]);

  // Al pasar de una oportunidad a otra, el panel arranca desde arriba.
  useEffect(() => {
    bodyRef.current?.scrollTo({ top: 0 });
  }, [id]);

  // Tab no se escapa del panel: da la vuelta adentro.
  const trapTab = (e: React.KeyboardEvent) => {
    if (e.key !== "Tab" || !panelRef.current) return;
    const focusable = Array.from(
      panelRef.current.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), select:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])',
      ),
    ).filter((el) => el.offsetParent !== null);
    if (!focusable.length) return;
    const first = focusable[0];
    const last = focusable[focusable.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  };

  if (!open) return null;

  const role = o ? roleName(o.title, o.company ?? null) : "Loading…";

  return (
    <div className="dr-root">
      <div className="dr-backdrop" onClick={onClose} aria-hidden="true" />

      <aside
        ref={panelRef}
        className="dr-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="dr-title"
        tabIndex={-1}
        onKeyDown={trapTab}
      >
        <header className="dr-head">
          {/* La cruz va arriba a la izquierda, como en Jobgether. */}
          <button type="button" className="icon-btn dr-close" onClick={onClose} aria-label="Close">
            <IconClose size={20} />
          </button>

          <Avatar name={o?.company ?? null} size="lg" />

          <div className="dr-title">
            <h2 id="dr-title">{role}</h2>
            <p>
              {o?.company ?? "Unknown company"}
              {o?.url && (
                <a href={o.url} target="_blank" rel="noreferrer" className="dr-ext">
                  Open posting <IconExternal size={14} />
                </a>
              )}
            </p>
          </div>

          <div className="dr-head-actions">
            {actions}
            {id && (
              <Link href={`/opportunity/${id}`} className="icon-btn" title="Open as a full page" aria-label="Open as a full page">
                <IconFullPage size={18} />
              </Link>
            )}
          </div>
        </header>

        <div className="dr-body" ref={bodyRef}>
          {o ? (
            <OpportunityDetail o={o} loading={isLoading} />
          ) : (
            <div className="dt-skeleton" aria-busy="true">
              <i /> <i /> <i />
            </div>
          )}

          {error && !data && (
            <div className="notice notice-error" role="alert">
              <p>Could not load the full posting.</p>
              <button type="button" className="btn" onClick={() => mutate()}>
                Try again
              </button>
            </div>
          )}
        </div>

        {/* En el celular los botones viven abajo, fijos, donde llega el pulgar. */}
        {actions && <footer className="dr-foot">{actions}</footer>}
      </aside>
    </div>
  );
}
