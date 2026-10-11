import { fitTier } from "@/lib/scoring";

/**
 * El puntaje como anillo: el número adentro y el arco proporcional alrededor.
 * El color es el tramo (verde, ocre, gris) y lo define fitTier() en scoring.ts.
 *
 * Es solo SVG: no necesita JavaScript, así que sirve igual en lo que arma el
 * servidor que en lo que arma el navegador.
 */
export function ScoreRing({
  value,
  size = 44,
}: {
  value: number | null | undefined;
  size?: number;
}) {
  const tier = fitTier(value);
  const stroke = size >= 56 ? 4 : 3;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value)) / 100;
  const mid = size / 2;

  return (
    <span
      className="ring"
      data-tier={tier}
      style={{ width: size, height: size }}
      role="img"
      aria-label={value == null ? "Not scored" : `Fit ${Math.round(value)} out of 100`}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-hidden="true">
        <circle className="ring-track" cx={mid} cy={mid} r={r} strokeWidth={stroke} />
        {value != null && (
          <circle
            className="ring-arc"
            cx={mid}
            cy={mid}
            r={r}
            strokeWidth={stroke}
            strokeDasharray={`${c * pct} ${c}`}
            transform={`rotate(-90 ${mid} ${mid})`}
          />
        )}
      </svg>
      <b style={{ fontSize: Math.round(size * 0.32) }}>
        {value != null ? Math.round(value) : "—"}
      </b>
    </span>
  );
}
