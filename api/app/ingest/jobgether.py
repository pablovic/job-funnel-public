"""Jobgether — API publica oficial, sin key y sin registro.

    https://jobgether.com/api/v1/jobs

Es la tercera fuente automatizada, y la primera que no es un board de empresa:
Greenhouse re-consulta empresas conocidas, Remotive descubre por palabra clave,
y esta agrega un catalogo grande de puestos remotos.

LO QUE HAY QUE SABER ANTES DE CONFIAR EN SUS PUNTAJES
-----------------------------------------------------
La respuesta NO trae la descripcion del puesto. Devuelve metadatos —titulo,
empresa, ubicacion, modalidad, experiencia, rango salarial, funciones— y el link
al aviso en jobgether.com, nada mas.

Eso importa mucho aca: `craft` y `domain` se calculan buscando palabras en el
texto del aviso, y sin texto quedan cerca de cero SIEMPRE. Entre las dos pesan
el 56% del puntaje, asi que un puesto de Jobgether va a rankear sistematicamente
mas bajo que uno de Greenhouse aunque sea mejor.

Se compensa en dos lugares:
  - Aca: se arma una cabecera con todos los metadatos, de la que el extractor
    saca nivel, sueldo y geografia. Tres de las seis dimensiones quedan bien.
  - En rules/filters.py: un aviso sin descripcion se marca con una bandera, para
    que la pantalla avise que el puntaje es parcial en vez de fingir precision.

Conclusion practica: de esta fuente, el puntaje sirve para descartar, no para
ordenar. El link esta; el aviso se abre antes de decidir.

TERMINOS, respetados aca
------------------------
  - Publica y sin autenticar. Limitan por volumen en el borde, no con keys.
    Piden "mantener el volumen razonable y cachear lo que se pueda": esto corre
    una vez por dia desde el cron, nunca por pagina ni sincronicamente.
  - Se pausa entre paginas para no parecer un scraper.
  - La URL canonica del aviso se conserva como link.

config: {"keyword": "data analyst", "locations": ["anywhere"],
         "remoteType": "full-remote", "sort": "date",
         "limit": 25, "max_pages": 4}

Todos los parametros son opcionales; sin ninguno devuelve lo mas reciente.
Enteros: `limit` topea en 25 y `page` en 10, del lado del servidor.
"""
from __future__ import annotations

import re
import time

import httpx

from app.ingest.base import RawPosting

# /api/v1/jobs es la superficie estable. La vieja /astroapi/ai/jobs deja de
# responder el 2026-09-28; no usarla.
API = "https://jobgether.com/api/v1/jobs"

ARRAY_PARAMS = ("jobReferences", "locations", "industries", "contractType", "experience")
SCALAR_PARAMS = ("keyword", "remoteType", "includeHybrid", "salaryMin", "salaryMax",
                 "currency", "sort")

MAX_LIMIT = 25      # tope del servidor
MAX_PAGES = 10      # tope del servidor
PAUSE_SECONDS = 0.7


class JobgetherConfigError(RuntimeError):
    """Un parametro invalido. Se levanta en vez de devolver vacio: una fuente mal
    configurada que devuelve cero parece una fuente sin resultados, y eso se
    descubre semanas despues."""


def _params(config: dict, page: int) -> dict:
    p: dict[str, object] = {}
    for k in SCALAR_PARAMS:
        if config.get(k) not in (None, ""):
            p[k] = config[k]
    for k in ARRAY_PARAMS:
        v = config.get(k)
        if not v:
            continue
        # La API acepta lista o cadena separada por comas; se manda siempre
        # separada por comas, que funciona igual por GET y por POST.
        p[k] = ",".join(v) if isinstance(v, (list, tuple)) else v
    p["limit"] = min(int(config.get("limit", MAX_LIMIT)), MAX_LIMIT)
    p["page"] = page
    return p


