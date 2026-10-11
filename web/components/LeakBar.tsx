"use client";

import type { CSSProperties } from "react";
import useSWR from "swr";
import { fetcher } from "@/lib/api";
import { KEY_FUNNEL } from "@/lib/counts";
import { FUNNEL_MEANING } from "@/lib/scoring";
import type { Funnel } from "@/lib/types";

/**
 * Surfaced -> shortlisted -> kept -> applied -> answered, drawn to scale so the
 * drop is visible before a number is read. It sits on every screen because the
 * failure this whole system exists to fix is invisible otherwise: postings get
 * read, and then not applied to.
 *
 * Cada tramo explica que cuenta al pasar el mouse. Sin eso la barra es bonita y
 * muda: "shortlisted 7" no dice si 7 es de 21 o de 200, ni de donde sale.
 *
 * `size="lg"` es la versión de la pantalla Funnel: la misma barra, más grande y
 * con el porcentaje de cada tramo escrito (en las demás pantallas ese número
 * está en el tooltip).
 */
export function LeakBar({ size = "sm" }: { size?: "sm" | "lg" }) {
  const { data, error } = useSWR<Funnel[]>(KEY_FUNNEL, fetcher, { refreshInterval: 30_000 });
  const f = data?.[0];
  // Mientras llega la respuesta se reserva el lugar de la barra, así la página no
  // salta cuando aparece. Si la API falló no se deja un hueco vacío.
  if (!f) {
    return error ? null : <div className="leak leak-skel" data-size={size} aria-hidden="true" />;
  }

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
    <div
      className="leak"
      data-size={size}
      aria-label="Funnel from surfaced postings to answered applications"
    >
      {steps.map((s, i) => {
        const prev = i === 0 ? s.value : steps[i - 1].value;
        const bigDrop = prev > 0 && s.value / prev < 0.4;
        const share = i === 0 || prev === 0 ? null : Math.round((s.value / prev) * 100);
        return (
          <div
            key={s.label}
            className="leak-seg"
            data-drop={bigDrop}
            // flexGrow dibuja el tramo a escala en la fila; --w (en %) lo usa la
            // versión del celular, donde cada tramo es una fila con su relleno.
            style={{ flexGrow: Math.max(s.value / max, 0.12), "--w": Math.round((s.value / max) * 100) } as CSSProperties}
          >
            <span>
              <b>{s.value}</b>
              {s.label}
              {size === "lg" && (
                <small>{share === null ? "what reached you" : `${share}% of ${steps[i - 1].label}`}</small>
              )}
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
