import Link from "next/link";
import { LeakBar } from "@/components/LeakBar";
import { api } from "@/lib/api";
import type { ApplicationRow } from "@/lib/types";
import { PipelineTable } from "./PipelineTable";

/**
 * Lo enviado, y en que quedo cada uno.
 *
 * Es la unica pantalla donde el estado se edita despues del hecho, porque es la
 * unica cuyos datos siguen cambiando solos: alguien contesta, o no contesta.
 */
export const dynamic = "force-dynamic";

export default async function PipelinePage() {
  let rows: ApplicationRow[] = [];
  let failed = false;
  try {
    rows = await api.get<ApplicationRow[]>("/applications");
  } catch {
    failed = true;
  }

  if (failed) {
    return (
      <main>
        <LeakBar />
        <div className="empty">
          <h2>The API is not answering.</h2>
          <p>
            Check that the containers are up: <code>docker compose ps</code> should
            show <code>db</code> and <code>api</code> running.
          </p>
        </div>
      </main>
    );
  }

  if (!rows.length) {
    return (
      <main>
        <LeakBar />
        <div className="empty">
          <h2>No applications logged yet.</h2>
          <p>
            Log one the moment you submit it, not later. The date, the CV variant and
            the number you asked for are the only inputs the funnel has.
          </p>
          <Link href="/apply">Go to the apply list</Link>
        </div>
      </main>
    );
  }

  const answered = rows.filter((r) => r.first_response_at).length;
  const waiting = rows.filter(
    (r) => !r.first_response_at && !["ghosted", "withdrawn"].includes(r.current_stage ?? ""),
  ).length;

  return (
    <main>
      <LeakBar />
      <h2 className="section-head">
        Applications <span className="count">{rows.length}</span>
      </h2>
      <p className="hint">
        {answered} answered · {waiting} still waiting. Change a stage in the row —
        it adds an event, it does not overwrite the last one.
      </p>
      <PipelineTable rows={rows} />
    </main>
  );
}
