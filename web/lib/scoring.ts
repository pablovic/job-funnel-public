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
  shortlisted: "Marked yes or maybe on the Decide screen — the quick filter, one glance each.",
  kept: "Survived a close read on the Apply board. Dropping one here is the third filter, and the cheapest place to say no after Decide.",
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

/* ===================================================================== vista
   Todo lo de abajo es PRESENTACIÓN: decide cómo se muestra el puntaje, no cómo
   se calcula. Si cambian los pesos, se cambian arriba; esto no se toca. */

/** El orden en que se nombran las seis dimensiones. Es el orden de las etiquetas. */
export const DIM_ORDER = ["craft", "domain", "level_fit", "comp", "language", "channel"];

/** high = verde, mid = ocre, low = gris. Un solo lugar para cambiar los cortes. */
export type Tier = "high" | "mid" | "low";

/** Puntaje total (0–100) → color del anillo. */
export function fitTier(fit: number | null | undefined): Tier | "none" {
  if (fit == null) return "none";
  // Se redondea primero: el anillo muestra el número redondeado, y un 64,6 que se
  // ve como "65" no puede tener un color distinto al de otro "65".
  const shown = Math.round(fit);
  if (shown >= 80) return "high";
  if (shown >= 65) return "mid";
  return "low";
}

/** Valor de una dimensión (0–10) → color de su etiqueta. */
export function dimTier(v: number): Tier {
  if (v >= 8) return "high";
  if (v >= 5) return "mid";
  return "low";
}

export const dimLabel = (key: string) => key.replace(/_/g, " ");

/** Las dimensiones en el orden de DIM_ORDER; las que no conozca van al final. */
export function orderedDimensions(
  dimensions: Record<string, number> | null | undefined,
): [string, number][] {
  if (!dimensions) return [];
  const known = DIM_ORDER.filter((k) => k in dimensions).map(
    (k) => [k, dimensions[k]] as [string, number],
  );
  const rest = Object.entries(dimensions).filter(([k]) => !DIM_ORDER.includes(k));
  return [...known, ...rest];
}

const escapeRe = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/**
 * El título tal como lo guarda la base a veces trae la empresa pegada
 * ("Data Analyst — Marlin Freight"). En pantalla la empresa ya va aparte, así
 * que se la saca del título para no leerla dos veces.
 */
export function roleName(title: string, company: string | null): string {
  if (!company) return title;
  const co = escapeRe(company.trim());
  const cleaned = title
    .replace(new RegExp(`\\s*(?:[—–|@-]|\\bat\\b)\\s*${co}\\s*$`, "i"), "")
    .replace(new RegExp(`^\\s*${co}\\s*[—–|:-]\\s*`, "i"), "")
    .trim();
  return cleaned || title;
}

/** "Saltmarsh Logistics" → "SL". Para el cuadradito donde iría un logo. */
export function initials(name: string | null): string {
  if (!name) return "?";
  const words = name.trim().split(/\s+/).filter(Boolean);
  const letters = (words.length > 1 ? words.slice(0, 2) : [words[0]]).map((w) => w[0]);
  return (words.length > 1 ? letters.join("") : words[0].slice(0, 2)).toUpperCase();
}

/**
 * "3 days ago". Usa la hora actual, así que SOLO va en componentes que se
 * dibujan después de cargar (la lista de Decide, el panel). En una pantalla que
 * el servidor ya armó, el servidor y el navegador podrían calcular valores
 * distintos y React protestaría; ahí se muestran fechas ISO.
 */
export function timeAgo(iso: string, now: number = Date.now()): string {
  const days = Math.floor((now - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return "today";
  if (days === 1) return "yesterday";
  if (days < 14) return `${days} days ago`;
  if (days < 60) return `${Math.floor(days / 7)} weeks ago`;
  return `${Math.floor(days / 30)} months ago`;
}

export function remoteLabel(remote: string | null | undefined): string {
  switch (remote) {
    case "remote_global": return "Remote (worldwide)";
    case "remote_country": return "Remote (by country)";
    case "hybrid": return "Hybrid";
    case "onsite": return "On-site";
    default: return "Remote unknown";
  }
}

export function geoLabel(scope: string | null | undefined): string | null {
  if (!scope || scope === "unknown") return null;
  if (scope === "global") return "Open globally";
  if (scope === "latam") return "Open to LatAm";
  if (scope === "us") return "US only";
  return scope.toUpperCase();
}

export function seniorityLabel(s: string | null | undefined): string | null {
  if (!s || s === "unknown") return null;
  return s.charAt(0).toUpperCase() + s.slice(1);
}

export const cvLabel = (cv: string | null | undefined) =>
  cv === "lead" ? "Lead CV" : "IC CV";
