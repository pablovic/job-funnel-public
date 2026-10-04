/**
 * Cliente de la API.
 *
 * Este codigo corre en dos lugares distintos, y cada uno llega a la API por
 * un camino diferente:
 *
 * - En el SERVIDOR de Next (las paginas como /apply, que piden datos antes de
 *   mandar el HTML): corre en tu PC, asi que habla directo con FastAPI en
 *   localhost:8000.
 *
 * - En el NAVEGADOR (el deck, los botones): puede ser tu PC o tu celular. En el
 *   celular, "localhost" es el celular mismo, donde no hay ninguna API. Por eso
 *   el navegador pide a /api/..., y next.config.mjs lo reenvia a FastAPI.
 */
const BASE =
  typeof window === "undefined"
    ? (process.env.API_URL ?? "http://localhost:8000")
    : "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T,>(path: string) => request<T>(path),
  post: <T,>(path: string, body: unknown) =>
    request<T>(path, { method: "POST", body: JSON.stringify(body) }),
};

export const fetcher = <T,>(path: string) => api.get<T>(path);
