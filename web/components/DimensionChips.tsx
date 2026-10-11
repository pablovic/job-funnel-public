import { dimLabel, dimTier, explainValue, orderedDimensions } from "@/lib/scoring";

/**
 * Las seis etiquetas que el scorer evalúa, cada una con su valor:
 * craft · domain · level fit · comp · language · channel.
 *
 * El relleno de cada etiqueta crece de izquierda a derecha según el valor (0–10)
 * y el tinte dice si es fuerte (verde), normal (neutro) o flojo (ocre). Así se
 * ve de un vistazo qué dimensión sostiene el puntaje y cuál lo hunde, sin leer.
 * El número siempre está escrito: el color nunca va solo.
 *
 * Pasar el mouse por encima explica qué quiere decir ese valor (explainValue).
 */
export function DimensionChips({
  dimensions,
}: {
  dimensions: Record<string, number> | null | undefined;
}) {
  const dims = orderedDimensions(dimensions);
  if (!dims.length) {
    return <p className="chips-empty">Not scored.</p>;
  }
  return (
    <ul className="dims" aria-label="Score dimensions">
      {dims.map(([key, value]) => (
        <li
          key={key}
          className="dim"
          data-tier={dimTier(value)}
          style={{ "--v": `${Math.max(0, Math.min(10, value)) * 10}%` } as React.CSSProperties}
          title={explainValue(key, value) || undefined}
        >
          <span className="dim-name">{dimLabel(key)}</span>
          <b className="dim-val">{value}</b>
        </li>
      ))}
    </ul>
  );
}
