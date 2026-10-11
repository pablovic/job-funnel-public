"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ComponentType } from "react";
import { BrandMark, IconApply, IconBoard, IconDecide, IconFunnel } from "@/components/Icons";
import { useNavCounts, type NavCounts } from "@/lib/counts";

/**
 * El menú de la izquierda. En pantallas anchas es una columna fija; en el
 * celular el mismo menú pasa a ser una barra de pestañas abajo, donde llega el
 * pulgar (el CSS decide cuál de las dos; acá hay un solo menú).
 *
 * El orden es el del trabajo real: decidir, aplicar, seguir, medir.
 */
interface Item {
  href: string;
  label: string;
  icon: ComponentType<{ size?: number }>;
  count?: keyof NavCounts;
  /** Qué hace la pantalla, para el tooltip del navegador. */
  hint: string;
}

const GROUPS: { label: string; items: Item[] }[] = [
  {
    label: "Opportunities",
    items: [
      { href: "/triage", label: "Decide", icon: IconDecide, count: "decide", hint: "Quick pass: yes, maybe or no" },
      { href: "/apply", label: "Apply", icon: IconApply, count: "apply", hint: "Close read, then apply or drop" },
      { href: "/pipeline", label: "Applications", icon: IconBoard, count: "applications", hint: "What happened to each application" },
    ],
  },
  {
    label: "Measure",
    items: [
      { href: "/analytics", label: "Funnel", icon: IconFunnel, hint: "Where the week went" },
    ],
  },
];

/** Más de 99 se muestra como "99+": el número exacto ya no ayuda a decidir. */
const shown = (n: number) => (n > 99 ? "99+" : String(n));

export function Sidebar() {
  const pathname = usePathname();
  const counts = useNavCounts();

  return (
    <>
      {/* Solo se ve en el celular: la marca arriba, el menú abajo. */}
      <header className="topbar">
        <BrandMark size={24} />
        <span>Job Funnel</span>
      </header>

      <aside className="sidebar">
        <Link href="/triage" className="sb-brand">
          <BrandMark />
          <span>Job Funnel</span>
        </Link>

        <nav aria-label="Main" className="sb-nav">
          {GROUPS.map((g) => (
            <div className="sb-group" key={g.label}>
              <p className="sb-label">{g.label}</p>
              {g.items.map((it) => {
                const active = pathname === it.href || pathname.startsWith(`${it.href}/`);
                const n = it.count ? counts[it.count] : undefined;
                const Icon = it.icon;
                return (
                  <Link
                    key={it.href}
                    href={it.href}
                    className="sb-item"
                    aria-current={active ? "page" : undefined}
                    title={it.hint}
                  >
                    <Icon size={20} />
                    <span className="sb-text">{it.label}</span>
                    {n ? <span className="sb-count">{shown(n)}</span> : null}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </aside>
    </>
  );
}
