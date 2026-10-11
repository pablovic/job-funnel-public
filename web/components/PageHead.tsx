import type { ReactNode } from "react";

/**
 * El encabezado de cada pantalla: el nombre (el mismo que en el menú de la
 * izquierda), un número chico al lado y una línea que dice para qué sirve.
 */
export function PageHead({
  title,
  count,
  countLabel,
  children,
}: {
  title: string;
  count?: number | string;
  countLabel?: string;
  children?: ReactNode;
}) {
  return (
    <header className="page-head">
      <h1>
        {title}
        {count !== undefined && (
          <span className="count-pill">
            {count}
            {countLabel && <small>{countLabel}</small>}
          </span>
        )}
      </h1>
      {children && <p className="page-sub">{children}</p>}
    </header>
  );
}
