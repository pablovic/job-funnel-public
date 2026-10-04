import Link from "next/link";
import { LeakBar } from "@/components/LeakBar";
import { api } from "@/lib/api";
import type { Opportunity } from "@/lib/types";
import { ApplyTable } from "./ApplyTable";

/**
 * The apply list — and the third filter.
 *
 * /triage is the quick pass: a glance, y/m/n, twenty postings in ten minutes.
 * This is the slow pass: the posting gets read properly, and only then does it
 * become an application or get dropped. Three filters, each cheaper than the
 * one after it, which is the whole point of having three.
 *
 * The maybes live here too. A "maybe" in the deck means "five seconds is not
 * enough to tell" — so it has to land somewhere that gives it five minutes.
 * Without that, deciding "maybe" is the same as deciding nothing, and the
 * posting quietly disappears.
 */
export const dynamic = "force-dynamic";

const byFit = (a: Opportunity, b: Opportunity) => (b.fit ?? 0) - (a.fit ?? 0);

export default async function ApplyPage() {
  let yes: Opportunity[] = [];
  let maybe: Opportunity[] = [];
  let failed = false;
  try {
    // include_archived: la seccion de descartadas necesita verlas para deshacer.
    [yes, maybe] = await Promise.all([
      api.get<Opportunity[]>("/opportunities?verdict=yes&limit=200&include_archived=true"),
      api.get<Opportunity[]>("/opportunities?verdict=maybe&limit=200"),
    ]);
  } catch {
    failed = true;
  }

  const dropped = yes.filter((r) => r.status === "archived").sort(byFit);
  const sent = yes.filter((r) => r.status !== "archived" && r.applied).sort(byFit);
  const pending = yes.filter((r) => r.status !== "archived" && !r.applied).sort(byFit);
  const pendingMaybe = maybe.filter((r) => r.status !== "archived" && !r.applied).sort(byFit);

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

  if (!yes.length && !maybe.length) {
    return (
      <main>
        <LeakBar />
        <div className="empty">
          <h2>Nothing decided yet.</h2>
          <p>
            Work through the deck first. Everything you mark yes or maybe lands here
            with its score, its gaps and the CV to send.
          </p>
          <Link href="/triage">Open the deck</Link>
        </div>
      </main>
    );
  }

  return (
    <main>
      <LeakBar />

      <h2 className="section-head">
        To apply <span className="count">{pending.length}</span>
      </h2>
      <p className="hint">
        Read the posting, then decide. <b>Applied</b> logs it and moves it to
        Applications; <b>Drop</b> files it away and can be undone. Hover a role to
        see how its score was built.
      </p>

      {pending.length === 0 ? (
        <p className="hint">
          Nothing waiting. Back to the <Link href="/triage">deck</Link>.
        </p>
      ) : (
        <ApplyTable rows={pending} mode="pending" />
      )}

      {pendingMaybe.length > 0 && (
        <>
          <h2 className="section-head">
            Maybe — needs a closer look{" "}
            <span className="count">{pendingMaybe.length}</span>
          </h2>
          <p className="hint">
            Five seconds was not enough in the deck. Open the posting and settle it:{" "}
            <b>Yes</b> moves it up to the list above, <b>Drop</b> files it away. A
            maybe you never come back to is a no you never admitted.
          </p>
          <ApplyTable rows={pendingMaybe} mode="maybe" />
        </>
      )}

      {sent.length > 0 && (
        <>
          <h2 className="section-head muted">
            Already applied <span className="count">{sent.length}</span>
          </h2>
          <ApplyTable rows={sent} mode="applied" />
        </>
      )}

      {dropped.length > 0 && (
        <>
          <h2 className="section-head muted">
            Dropped on review <span className="count">{dropped.length}</span>
          </h2>
          <p className="hint">
            Passed the quick filter, did not survive a close read. Kept, not deleted.
          </p>
          <ApplyTable rows={dropped} mode="dropped" />
        </>
      )}
    </main>
  );
}