def fetch(config: dict) -> list[RawPosting]:
    max_pages = min(int(config.get("max_pages", 3)), MAX_PAGES)
    out: list[RawPosting] = []

    with httpx.Client(timeout=25, headers={"User-Agent": "job-funnel/personal"}) as client:
        for page in range(1, max_pages + 1):
            if page > 1:
                time.sleep(PAUSE_SECONDS)
            try:
                r = client.get(API, params=_params(config, page))
            except httpx.HTTPError:
                break   # de red: lo que se junto hasta aca sirve igual

            if r.status_code == 400:
                raise JobgetherConfigError(_explain(r))
            if r.status_code >= 500 or r.status_code == 504:
                break   # transitorio: manana se reintenta
            if r.status_code != 200:
                break

            try:
                body = r.json()
            except ValueError:
                break

            jobs = body.get("jobs") or []
            out.extend(parse_job(j) for j in jobs)

            if not (body.get("pagination") or {}).get("hasMore"):
                break

    return out


def _explain(r: httpx.Response) -> str:
    """Los errores son RFC 9457. En un 400 vienen `field` y `allowedValues`, que
    es exactamente lo que hace falta para corregir la config sin ir a buscar la
    documentacion."""
    try:
        b = r.json()
    except ValueError:
        return f"Jobgether devolvio 400: {r.text[:200]}"
    msg = b.get("detail") or b.get("error") or "parametro invalido"
    field = b.get("field")
    allowed = b.get("allowedValues")
    parts = [f"Jobgether rechazo la consulta: {msg}"]
    if field:
        parts.append(f"El parametro es '{field}'.")
    if allowed:
        parts.append("Valores validos: " + ", ".join(map(str, allowed)))
    parts.append("Corregilo en la columna config de la tabla sources.")
    return " ".join(parts)


# "60000-80000 EUR" — la moneda va DESPUES del numero, y el extractor la espera
# antes. Sin normalizar esto, ningun sueldo de esta fuente se lee.
_RANGE_TRAILING_CUR = re.compile(
    r"^\s*([\d][\d.,]*)\s*(?:-|–|—|to)\s*([\d][\d.,]*)\s*([A-Z]{3}|\$|€)\s*$")
_SINGLE_TRAILING_CUR = re.compile(r"^\s*([\d][\d.,]*)\s*([A-Z]{3}|\$|€)\s*$")


def normalize_salary(raw: str) -> str:
    """'60000-80000 EUR' -> 'EUR 60000 - EUR 80000 per year'

    El 'per year' no es un invento: salaryMin y salaryMax estan documentados como
    filtros de sueldo ANUAL, asi que el rango que devuelven es anual.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    m = _RANGE_TRAILING_CUR.match(raw)
    if m:
        a, b, cur = m.groups()
        return f"{cur} {a} - {cur} {b} per year"
    m = _SINGLE_TRAILING_CUR.match(raw)
    if m:
        a, cur = m.groups()
        return f"{cur} {a} per year"
    return raw   # ya viene con la moneda adelante, o en un formato desconocido


def parse_job(job: dict) -> RawPosting:
    """Separado de fetch() para poder probarlo sin red."""
    title = (job.get("title") or "").strip()
    company = (job.get("company") or "").strip()
    location = (job.get("location") or "").strip()
    remote = (job.get("remote") or "").strip()
    salary = normalize_salary(job.get("salaryRange") or "")
    functions = job.get("jobFunctions") or []

    # La cabecera es todo lo que hay. El extractor saca de aca el nivel
    # (experience), el sueldo (salary) y la geografia (location + remote).
    bits = [f"{title} at {company}." if company else f"{title}."]
    if salary:
        bits.append(f"Salary: {salary}.")
    if location:
        bits.append(f"Location: {location}.")
    if remote:
        bits.append(f"Remote policy: {remote}.")
    if job.get("experience"):
        bits.append(f"Experience: {job['experience']}.")
    if job.get("contractType"):
        bits.append(f"Contract: {job['contractType']}.")
    if functions:
        bits.append("Job functions: " + ", ".join(functions) + ".")
    bits.append("NOTE: this listing carries no description. Open the posting.")

    # location_hint junta ubicacion y modalidad porque el filtro geografico lee
    # ese campo primero, y es la senal mas confiable que hay.
    hint = " ".join(x for x in (location, f"({remote})" if remote else "") if x).strip()

    return RawPosting(
        title=f"{title} — {company}" if company else title,
        raw_text=" ".join(bits),
        url=job.get("url"),
        external_id=str(job.get("id", "")),
        company=company,
        salary=salary,
        location=hint,
    )
