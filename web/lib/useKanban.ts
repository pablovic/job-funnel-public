import { useCallback, useEffect, useState } from "react";

export interface Notice {
  kind: "info" | "error";
  text: string;
}

/**
 * La lógica de mover tarjetas entre columnas, sin nada de dibujo.
 *
 * Mover es OPTIMISTA: la tarjeta cambia de columna al instante y recién después
 * se le avisa a la API. Si la API falla, la tarjeta vuelve y aparece un aviso.
 * Si sale bien, el que llamó pide los datos de nuevo (router.refresh) y esa
 * respuesta pasa a ser la verdad.
 *
 * Vive aparte del tablero porque la misma acción se dispara desde tres lados:
 * arrastrando, desde el menú "Move to…" de la tarjeta, y desde los botones del
 * panel lateral. Los tres tienen que pasar por las mismas reglas.
 */
export function useKanban<T>({
  items,
  getId,
  getColumn,
  canMove,
  onMove,
}: {
  items: T[];
  getId: (t: T) => string;
  /** En qué columna dice el servidor que está. */
  getColumn: (t: T) => string;
  /** null = se puede. Un texto = por qué no (se le muestra a la persona). */
  canMove: (t: T, from: string, to: string) => string | null;
  /** Hace el trabajo de verdad. Si tira un error, el movimiento se deshace. */
  onMove: (t: T, from: string, to: string) => Promise<void>;
}) {
  const [overrides, setOverrides] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string[]>([]);
  const [notice, setNotice] = useState<Notice | null>(null);

  // Llegaron datos nuevos del servidor: las posiciones provisorias ya no hacen falta.
  useEffect(() => {
    setOverrides({});
  }, [items]);

  // El aviso se apaga solo.
  useEffect(() => {
    if (!notice) return;
    const t = setTimeout(() => setNotice(null), 6000);
    return () => clearTimeout(t);
  }, [notice]);

  const columnOf = useCallback((t: T) => overrides[getId(t)] ?? getColumn(t), [overrides, getId, getColumn]);

  const move = useCallback(
    async (t: T, to: string) => {
      const id = getId(t);
      const from = overrides[id] ?? getColumn(t);
      if (from === to || busy.includes(id)) return;

      const why = canMove(t, from, to);
      if (why) {
        setNotice({ kind: "info", text: why });
        return;
      }

      setNotice(null);
      setBusy((b) => [...b, id]);
      setOverrides((o) => ({ ...o, [id]: to }));
      try {
        await onMove(t, from, to);
      } catch {
        setOverrides((o) => {
          const rest = { ...o };
          delete rest[id];
          return rest;
        });
        setNotice({ kind: "error", text: "Could not save that move. Nothing changed." });
      } finally {
        setBusy((b) => b.filter((x) => x !== id));
      }
    },
    [overrides, busy, getId, getColumn, canMove, onMove],
  );

  return { columnOf, move, busy, notice, dismiss: () => setNotice(null) };
}
