import type { ReactNode } from "react";
import { LeakBar } from "@/components/LeakBar";
import { PageHead } from "@/components/PageHead";
import { api } from "@/lib/api";
import { roleName } from "@/lib/scoring";
import type { Funnel } from "@/lib/types";

/**
 * Funnel: la pantalla donde se mide.
 *
 * Muestra exactamente las mismas cinco tablas de antes, con todos sus valores y
 * sus nombres de columna, y encima de ellas la barra del embudo en grande y
 * cuatro números que ya calculaba la vista v_funnel pero ninguna pantalla mostraba
 * (la tasa de postulación, la de respuesta, cuántas siguen en proceso, ofertas).
 *
 * Cada vista se dibuja con lo que la hace legible (una barra al lado del número,
 * un medidor), pero el número sigue escrito: ningún dato vive solo en un dibujo.
 * Y si una vista llega con columnas que esta pantalla no conoce, igual se
 * muestran: la tabla se arma con las claves que mande la API.
 */
export const dynamic = "force-dynamic";

type Row = Record<string, string | number | boolean | null>;

/** null = la API no contestó; [] = contestó y no hay filas. */
async function view(name: string): Promise<Row[] | null> {
  try {
    const rows = await api.get<Row[]>(`/analytics/${name}`);
    return Array.isArray(rows) ? rows : null;
  } catch {
    return null;
  }
}

const label = (key: string) => key.replace(/_/g, " ");

/** Un valor tal cual lo manda la API, listo para mostrar. */
function fmt(v: Row[string]): ReactNode {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(v)) {
    // "2026-09-22T07:51:22.706608+00:00" -> la fecha, y la hora chica al lado.
    return (
      <>
        {v.slice(0, 10)} <small className="muted">{v.slice(11, 16)} UTC</small>
      </>
    );
  }
  return String(v);
}

const num = (v: Row[string] | undefined) => (typeof v === "number" ? v : Number(v ?? 0));
/** "ic" → "IC", "lead" → "Lead": el valor es el mismo, solo se escribe como se lee. */
const variantName = (v: Row[string]) => {
  const s = String(v ?? "");
  return s.toLowerCase() === "ic" ? "IC" : s.charAt(0).toUpperCase() + s.slice(1);
};
const pct = (v: number | null | undefined) => (v == null ? "—" : `${v}%`);

