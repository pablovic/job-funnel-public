import Link from "next/link";
import { LeakBar } from "@/components/LeakBar";
import { PageHead } from "@/components/PageHead";
import { api } from "@/lib/api";
import type { Opportunity } from "@/lib/types";
import { ApplyBoard } from "./ApplyBoard";

/**
 * The apply board — and the third filter.
 *
 * /triage is the quick pass: a glance, y/m/n, twenty postings in ten minutes.
 * This is the slow pass: the posting gets read properly, and only then does it
 * become an application or get dropped. Three filters, each cheaper than the
 * one after it, which is the whole point of having three.
 *
 * The maybes live here too. A "maybe" in Decide means "five seconds is not
 * enough to tell" — so it has to land somewhere that gives it five minutes.
 * Without that, deciding "maybe" is the same as deciding nothing, and the
 * posting quietly disappears.
 */
export const dynamic = "force-dynamic";

const byFit = (a: Opportunity, b: Opportunity) => (b.fit ?? 0) - (a.fit ?? 0);

export default async function ApplyPage() {
  let rows: Opportunity[] = [];
  let failed = false;
  try {
    // include_archived: la columna de descartadas necesita verlas para deshacer.
    // Se pide tambien para los maybe: antes un maybe descartado desaparecia de la
    // pantalla y no habia forma de deshacerlo.
    const [yes, maybe] = await Promise.all([
      api.get<Opportunity[]>("/opportunities?verdict=yes&limit=200&include_archived=true"),
      api.get<Opportunity[]>("/opportunities?verdict=maybe&limit=200&include_archived=true"),
    ]);
    rows = [...yes, ...maybe].sort(byFit);
  } catch {
    failed = true;
  }

  if (failed) {
    return (
      <main className="page">
        <PageHead title="Apply" />
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
        <PageHead title="Apply" />
        <LeakBar />
        <div className="empty">
          <h2>Nothing decided yet.</h2>
          <p>
            Work through Decide first. Everything you mark yes or maybe lands here
            with its score, its gaps and the CV to send.
          </p>
          <Link href="/triage" className="btn btn-primary">
            Open Decide
          </Link>
        </div>
      </main>
    );
  }

  const waiting = rows.filter((r) => r.status !== "archived" && !r.applied).length;

  return (
    <main className="page page--board">
      <PageHead title="Apply" count={waiting} countLabel="to review">
        The close read. Read the posting properly, then move it to Applied to log it or to
        Dropped to file it away: drag the card, or use the ⋮ menu. Drops are kept, never deleted.
      </PageHead>
      <LeakBar />
      <ApplyBoard rows={rows} />
    </main>
  );
}
