"use client";

import useSWR, { mutate } from "swr";
import { fetcher } from "@/lib/api";
import type { Funnel, Opportunity } from "@/lib/types";

/**
 * Los números chicos del menú lateral (Decide 7, Applications 10).
 *
 * Cada uno sale de un pedido que la propia app ya sabe hacer; no hay endpoint
 * nuevo. SWR guarda las respuestas por "clave" (el texto del pedido), así que
 * si dos componentes piden la misma clave, el pedido se hace una sola vez.
 * `KEY_DECIDE` es justamente la clave que usa la lista de Decide: contar desde
 * ahí significa que el número del menú baja en el mismo instante en que decidís.
 */
export const KEY_DECIDE = "/opportunities?unlabeled=true&limit=100";
const KEY_YES = "/opportunities?verdict=yes&not_applied=true&limit=100";
const KEY_MAYBE = "/opportunities?verdict=maybe&not_applied=true&limit=100";
export const KEY_FUNNEL = "/analytics/funnel";

export interface NavCounts {
  decide?: number;
  apply?: number;
  applications?: number;
}

export function useNavCounts(): NavCounts {
  const decide = useSWR<Opportunity[]>(KEY_DECIDE, fetcher);
  const yes = useSWR<Opportunity[]>(KEY_YES, fetcher);
  const maybe = useSWR<Opportunity[]>(KEY_MAYBE, fetcher);
  const funnel = useSWR<Funnel[]>(KEY_FUNNEL, fetcher);

  return {
    decide: decide.data?.length,
    // Lo que /apply tiene para hacer: los yes sin enviar más los maybe sin resolver.
    // Los archivados quedan afuera solos (la API no los devuelve por defecto).
    apply: yes.data && maybe.data ? yes.data.length + maybe.data.length : undefined,
    applications: funnel.data?.[0]?.applied,
  };
}

/** Vuelve a pedir los números que cambian cuando se aplica o se descarta algo. */
export function refreshCounts() {
  [KEY_YES, KEY_MAYBE, KEY_FUNNEL].forEach((k) => mutate(k));
}