export default async function AnalyticsPage() {
  const [funnelRows, effort, variantRows, power, bias, followups] = await Promise.all([
    view("funnel"),
    view("effort"),
    view("variants"),
    view("power"),
    view("bias"),
    view("followups"),
  ]);
  // La vista v_response_by_variant agrupa sin ORDER BY: el orden de las filas no está
  // garantizado y las dos variantes podían intercambiarse entre una recarga y otra.
  // Se ordenan por nombre para que cada una tenga siempre el mismo lugar.
  const variants =
    variantRows && [...variantRows].sort((a, b) => String(a.cv_variant).localeCompare(String(b.cv_variant)));

  if ([funnelRows, effort, variants, power, bias, followups].every((r) => r === null)) {
    return (
      <main className="page">
        <PageHead title="Funnel" />
        <div className="empty">
          <h2>The API is not answering.</h2>
          <p>
            Check that the containers are up: <code>docker compose ps</code> should show{" "}
            <code>db</code> and <code>api</code> running.
          </p>
        </div>
      </main>
    );
  }

  const f = (funnelRows?.[0] ?? null) as unknown as Funnel | null;

  return (
    <main className="page">
      <PageHead title="Funnel">
        Where the postings went: what reached you, what you decided, what you sent and what came
        back.
      </PageHead>

      <LeakBar size="lg" />

      {f && (
        <section className="an-kpis" aria-label="Funnel rates">
          <Kpi
            label="Apply rate"
            value={pct(f.apply_rate_pct)}
            note={`${f.applied} applied of ${f.shortlisted} shortlisted`}
          />
          <Kpi
            label="Response rate"
            value={pct(f.response_rate_pct)}
            note={`${f.responded} answered of ${f.applied} applied`}
          />
          <Kpi label="In process" value={String(f.in_process)} note="screening, technical, onsite or offer" />
          <Kpi label="Offers" value={String(f.offers)} note="made an offer" />
        </section>
      )}

      <div className="an-grid">
        {/* ------------------------------------------------------------ la semana */}
        <Card
          className="an-12"
          title="Where the week went"
          note="Ingested, auto-filtered, reviewed, applied. The gap between reviewed and applied is the one that matters."
          legend={
            <span className="an-legend" aria-hidden="true">
              <i data-k="rev" /> reviewed <i data-k="app" /> applied
            </span>
          }
        >
          <Table
            rows={effort}
            extra={{
              head: "reviewed vs applied",
              cell: (r, rows) => {
                const max = Math.max(1, ...rows.map((x) => Math.max(num(x.reviewed), num(x.applied))));
                return (
                  <span
                    className="duo"
                    title={`${r.week}: reviewed ${num(r.reviewed)}, applied ${num(r.applied)}`}
                  >
                    <i data-k="rev" style={{ width: `${(num(r.reviewed) / max) * 100}%` }} />
                    <i data-k="app" style={{ width: `${(num(r.applied) / max) * 100}%` }} />
                  </span>
                );
              },
            }}
          />
        </Card>

        {/* ------------------------------------------------------- variantes de CV */}
        <Card className="an-7" title="Response by CV variant">
          {variants === null || variants.length === 0 ? (
            <Empty />
          ) : (
            <div className="an-tiles">
              {variants.map((r) => {
                const rate = num(r.response_rate_pct);
                const rest = Object.entries(r).filter(
                  ([k]) => !["cv_variant", "response_rate_pct"].includes(k),
                );
                return (
                  <article className="an-tile" key={String(r.cv_variant)}>
                    <h3>
                      {variantName(r.cv_variant)}
                      <small>cv variant</small>
                    </h3>
                    <p className="an-big">
                      {rate}
                      <small>%</small>
                    </p>
                    <p className="an-cap">{label("response_rate_pct")}</p>
                    <div className="meter meter-lg" aria-hidden="true">
                      <i style={{ width: `${Math.min(100, rate)}%` }} />
                    </div>
                    <dl className="an-dl">
                      {rest.map(([k, v]) => (
                        <div key={k}>
                          <dt>{label(k)}</dt>
                          <dd>{fmt(v)}</dd>
                        </div>
                      ))}
                    </dl>
                  </article>
                );
              })}
            </div>
          )}
        </Card>

        {/* ----------------------------------------------------------- poder */}
        <Card
          className="an-5"
          title="Can this comparison decide anything?"
          note="Below roughly a thousand applications per arm, the variant table is descriptive. Read it, do not rewrite the CV on it."
        >
          {power === null || power.length === 0 ? (
            <Empty />
          ) : (
            <PowerBody row={power[0]} arms={Math.max(2, variants?.length ?? 2)} />
          )}
        </Card>

        {/* ------------------------------------------------------------ sesgo */}
        <Card
          className="an-5"
          title="Rejection rate by whether pay was published"
          note="If the rejection rate is far higher for unpublished ranges, the filter is firing on disclosure policy rather than fit."
        >
          <Table
            rows={bias}
            render={{
              comp_published: (r) => (
                <>
                  <span className="pill">{String(r.comp_published)}</span>{" "}
                  <small className="muted">{r.comp_published === true ? "published" : "not published"}</small>
                </>
              ),
              reject_rate_pct: (r) => (
                <span className="rate">
                  <span className="rate-bar" aria-hidden="true">
                    <i style={{ width: `${Math.min(100, num(r.reject_rate_pct))}%` }} />
                  </span>
                  {fmt(r.reject_rate_pct)}
                </span>
              ),
            }}
          />
        </Card>

        {/* -------------------------------------------------------- seguimiento */}
        <Card className="an-7" title="Silent for more than a week">
          {followups === null ? (
            <Empty />
          ) : followups.length === 0 ? (
            <p className="an-ok">Nothing has been silent for more than a week.</p>
          ) : (
            <ul className="an-follow">
              {followups.map((r) => (
                <li key={String(r.application_id)}>
                  <p className="an-days">
                    <b>{fmt(r.days_since)}</b>
                    <span>{label("days_since")}</span>
                  </p>
                  <div className="an-follow-main">
                    <strong>{roleName(String(r.title ?? ""), r.company == null ? null : String(r.company))}</strong>
                    <span>{fmt(r.company)}</span>
                    <span className="muted">
                      {label("applied_at")} {fmt(r.applied_at)}
                    </span>
                    <code>{String(r.application_id)}</code>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </main>
  );
}

/* ================================================================= piezas */

function Card({
  title,
  note,
  legend,
  className = "",
  children,
}: {
  title: string;
  note?: string;
  legend?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`an-card ${className}`}>
      <header>
        <div>
          <h2>{title}</h2>
          {note && <p>{note}</p>}
        </div>
        {legend}
      </header>
      {children}
    </section>
  );
}

function Kpi({ label: name, value, note }: { label: string; value: string; note: string }) {
  return (
    <article className="an-kpi">
      <p className="an-kpi-label">{name}</p>
      <p className="an-kpi-value">{value}</p>
      <p className="an-kpi-note">{note}</p>
    </article>
  );
}

function Empty() {
  return <p className="an-ok">No data yet.</p>;
}

/**
 * Una tabla armada con las columnas que mande la API (no hay una lista fija: si
 * la vista gana una columna, aparece sola). `render` cambia cómo se dibuja una
 * celda sin quitarle el valor; `extra` agrega una columna al final.
 */
function Table({
  rows,
  render = {},
  extra,
}: {
  rows: Row[] | null;
  render?: Record<string, (r: Row) => ReactNode>;
  extra?: { head: string; cell: (r: Row, rows: Row[]) => ReactNode };
}) {
  if (rows === null || rows.length === 0) return <Empty />;
  const cols = Object.keys(rows[0]);
  return (
    <div className="an-table-wrap">
      <table className="an-table">
        <thead>
          <tr>
            {cols.map((c) => (
              <th key={c} className={typeof rows[0][c] === "number" ? "num" : undefined}>
                {label(c)}
              </th>
            ))}
            {extra && <th>{extra.head}</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c} className={typeof r[c] === "number" ? "num" : undefined}>
                  {render[c] ? render[c](r) : fmt(r[c])}
                </td>
              ))}
              {extra && <td>{extra.cell(r, rows)}</td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/**
 * "¿Puede esta comparación decidir algo?" Un medidor con cuánto falta, y debajo
 * los cuatro valores de la vista tal cual (incluido el `false`).
 *
 * El medidor compara contra n_needed_per_arm × cantidad de brazos (los CV
 * que se comparan): es el mismo corte que usa v_power_check (n >= 2000).
 */
function PowerBody({ row, arms }: { row: Row; arms: number }) {
  const n = num(row.n_applications);
  const need = num(row.n_needed_per_arm) * arms;
  const share = need ? Math.min(100, (n / need) * 100) : 0;
  const can = row.can_compare_variants === true;
  return (
    <>
      <p className="an-big">
        {n}
        <small>
          {" "}
          of {need.toLocaleString("en-US")} applications
        </small>
      </p>
      <div className="meter meter-lg" aria-hidden="true">
        <i style={{ width: `${Math.max(share, 1)}%` }} />
      </div>
      <dl className="an-dl">
        {Object.entries(row)
          .filter(([k]) => k !== "guidance")
          .map(([k, v]) => (
            <div key={k}>
              <dt>{label(k)}</dt>
              <dd>
                {k === "can_compare_variants" ? (
                  <span className="pill" data-ok={can || undefined}>
                    {String(v)}
                  </span>
                ) : (
                  fmt(v)
                )}
              </dd>
            </div>
          ))}
      </dl>
      {typeof row.guidance === "string" && <p className="an-guidance">{row.guidance}</p>}
    </>
  );
}
