import Link from "next/link";
import { notFound } from "next/navigation";
import { Avatar } from "@/components/Avatar";
import { IconExternal } from "@/components/Icons";
import { OpportunityDetail } from "@/components/OpportunityDetail";
import { api } from "@/lib/api";
import { roleName } from "@/lib/scoring";
import type { Opportunity } from "@/lib/types";

/**
 * One opportunity, explained, as a full page.
 *
 * El mismo contenido que el panel lateral (es el mismo componente), pero con
 * dirección propia: sirve para guardarlo, mandarlo o abrirlo en otra pestaña.
 *
 * The deck answers "should I look at this". This page answers the question that
 * comes after a yes: *why* did it score what it scored, what is missing, and
 * which CV goes out. Every number here is decomposed rather than asserted —
 * a fit of 50 that is 20 points of domain and 2 of craft is a different
 * proposition from the same 50 split evenly, and the difference changes what
 * you write in the application.
 */
export const dynamic = "force-dynamic";

export default async function OpportunityPage({
  params,
}: {
  // Next 15: params llega como promesa y hay que esperarla.
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  let o: Opportunity;
  try {
    o = await api.get<Opportunity>(`/opportunities/${id}`);
  } catch {
    notFound();
  }

  return (
    <main className="page page--narrow">
      <p className="back">
        <Link href="/apply" className="btn">
          ← Back to Apply
        </Link>
      </p>

      <header className="op-head">
        <Avatar name={o.company} size="lg" />
        <div>
          <h1>{roleName(o.title, o.company)}</h1>
          <p>
            {o.company ?? "Unknown company"}
            {o.url && (
              <a href={o.url} target="_blank" rel="noreferrer" className="dr-ext">
                Open posting <IconExternal size={14} />
              </a>
            )}
          </p>
        </div>
      </header>

      <OpportunityDetail o={o} />
    </main>
  );
}
