import { LeakBar } from "@/components/LeakBar";
import { api } from "@/lib/api";

interface Row { [k: string]: string | number | boolean | null }

async function table(name: string): Promise<Row[]> {
  try { return await api.get<Row[]>(`/analytics/${name}`); } catch { return []; }
}

function Table({ title, note, rows }: { title: string; note?: string; rows: Row[] }) {
  if (!rows.length) return null;
  const cols = Object.keys(rows[0]);
  return (
    <section style={{ marginTop: "2.5rem" }}>
      <h2 style={{ fontSize: "1.125rem", margin: 0 }}>{title}</h2>
      {note && <p style={{ color: "var(--ink-soft)", maxWidth: "60ch" }}>{note}</p>}
      <table>
        <thead>
          <tr>{cols.map((c) => <th key={c} className={typeof rows[0][c] === "number" ? "num" : ""}>{c.replace(/_/g, " ")}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {cols.map((c) => (
                <td key={c} className={typeof r[c] === "number" ? "num" : ""}>{String(r[c] ?? "—")}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

export default async function AnalyticsPage() {
  const [effort, variants, power, bias, followups] = await Promise.all([
    table("effort"), table("variants"), table("power"), table("bias"), table("followups"),
  ]);

  return (
    <main>
      <LeakBar />
      <Table title="Where the week went" rows={effort}
        note="Ingested, auto-filtered, reviewed, applied. The gap between reviewed and applied is the one that matters." />
      <Table title="Response by CV variant" rows={variants} />
      <Table title="Can this comparison decide anything?" rows={power}
        note="Below roughly a thousand applications per arm, the variant table is descriptive. Read it, do not rewrite the CV on it." />
      <Table title="Rejection rate by whether pay was published" rows={bias}
        note="If the rejection rate is far higher for unpublished ranges, the filter is firing on disclosure policy rather than fit." />
      <Table title="Silent for more than a week" rows={followups} />
    </main>
  );
}
