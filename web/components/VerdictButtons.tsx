"use client";

import type { Verdict } from "@/lib/types";

/**
 * Yes / Maybe / No. Los mismos tres botones del deck de antes, con las mismas
 * teclas (y, m, n), ahora en cada fila de la lista y en el panel lateral.
 *
 * El color sigue la regla de siempre: índigo = "podés actuar sobre esto",
 * ocre = "falta mirar más", gris = "se descarta".
 */
const OPTIONS: { v: Verdict; label: string; key: string }[] = [
  { v: "yes", label: "Yes", key: "y" },
  { v: "maybe", label: "Maybe", key: "m" },
  { v: "no", label: "No", key: "n" },
];

export function VerdictButtons({
  onDecide,
  disabled,
}: {
  onDecide: (v: Verdict) => void;
  disabled?: boolean;
}) {
  return (
    <div className="verdicts" role="group" aria-label="Decide">
      {OPTIONS.map((o) => (
        <button
          key={o.v}
          type="button"
          className="verdict"
          data-v={o.v}
          disabled={disabled}
          title={`${o.label} (${o.key})`}
          onClick={() => onDecide(o.v)}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
