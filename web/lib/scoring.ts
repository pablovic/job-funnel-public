/**
 * Lo que el puntaje significa, para poder explicarlo en pantalla.
 *
 * ACOPLAMIENTO A DECLARAR: los pesos y los umbrales de abajo son una copia de
 * WEIGHTS y de score() en `api/app/free/scorer.py`. Si alla cambian, hay que
 * cambiarlos aca tambien o la pantalla va a mentir sobre como se compuso el
 * numero.
 *
 * Se copian en vez de pedirlos a la API a proposito: son una constante de
 * diseno, no un dato, y un endpoint para seis numeros fijos es mas cableado del
 * que el problema justifica. El costo es este comentario.
 */

export const COMP_FLOOR_USD = 85_000;

export const WEIGHTS: Record<string, number> = {
  domain: 0.28,
  craft: 0.28,
  comp: 0.18,
  level_fit: 0.14,
  channel: 0.07,
  language: 0.05,
};

/** Qué mide cada dimensión. */
export const MEANING: Record<string, string> = {
  domain:
    "Industry overlap — marketplace, growth, fintech, ecommerce, SaaS, logistics.",
  craft:
    "Tools and methods named in the posting — SQL, Python, A/B testing, statistics, BI.",
  comp:
    "Published pay against the $85k floor. Unpublished scores 5, never 0: silence is not evidence about pay.",
  level_fit: "How the seniority in the title maps to where you are.",
  channel:
    "A product company you apply to directly, or a consultancy / staffing middleman.",
  language: "English, Spanish or Portuguese.",
};

const k = (n: number) => `$${Math.round(n / 1000)}k`;

/**
 * El diccionario: qué quiere decir "comp 10" y no otro número.
 * Los umbrales son los mismos que usa el scorer, no aproximaciones.
 */
export function explainValue(key: string, v: number): string {
  switch (key) {
    case "comp":
      if (v >= 10) return `Published pay tops ${k(COMP_FLOOR_USD * 1.5)} — at least 1.5× your floor.`;
      if (v >= 8) return `Published pay clears your ${k(COMP_FLOOR_USD)} floor.`;
      if (v >= 5) return "No pay published. Scores 5 by default, never 0 — silence is not evidence about pay.";
      if (v >= 4) return `Published pay lands just under the floor (${k(COMP_FLOOR_USD * 0.8)}–${k(COMP_FLOOR_USD)}).`;
      return "Published pay is well below your floor.";

    case "craft":
      if (v >= 8) return "Several tools you know are named — the posting is asking for your stack.";
      if (v >= 6) return "Your core stack is there — SQL and Python together guarantee at least a 6 on their own.";
      if (v >= 3) return "A couple of weak tool matches.";
      if (v > 0) return "Barely any tool from your stack is named.";
      return "No tool from your stack appears. Often means the posting is written in prose, not that the job doesn't need them.";

    case "domain":
      if (v >= 9) return "Two or more strong industry matches.";
      if (v >= 4.5) return "One solid industry match.";
      if (v > 0) return "A weak industry signal — possibly one word in a boilerplate paragraph.";
      return "No industry overlap detected.";

    case "level_fit":
      if (v >= 10) return "Senior — the level you are targeting.";
      if (v >= 9) return "Staff — close to your level.";
      if (v >= 7) return "Mid — below your level, though a mid title paying USD can still beat a manager title paying BRL.";
      if (v >= 6) return "Lead, or the level could not be read. 6 is the neutral default.";
      if (v >= 3) return "Manager — a people-management role.";
      if (v >= 2) return "Head or Director — people management, well above IC work.";
      return "Junior.";

    case "channel":
      if (v >= 10) return "A product company. You apply directly.";
      if (v >= 7) return "Company type unknown — pasted postings don't carry it, so this is the neutral 7.";
      if (v >= 3) return "A consultancy.";
      if (v >= 2) return "An agency.";
      return "Staffing. Near-zero conversion in your own history.";

    case "language":
      return v >= 10 ? "English, Spanish or Portuguese." : "Not a language you work in.";

    default:
      return "";
  }
}

/** Qué cuenta cada tramo de la barra de arriba. Espeja views.sql (v_funnel). */
export const FUNNEL_MEANING: Record<string, string> = {
  surfaced:
    "Postings that passed the automatic filters and reached you. Anything auto-rejected — staffing, on-site, US-only, wrong role family — is not counted here.",
  shortlisted: "Marked yes or maybe in the deck — the quick filter, one glance each.",
  kept: "Survived a close read on the apply list. Dropping one here is the third filter, and the cheapest place to say no after the deck.",
  applied:
    "Logged as actually submitted. Raising this number is the point of the whole system.",
  answered: "Got any reply at all after applying.",
};

export interface Contribution {
  key: string;
  label: string;
  /** 0–10, as the scorer emitted it. */
  value: number;
  /** Share of the final score this dimension can carry. */
  weight: number;
  /** Points out of 100 this dimension actually contributed. */
  points: number;
  meaning: string;
  /** What this particular number means. */
  reading: string;
}

/**
 * fit = sum(dimension * weight) * 10, so a dimension's contribution to the
 * 0–100 score is value * weight * 10. Devuelto de mayor a menor aporte: lo que
 * explica el numero va primero.
 */
export function contributions(
  dimensions: Record<string, number> | null,
): Contribution[] {
  if (!dimensions) return [];
  return Object.entries(dimensions)
    .map(([key, value]) => {
      const weight = WEIGHTS[key] ?? 0;
      return {
        key,
        label: key.replace(/_/g, " "),
        value,
        weight,
        points: value * weight * 10,
        meaning: MEANING[key] ?? "",
        reading: explainValue(key, value),
      };
    })
    .sort((a, b) => b.points - a.points);
}

/** Por qué el scorer eligió ese CV. Espeja `_cv_variant` en free/scorer.py. */
export function cvReason(o: {
  recommended_cv: string | null;
  seniority: string | null;
}): string {
  if (o.recommended_cv === "lead") {
    return o.seniority === "manager" || o.seniority === "head"
      ? `The title reads as ${o.seniority} — a people-management role.`
      : "The posting shows evidence of actual reports, not just the word “lead”.";
  }
  return "No evidence of direct reports. “Lead” in a title is usually an IC role, and the manager CV reads as overqualified.";
}

export function money(o: {
  comp_usd_year_min: number | null;
  comp_usd_year_max: number | null;
}): string {
  if (!o.comp_usd_year_max) return "not published";
  const lo = Math.round((o.comp_usd_year_min ?? 0) / 1000);
  const hi = Math.round(o.comp_usd_year_max / 1000);
  return lo && lo !== hi ? `$${lo}k–$${hi}k` : `$${hi}k`;
}
