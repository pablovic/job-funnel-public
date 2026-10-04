export type Verdict = "yes" | "maybe" | "no";

export interface Gap {
  requirement: string;
  quote: string;
  severity?: "blocking" | "teachable" | "cosmetic";
}

export interface Opportunity {
  id: string;
  title: string;
  company: string | null;
  url: string | null;
  status: string;
  lang: string | null;
  seniority: string | null;
  remote: string | null;
  comp_published: boolean | null;
  comp_usd_year_min: number | null;
  comp_usd_year_max: number | null;
  fit: number | null;
  dimensions: Record<string, number> | null;
  gaps: Gap[] | null;
  rationale: string | null;
  recommended_cv: "ic" | "lead" | null;
  rule_flags: string[];
  verdict: Verdict | null;
  captured_at: string;
  /** True once a row exists in `applications`. Set by the API, never here. */
  applied: boolean;
  /** The words the scorer actually matched. */
  tech_tags: string[];
  domain_tags: string[];
  /** global | latam | us | … | unknown */
  geo_scope: string | null;
  /** Only the detail endpoint returns this; the list leaves it null. */
  raw_text: string | null;
}

export interface Funnel {
  surfaced: number;
  shortlisted: number;
  applied: number;
  responded: number;
  in_process: number;
  offers: number;
  apply_rate_pct: number | null;
  response_rate_pct: number | null;
  /** Shortlisted que sobrevivieron a la lectura atenta (no archivadas). */
  kept: number;
}
export type Stage =
  | "applied" | "ack" | "screening" | "technical" | "onsite"
  | "offer" | "rejected" | "withdrawn" | "ghosted";

/** Una fila de /applications: la vista v_application_state mas los nombres. */
export interface ApplicationRow {
  application_id: string;
  opportunity_id: string;
  applied_at: string;
  cv_variant: string;
  comp_asked_usd: number | null;
  channel: string | null;
  current_stage: Stage | null;
  first_response_at: string | null;
  title: string;
  url: string | null;
  company: string | null;
  pay_usd_year: number | null;
  days_to_response: number | null;
}
