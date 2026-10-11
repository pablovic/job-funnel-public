import Link from "next/link";
import { LeakBar } from "@/components/LeakBar";
import { PageHead } from "@/components/PageHead";
import { api } from "@/lib/api";
import type { ApplicationRow, Opportunity } from "@/lib/types";
import { PipelineBoard } from "./PipelineBoard";

/**
 * Lo enviado, y en que quedo cada uno.
 *
 * Es la unica pantalla donde el estado se edita despues del hecho, porque es la
 * unica cuyos datos siguen cambiando solos: alguien contesta, o no contesta.
 */
export const dynamic = "force-dynamic";

// Etapas en las que la postulacion ya no esta viva.
const CLOSED = ["rejected", "withdrawn", "ghosted"];

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
      <main className="page">
        <PageHead title="Applications" />
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
      <main className="page">
        <PageHead title="Applications" />
        <LeakBar />
        <div className="empty">
          <h2>No applications logged yet.</h2>
          <p>
            Log one the moment you submit it, not later. The date, the CV variant and
            the number you asked for are the only inputs the funnel has.
          </p>
          <Link href="/apply" className="btn btn-primary">
            Go to Apply
          </Link>
        </div>
      </main>
    );
  }

  // El puntaje de cada postulacion, para el anillo de la tarjeta. /applications no
  // lo trae (es la vista de estado, no la de puntajes), asi que se pide aparte.
  // Si falla, las tarjetas simplemente salen sin anillo.
  const fits: Record<string, number | null> = {};
  try {
    const opps = await api.get<Opportunity[]>("/opportunities?status=applied&limit=200");
    for (const o of opps) fits[o.id] = o.fit;
  } catch {
    /* sin anillos */
  }

  const answered = rows.filter((r) => r.first_response_at).length;
  const waiting = rows.filter(
    (r) => !r.first_response_at && !["ghosted", "withdrawn"].includes(r.current_stage ?? ""),
  ).length;
  const active = rows.filter((r) => !CLOSED.includes(r.current_stage ?? "")).length;

  return (
    <main className="page page--board">
      <PageHead title="Applications" count={active} countLabel="active">
        {answered} answered · {waiting} still waiting. Drag a role to another stage, or use the ⋮
        menu on its card. Either way it adds an event; it does not overwrite the last one.
      </PageHead>
      <LeakBar />
      <PipelineBoard rows={rows} fits={fits} />
    </main>
  );
}
