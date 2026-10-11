/**
 * Íconos. Son SVG escritos a mano: cero dependencias, cero costo, y heredan el
 * color del texto (`currentColor`), así que cambian solos con el estado del botón.
 *
 * Todos miden 24×24 por dentro y se escalan con `size`.
 */
import type { ReactNode } from "react";

interface IconProps {
  size?: number;
  className?: string;
}

function Svg({ size = 20, className, children }: IconProps & { children: ReactNode }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      className={className}
    >
      {children}
    </svg>
  );
}

/* ---- navegación ---- */

export const IconDecide = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.5" y="4" width="17" height="16" rx="3.5" />
    <path d="M8.5 12.2l2.4 2.4 4.6-5" />
  </Svg>
);

export const IconApply = (p: IconProps) => (
  <Svg {...p}>
    <path d="M20.5 3.5L10.2 13.8" />
    <path d="M20.5 3.5l-6.3 17-3.9-7-7-3.9 17.2-6.1z" />
  </Svg>
);

export const IconBoard = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3.5" y="4" width="5" height="16" rx="1.6" />
    <rect x="10" y="4" width="4.5" height="10" rx="1.6" />
    <rect x="16" y="4" width="4.5" height="13" rx="1.6" />
  </Svg>
);

export const IconFunnel = (p: IconProps) => (
  <Svg {...p}>
    <path d="M3.5 5h17l-6.5 7.6V19l-4 1.8v-8.2L3.5 5z" />
  </Svg>
);

/* ---- acciones ---- */

export const IconClose = (p: IconProps) => (
  <Svg {...p}>
    <path d="M6.5 6.5l11 11M17.5 6.5l-11 11" />
  </Svg>
);

export const IconExternal = (p: IconProps) => (
  <Svg {...p}>
    <path d="M14 4h6v6" />
    <path d="M20 4l-9 9" />
    <path d="M18 14v4.5a1.5 1.5 0 01-1.5 1.5h-11A1.5 1.5 0 014 18.5v-11A1.5 1.5 0 015.5 6H10" />
  </Svg>
);

export const IconFullPage = (p: IconProps) => (
  <Svg {...p}>
    <path d="M9 4H5.5A1.5 1.5 0 004 5.5V9" />
    <path d="M15 4h3.5A1.5 1.5 0 0120 5.5V9" />
    <path d="M9 20H5.5A1.5 1.5 0 014 18.5V15" />
    <path d="M15 20h3.5a1.5 1.5 0 001.5-1.5V15" />
  </Svg>
);

export const IconKebab = (p: IconProps) => (
  <svg
    width={p.size ?? 20}
    height={p.size ?? 20}
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
    focusable="false"
    className={p.className}
  >
    <circle cx="12" cy="5.5" r="1.6" />
    <circle cx="12" cy="12" r="1.6" />
    <circle cx="12" cy="18.5" r="1.6" />
  </svg>
);

export const IconSearch = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="M20 20l-4.2-4.2" />
  </Svg>
);

export const IconInfo = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M12 11v5" />
    <path d="M12 7.9v.1" />
  </Svg>
);

export const IconChevron = (p: IconProps & { up?: boolean }) => (
  <Svg {...p}>
    <path d={p.up ? "M6 14.5l6-6 6 6" : "M6 9.5l6 6 6-6"} />
  </Svg>
);

export const IconWarn = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 4.2l8.4 14.6H3.6L12 4.2z" />
    <path d="M12 10v4" />
    <path d="M12 16.9v.1" />
  </Svg>
);

export const IconCheck = (p: IconProps) => (
  <Svg {...p}>
    <path d="M5 12.5l4.5 4.5L19 7.5" />
  </Svg>
);

/* ---- datos de un aviso (la línea de abajo del título) ---- */

export const IconPin = (p: IconProps) => (
  <Svg {...p}>
    <path d="M12 20.5s-6.2-5.3-6.2-10.4a6.2 6.2 0 0112.4 0c0 5.1-6.2 10.4-6.2 10.4z" />
    <circle cx="12" cy="10" r="2.3" />
  </Svg>
);

export const IconLevel = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="8" r="3.6" />
    <path d="M5 20c0-3.6 3.1-6 7-6s7 2.4 7 6" />
  </Svg>
);

export const IconGlobe = (p: IconProps) => (
  <Svg {...p}>
    <circle cx="12" cy="12" r="8.5" />
    <path d="M3.5 12h17" />
    <path d="M12 3.5c2.3 2.4 3.4 5.2 3.4 8.5s-1.1 6.1-3.4 8.5c-2.3-2.4-3.4-5.2-3.4-8.5S9.7 5.9 12 3.5z" />
  </Svg>
);

export const IconCash = (p: IconProps) => (
  <Svg {...p}>
    <rect x="3" y="6.5" width="18" height="11" rx="2.2" />
    <circle cx="12" cy="12" r="2.6" />
  </Svg>
);

export const IconDoc = (p: IconProps) => (
  <Svg {...p}>
    <path d="M7 3.5h7l4 4V19a1.5 1.5 0 01-1.5 1.5h-9A1.5 1.5 0 016 19V5A1.5 1.5 0 017 3.5z" />
    <path d="M14 3.5V8h4" />
    <path d="M9 12.5h6M9 16h4" />
  </Svg>
);

/* ---- marca ---- */

/** El embudo de la marca: lo mismo que dibuja la barra de arriba, en chiquito. */
export function BrandMark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 28 28" aria-hidden="true" focusable="false">
      <rect width="28" height="28" rx="8" fill="var(--act)" />
      <path d="M7 8.5h14l-5 6v5.2l-4 1.8v-7L7 8.5z" fill="#fff" />
    </svg>
  );
}
