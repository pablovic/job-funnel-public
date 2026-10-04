"""Operational CLI. Everything the scheduler does is available here by hand, so
a broken cron never blocks a decision."""
from __future__ import annotations

import csv
import datetime as dt
import io
import re
import time
import hashlib
import json
import pathlib
from dataclasses import dataclass, field

import typer
from sqlalchemy import text

from app.db import SessionLocal
from app.models import (
    Application, ApplicationEvent, Company, JobDetail, Label, Opportunity,
    Score, Source,
)
from app.pipeline import ingest

cli = typer.Typer(no_args_is_help=True)


@cli.command()
def add(title: str, file: str, url: str = ""):
    """Ingest one posting from a text file. `funnel add "Lead Analyst" ./posting.txt`"""
    with SessionLocal() as db:
        opp, outcome = ingest(db, title=title, raw_text=open(file).read(), url=url or None)
        db.commit()
        typer.echo(f"{outcome}: {opp.id}")


def _run_source(db, src) -> dict:
    """Una fuente, de punta a punta: traer, filtrar, puntuar, guardar.

    Es la unidad que usan tanto `pull` (una fuente a mano) como `pull-all` (el
    cron), asi que las dos formas producen exactamente las mismas filas.
    """
    import importlib
    mod = importlib.import_module(f"app.ingest.{src.adapter}")
    found = mod.fetch(src.config)
    counts = {"found": len(found), "scored": 0, "rejected": 0, "duplicate": 0}
    for p in found:
        _, outcome = ingest(db, title=p.title, raw_text=p.raw_text, url=p.url,
                            source_id=src.id, company_hint=p.company,
                            salary_hint=p.salary, location_hint=p.location)
        counts[outcome] = counts.get(outcome, 0) + 1
    src.last_run_at = dt.datetime.now(dt.timezone.utc)
    return counts


@cli.command()
def pull(source: str):
    """Run one configured source adapter."""
    with SessionLocal() as db:
        src = db.query(Source).filter_by(name=source).one()
        counts = _run_source(db, src)
        db.commit()
        typer.echo(json.dumps(counts))


# El script diario busca esta marca para leer el resumen sin interpretar el
# resto de la salida. Si se cambia aca, hay que cambiarla en daily-pull.ps1.
SUMMARY_MARK = "SUMMARY "


@cli.command("pull-all")
def pull_all():
    """Corre TODAS las fuentes activas. Es el comando que ejecuta la automatizacion.

    Las fuentes salen de la tabla `sources`, no de una lista escrita a mano:
    una fuente nueva (o un board agregado con `boards --add`) entra sola en la
    proxima corrida, y una se apaga poniendo enabled = false.

    Cada fuente corre y se guarda por separado. Si Jobgether esta caido o una
    config esta mal, esa fuente falla y las demas siguen: un error en una API
    ajena no puede dejarte sin la busqueda del dia.

    Termina con una linea 'SUMMARY {...}' en JSON para que el script la lea, y
    sale con codigo 1 solo si fallaron TODAS.
    """
    totals = {"found": 0, "scored": 0, "rejected": 0, "duplicate": 0}
    failed: list[str] = []
    ran = 0

    with SessionLocal() as db:
        sources = (db.query(Source)
                   .filter(Source.enabled.is_(True), Source.adapter != "paste")
                   .order_by(Source.name).all())
        for src in sources:
            try:
                counts = _run_source(db, src)
                db.commit()
            except Exception as e:  # noqa: BLE001 - aislar, anotar, seguir
                db.rollback()
                failed.append(src.name)
                typer.echo(f"  {src.name:28} FALLO: {type(e).__name__}: {str(e)[:160]}")
                continue
            ran += 1
            for k in totals:
                totals[k] += counts.get(k, 0)
            typer.echo(f"  {src.name:28} {counts['found']:>4} encontradas | "
                       f"{counts['scored']:>3} nuevas | {counts['rejected']:>3} descartadas | "
                       f"{counts['duplicate']:>4} ya estaban")

    typer.echo(SUMMARY_MARK + json.dumps({**totals, "sources": ran, "failed": failed}))
    if sources and not ran:
        raise typer.Exit(1)


# --------------------------------------------------------------------- backfill

# Etapas que implican que la empresa contesto, y por lo tanto necesitan fecha:
# sin saber CUANDO llego, el tiempo de respuesta no se puede medir.
RESPONSE_STAGES = {"ack", "screening", "technical", "onsite", "offer", "rejected"}

# Etapas que se registran pero NO son una respuesta de la empresa. Se guardan
# igual —sirven para saber en que quedo cada postulacion— y v_application_state
# las excluye de first_response_at. 'ghosted' es la ausencia de respuesta, y
# bajarse es una accion propia.
CLOSING_STAGES = {"ghosted", "withdrawn"}

ALL_STAGES = RESPONSE_STAGES | CLOSING_STAGES | {"applied"}
CV_VARIANTS = {"ic", "lead"}


@dataclass
class BackfillRow:
    company: str
    role: str
    applied_at: dt.datetime
    url: str | None = None
    cv_variant: str = "ic"
    comp_asked_usd: float | None = None
    posted: dict | None = None          # rango publicado por el aviso
    stage: str = ""
    response_at: dt.datetime | None = None
    note: str = ""
    posting_text: str = ""
    warnings: list[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        # El separador " — " (em dash) es el que parte la regla de familia de
        # puesto. Tiene que ser el mismo que usan greenhouse.py y remotive.py.
        #
        # Si el puesto o la empresa YA traen una raya larga —"Lead Data Analyst
        # — Growth"— el separador se vuelve ambiguo y partir el titulo deja de
        # dar lo que deberia. Se baja a guion simple adentro de cada parte, asi
        # la raya larga del titulo significa una sola cosa.
        return f"{_flatten(self.role)} — {_flatten(self.company)}"


def _flatten(s: str) -> str:
    """Raya larga -> guion, para que el separador del titulo sea unico."""
    return " ".join(s.replace("—", "-").replace("–", "-").split())


_SLASH_DATE = re.compile(r"^\s*(\d{1,2})[/\-.](\d{1,2})[/\-.](\d{2,4})\s*$")


def _slash_parts(raw: str) -> tuple[int, int, int] | None:
    m = _SLASH_DATE.match(raw)
    if not m:
        return None
    a, b, y = (int(g) for g in m.groups())
    return a, b, (y + 2000 if y < 100 else y)


def detect_date_format(rows: list[dict]) -> tuple[str | None, str]:
    """Deduce si las fechas del archivo son D/M/AAAA o M/D/AAAA.

    No es adivinar: es leer TODAS las fechas del archivo y buscar una que solo
    pueda interpretarse de una manera. En '8/23/2026' el 23 no puede ser un mes,
    asi que ese archivo es M/D — y esa prueba vale para todas las demas filas,
    porque una planilla no mezcla formatos.

    Cuando el archivo no alcanza para probarlo —todos los numeros son 12 o
    menos, o hay fechas que se contradicen— devuelve None y no se carga nada.
    Ahi si seria adivinar, y una fecha corrida envenena el tiempo de respuesta,
    que es justo la metrica que este import viene a construir.
    """
    hay_barras = False
    prueba_dmy = prueba_mdy = ""
    for r in rows:
        for col in ("date", "response_date"):
            raw = (r.get(col) or "").strip()
            if not raw:
                continue
            try:
                dt.date.fromisoformat(raw)
                continue          # ISO: no hay nada que deducir
            except ValueError:
                pass
            parts = _slash_parts(raw)
            if not parts:
                continue
            hay_barras = True
            a, b, _ = parts
            if a > 12 and not prueba_dmy:
                prueba_dmy = raw
            if b > 12 and not prueba_mdy:
                prueba_mdy = raw

    if not hay_barras:
        return "iso", ""
    if prueba_dmy and prueba_mdy:
        return None, (f"'{prueba_dmy}' solo funciona como dia/mes y '{prueba_mdy}' solo "
                      "como mes/dia: el archivo mezcla los dos formatos")
    if prueba_dmy:
        return "dmy", f"'{prueba_dmy}' tiene {prueba_dmy.split('/')[0]} en el primer lugar"
    if prueba_mdy:
        return "mdy", f"'{prueba_mdy}' tiene {prueba_mdy.split('/')[1]} en el segundo lugar"
    return None, "ninguna fecha tiene un numero mayor a 12, asi que no hay forma de saberlo"


def _date(raw: str, label: str, warnings: list[str],
          fmt: str = "iso") -> dt.datetime | None:
    raw = (raw or "").strip()
    if not raw:
        return None
    d = None
    try:
        d = dt.date.fromisoformat(raw)
    except ValueError:
        parts = _slash_parts(raw)
        if parts and fmt in ("dmy", "mdy"):
            a, b, y = parts
            day, month = (a, b) if fmt == "dmy" else (b, a)
            try:
                d = dt.date(y, month, day)
            except ValueError:
                d = None
    if d is None:
        warnings.append(f"{label} '{raw}' no se pudo leer como fecha")
        return None
    # Mediodia UTC: evita que la fecha se corra un dia por zona horaria.
    return dt.datetime.combine(d, dt.time(12, 0), tzinfo=dt.timezone.utc)


def parse_row(row: dict, fmt: str = "iso", *,
              ack_same_day: bool = False) -> tuple[BackfillRow | None, list[str]]:
    """Una fila del CSV -> algo cargable, o None con el motivo.

    Separado de la escritura en la base a proposito: asi se puede probar sin
    Postgres, y un CSV con una fila rota no arruina las otras veintinueve.
    """
    warnings: list[str] = []
    g = lambda k: (row.get(k) or "").strip()  # noqa: E731

    company, role = g("company"), g("role")
    if not company or not role:
        return None, ["faltan 'company' o 'role', que son obligatorios"]

    applied_at = _date(g("date"), "date", warnings, fmt)
    if applied_at is None:
        # El motivo ya quedo en warnings; no se repite.
        return None, warnings or ["falta 'date', que es obligatoria"]

    cv = g("cv_variant").lower() or "ic"
    if cv not in CV_VARIANTS:
        warnings.append(f"cv_variant '{cv}' no es ic ni lead; se usa 'ic'")
        cv = "ic"

    comp, posted = _salary(g("salary_posted") or g("salary_asked"), warnings)

    stage = g("stage").lower()
    if stage and stage not in ALL_STAGES:
        warnings.append(f"stage '{stage}' no existe; se ignora. Validos: {', '.join(sorted(ALL_STAGES))}")
        stage = ""

    response_at = _date(g("response_date"), "response_date", warnings, fmt)
    if stage in RESPONSE_STAGES and response_at is None:
        # Un acuse es casi siempre automatico y llega el mismo dia. Con
        # --ack-same-day se asume eso, SOLO para 'ack': una invitacion a
        # screening puede llegar tres semanas despues y ahi la fecha si importa.
        if stage == "ack" and ack_same_day:
            response_at = applied_at
            warnings.append("acuse sin fecha: se toma el mismo dia de la postulacion")
        else:
            warnings.append(
                f"stage '{stage}' necesita 'response_date' para saber cuando llego; "
                "se carga como 'applied' y el tiempo de respuesta queda sin medir")
            stage = ""
    if response_at and response_at < applied_at:
        warnings.append("response_date es anterior a date; se ignora la respuesta")
        response_at, stage = None, ""

    return BackfillRow(
        company=company, role=role, applied_at=applied_at, url=g("url") or None,
        cv_variant=cv, comp_asked_usd=comp, posted=posted, stage=stage,
        response_at=response_at, note=g("note"), posting_text=g("text"),
        warnings=warnings,
    ), []


# Excel en Windows guarda "CSV (delimitado por comas)" en la codificacion del
# sistema, no en UTF-8: en un Windows en espanol eso es Windows-1252. Una raya
# larga, una comilla curva o una enie alcanzan para que falle la lectura.
# El orden importa: utf-8 primero porque es el unico que valida de verdad —si un
# archivo decodifica como utf-8, ES utf-8. cp1252 y latin-1 aceptan casi
# cualquier byte, asi que van despues, de mas preciso a mas permisivo.
ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def _decode(path: str) -> tuple[str, str]:
    raw = pathlib.Path(path).read_bytes()
    for enc in ENCODINGS:
        try:
            return raw.decode(enc), enc
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace"), "latin-1(con reemplazos)"


def read_rows(path: str) -> tuple[list[dict], str, str]:
    """Lee el CSV tolerando como lo guarda Excel de verdad.

    Tres cosas que pasan siempre y no deberian costar un viaje de ida y vuelta:

    - La codificacion. Excel guarda en Windows-1252, no en UTF-8 (ver arriba).
    - El separador. En configuracion regional espanola usa ';' en vez de ','.
    - Los encabezados. 'Company' y ' company ' son la misma columna.

    Lo que NO se adivina son las fechas: 03/04/2026 puede ser 3 de abril o 4 de
    marzo, y elegir mal envenena justamente la metrica de tiempo de respuesta
    que se quiere construir. Se exige AAAA-MM-DD y se avisa fila por fila.
    """
    text_all, encoding = _decode(path)
    if not text_all.strip():
        return [], ",", encoding

    first = text_all.splitlines()[0]
    delim = ";" if first.count(";") > first.count(",") else \
            "\t" if first.count("\t") > first.count(",") else ","

    # StringIO y no splitlines(): conserva los saltos de linea, que es lo que
    # permite que una nota entre comillas ocupe varias lineas sin romperse.
    reader = csv.DictReader(io.StringIO(text_all, newline=""), delimiter=delim)
    rows = []
    for raw in reader:
        rows.append({(k or "").strip().lower(): v for k, v in raw.items()})
    return rows, delim, encoding


# "RS 24000" es como se escribe R$ sin el simbolo. Solo se normaliza cuando
# viene pegado a un numero, para no tocar un "RS" que signifique otra cosa.
_RS = re.compile(r"\bRS\b(?=\s*[\d.,])")
_SIN_SUELDO = {"not published", "no publicado", "nao publicado", "n/a", "na", "-", "--", "?"}


def _salary(raw: str, warnings: list[str]) -> tuple[float | None, dict | None]:
    """La columna de sueldo trae una de dos cosas distintas, y se distinguen
    solas:

    - Un numero pelado ("90000") es lo que PEDISTE al postularte. Va a
      comp_asked_usd, que es lo que compara el analisis por variante de CV.
    - Cualquier otra cosa ("USD 75000 - 100000 Yearly", "RS 24000 - 30000
      Monthly") es el rango que PUBLICO el aviso. Va a los campos de la
      oportunidad, que es lo que alimenta la dimension `comp` y la auditoria de
      sesgo por rango publicado.

    Son datos distintos y los dos sirven; lo que no sirve es mezclarlos. Se
    reusa el mismo parser que usan las fuentes automaticas, asi que R$, USD,
    rangos, mensual y anual se leen igual que en cualquier aviso.
    """
    raw = (raw or "").strip()
    if not raw or raw.lower() in _SIN_SUELDO:
        return None, None

    pelado = raw.replace("$", "").replace(",", "").replace("_", "").strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", pelado):
        return float(pelado), None

    from app.free import extractor as free_extractor
    encontrado = free_extractor.find_salary("", _RS.sub("R$", raw))
    if encontrado is None:
        warnings.append(f"no pude leer el sueldo '{raw}'; se ignora")
        return None, None
    return None, encontrado


def _hash(r: BackfillRow) -> str:
    """Clave de deduplicacion estable: no depende del texto del aviso, que puede
    no estar, sino de a que se postulo."""
    key = f"{r.company}|{r.role}|{r.url or ''}".lower()
    return hashlib.sha256(" ".join(key.split()).encode()).hexdigest()


@cli.command()
def backfill(
    file: str,
    dry_run: bool = typer.Option(False, "--dry-run",
                                 help="Muestra que haria, sin escribir nada"),
    ack_same_day: bool = typer.Option(
        False, "--ack-same-day",
        help="Cuenta los acuses sin fecha como recibidos el mismo dia de la postulacion"),
    replace: bool = typer.Option(
        False, "--replace",
        help="Borra lo cargado por un backfill anterior y vuelve a empezar"),
):
    """Carga postulaciones YA ENVIADAS desde un CSV, con sus respuestas.

    Para las que se aplicaron antes de que existiera la app. Sin esto el embudo
    arranca en cero y las metricas no tienen nada que medir.

    Dos decisiones que conviene conocer:

    1. NO pasa por el filtro de reglas. Estas vacantes son hechos del pasado, no
       candidatas a filtrar: si el filtro las rechazara, desaparecerian del
       embudo y el dato se perderia.

    2. NO se puntuan. Se les crea una etiqueta 'yes' (postularse es decir que si)
       pero sin puntaje, para que no entren en v_scorer_agreement: treinta 'yes'
       automaticos ahi dentro harian que la metrica de acuerdo del scorer mida
       cualquier cosa. Si el CSV trae el texto del aviso en la columna 'text', si
       se extraen empresa, sueldo y modalidad, que no contaminan nada.
    """
    rows, delim, encoding = read_rows(file)

    if not rows:
        typer.echo("El CSV no tiene filas.")
        raise typer.Exit(1)

    nombre_delim = {";": "punto y coma", "\t": "tabulacion"}.get(delim, "coma")
    typer.echo(f"{len(rows)} filas, separadas por {nombre_delim}, codificacion {encoding}.")
    faltantes = {"date", "company", "role"} - set(rows[0])
    if faltantes:
        typer.echo(f"Faltan columnas obligatorias: {', '.join(sorted(faltantes))}")
        typer.echo(f"Las que encontre: {', '.join(sorted(k for k in rows[0] if k))}")
        raise typer.Exit(1)

    fmt, prueba = detect_date_format(rows)
    if fmt is None:
        typer.echo("\nNo puedo leer las fechas con seguridad: " + prueba + ".")
        typer.echo("Cambialas a AAAA-MM-DD y volve a intentar. En Excel: seleccionar")
        typer.echo("las columnas date y response_date, Formato de celdas, Personalizada,")
        typer.echo("escribir  aaaa-mm-dd  y guardar de nuevo como CSV.")
        raise typer.Exit(1)
    if fmt == "dmy":
        typer.echo(f"Fechas en formato dia/mes/ano ({prueba}).")
    elif fmt == "mdy":
        typer.echo(f"Fechas en formato mes/dia/ano ({prueba}).")

    created = skipped = failed = 0
    with SessionLocal() as db:
        if replace:
            borradas = _clear_backfill(db, dry_run=dry_run)
            verbo = "se borrarian" if dry_run else "borradas"
            typer.echo(f"{verbo} {borradas} filas de un backfill anterior.")

        for i, raw in enumerate(rows, start=2):  # fila 1 es el encabezado
            parsed, errors = parse_row(raw, fmt, ack_same_day=ack_same_day)
            if parsed is None:
                failed += 1
                for e in errors:
                    typer.echo(f"  fila {i}: SE SALTEA — {e}")
                continue
            for w in parsed.warnings:
                typer.echo(f"  fila {i}: aviso — {w}")

            h = _hash(parsed)
            if db.query(Opportunity).filter_by(content_hash=h).one_or_none():
                skipped += 1
                typer.echo(f"  fila {i}: ya estaba — {parsed.title}")
                continue

            if dry_run:
                created += 1
                typer.echo(f"  fila {i}: se cargaria — {parsed.title} "
                           f"({parsed.applied_at:%Y-%m-%d}, {parsed.cv_variant}"
                           f"{', ' + parsed.stage if parsed.stage else ''})")
                continue

            _write(db, parsed, h)
            created += 1

        if not dry_run:
            db.commit()

    typer.echo(json.dumps({"cargadas": created, "ya_estaban": skipped,
                           "con_error": failed, "dry_run": dry_run}))


def _clear_backfill(db, *, dry_run: bool = False) -> int:
    """Borra SOLO lo que cargo este comando.

    Se identifica por la marca que deja _write en el campo extraction, no por
    fecha ni por estado: asi no hay forma de llevarse por delante una vacante
    que entro por el deck o por una fuente automatica.
    """
    opp_ids = [r[0] for r in db.query(JobDetail.opportunity_id)
               .filter(JobDetail.extraction["provider"].astext == "backfill").all()]
    if not opp_ids or dry_run:
        return len(opp_ids)

    app_ids = [r[0] for r in db.query(Application.id)
               .filter(Application.opportunity_id.in_(opp_ids)).all()]
    if app_ids:
        (db.query(ApplicationEvent)
           .filter(ApplicationEvent.application_id.in_(app_ids))
           .delete(synchronize_session=False))
        (db.query(Application).filter(Application.id.in_(app_ids))
           .delete(synchronize_session=False))
    for modelo, col in ((Score, Score.opportunity_id), (Label, Label.opportunity_id),
                        (JobDetail, JobDetail.opportunity_id), (Opportunity, Opportunity.id)):
        db.query(modelo).filter(col.in_(opp_ids)).delete(synchronize_session=False)
    db.flush()
    return len(opp_ids)


def _write(db, r: BackfillRow, h: str) -> None:
    text_blob = r.posting_text or f"{r.role} at {r.company}. {r.note}".strip()

    opp = Opportunity(vertical="job", title=r.title, raw_text=text_blob,
                      url=r.url, content_hash=h, status="applied",
                      captured_at=r.applied_at)
    db.add(opp)
    db.flush()

    company = db.query(Company).filter(Company.name.ilike(r.company)).one_or_none()
    if not company:
        company = Company(name=r.company)
        db.add(company)
        db.flush()

    # Extraccion solo si hay texto de verdad. Sin texto, los campos quedan
    # vacios en vez de con valores inventados a partir de una linea.
    d = {}
    if r.posting_text:
        from app.free import extractor as free_extractor
        d = free_extractor.extract(r.posting_text, title=r.title, company_hint=r.company)

    # El rango que vino en el CSV gana sobre lo que se pueda sacar del texto:
    # lo escribio una persona mirando el aviso.
    from app.free.extractor import to_usd_year
    sal = r.posted or {"currency": d.get("comp_currency"), "comp_min": d.get("comp_min"),
                       "comp_max": d.get("comp_max"), "period": d.get("comp_period")}
    cur, per = sal.get("currency"), sal.get("period")
    lo, hi = sal.get("comp_min"), sal.get("comp_max")

    db.add(JobDetail(
        opportunity_id=opp.id, company_id=company.id,
        seniority=d.get("seniority", "unknown"), remote=d.get("remote", "unknown"),
        comp_min=lo, comp_max=hi, comp_currency=cur, comp_period=per,
        comp_published=lo is not None,
        comp_usd_year_min=to_usd_year(lo, cur, per),
        comp_usd_year_max=to_usd_year(hi, cur, per),
        tech_tags=d.get("tech_tags", []), domain_tags=d.get("domain_tags", []),
        extraction={"provider": "backfill", "geo_scope": d.get("geo_scope", "unknown"),
                    "rule_flags": [], "rule_reasons": []},
    ))
    opp.lang = d.get("lang")

    # reason_code marca el origen: estas etiquetas no salieron del deck.
    db.add(Label(opportunity_id=opp.id, verdict="yes", reason_code="backfill",
                 note=r.note or None, labeled_at=r.applied_at))

    app_row = Application(opportunity_id=opp.id, applied_at=r.applied_at,
                          cv_variant=r.cv_variant, comp_asked_usd=r.comp_asked_usd,
                          channel="backfill")
    db.add(app_row)
    db.flush()

    db.add(ApplicationEvent(application_id=app_row.id, stage="applied",
                            occurred_at=r.applied_at))
    if r.stage in RESPONSE_STAGES and r.response_at:
        db.add(ApplicationEvent(application_id=app_row.id, stage=r.stage,
                                occurred_at=r.response_at, note=r.note or None))
    elif r.stage in CLOSING_STAGES:
        # Sin fecha propia: se registra en la fecha de la postulacion solo para
        # que la etapa quede visible. No cuenta como respuesta, asi que no
        # contamina ningun tiempo.
        db.add(ApplicationEvent(application_id=app_row.id, stage=r.stage,
                                occurred_at=r.response_at or r.applied_at,
                                note=r.note or None))
    db.flush()


# --------------------------------------------------------------------- metrics


# --------------------------------------------------------------------- boards

GREENHOUSE_BOARD = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"


def inspect_board(jobs: list[dict]) -> dict:
    """Cuantos puestos de un board sirven de verdad.

    Se reusan las MISMAS reglas que el pipeline —familia de puesto y candado
    geografico— asi que el numero que sale aca es el que vas a ver despues, no
    una estimacion optimista.
    """
    from app.free.extractor import geo_scope
    from app.rules.filters import TARGET_FAMILIES

    de_interes = abiertos = 0
    ejemplos: list[str] = []
    for j in jobs:
        titulo = (j.get("title") or "").strip()
        if not TARGET_FAMILIES.search(titulo):
            continue
        de_interes += 1
        ubicacion = ((j.get("location") or {}).get("name") or "").strip()
        region, _ = geo_scope("", title=titulo, location_hint=ubicacion)
        if region in ("global", "latam", "unknown"):
            abiertos += 1
            if len(ejemplos) < 3:
                ejemplos.append(f"{titulo} [{ubicacion or 'sin ubicacion'}]")
    return {"total": len(jobs), "de_interes": de_interes,
            "abiertos": abiertos, "ejemplos": ejemplos}


@cli.command()
def boards(
    tokens: list[str] = typer.Argument(..., help="Nombres de board de Greenhouse"),
    add: bool = typer.Option(False, "--add",
                             help="Agrega a greenhouse_boards los que tengan algo"),
):
    """Revisa boards de Greenhouse y dice cuales vale la pena vigilar.

    El nombre del board se saca de la URL de su pagina de empleos:
    job-boards.greenhouse.io/NOMBRE  o  boards.greenhouse.io/NOMBRE

    Para cada uno informa cuantos puestos hay, cuantos son de las familias que
    buscas, y cuantos de esos NO exigen estar en otro pais. La ultima columna es
    la que importa: una empresa con cuarenta vacantes de datos todas US-only no
    sirve para nada.
    """
    import httpx

    utiles: list[str] = []
    with httpx.Client(timeout=20, headers={"User-Agent": "job-funnel/personal"}) as client:
        for i, token in enumerate(tokens):
            if i:
                time.sleep(0.4)
            token = token.strip().strip("/").lower()
            if not token:
                continue
            try:
                r = client.get(GREENHOUSE_BOARD.format(token=token))
            except httpx.HTTPError as e:
                typer.echo(f"  {token:24} error de red: {e}")
                continue
            if r.status_code == 404:
                typer.echo(f"  {token:24} no usa Greenhouse con ese nombre")
                continue
            if r.status_code != 200:
                typer.echo(f"  {token:24} respondio {r.status_code}")
                continue
            try:
                jobs = r.json().get("jobs", [])
            except ValueError:
                typer.echo(f"  {token:24} respuesta ilegible")
                continue

            info = inspect_board(jobs)
            if info["abiertos"]:
                utiles.append(token)
            typer.echo(f"  {token:24} {info['total']:>4} puestos | "
                       f"{info['de_interes']:>3} de tu area | "
                       f"{info['abiertos']:>3} sin candado de pais")
            for e in info["ejemplos"]:
                typer.echo(f"  {'':24}      {e}")

    if not utiles:
        typer.echo("\nNinguno aporta algo. No hay nada que agregar.")
        return
    typer.echo("\nSirven: " + " ".join(utiles))

    if not add:
        typer.echo("Volve a correr con --add para sumarlos a la watchlist.")
        return

    with SessionLocal() as db:
        src = db.query(Source).filter_by(name="greenhouse_boards").one()
        actuales = list(src.config.get("boards", []))
        nuevos = [t for t in utiles if t not in actuales]
        if not nuevos:
            typer.echo("Ya estaban todos en la watchlist.")
            return
        # Se reasigna el dict entero: SQLAlchemy no detecta cambios internos de
        # un JSONB si se muta en el lugar.
        src.config = {**src.config, "boards": actuales + nuevos}
        db.commit()
        typer.echo(f"Agregados a la watchlist: {', '.join(nuevos)}")
        typer.echo(f"La watchlist ahora tiene {len(actuales) + len(nuevos)} empresas.")


@cli.command()
def metrics(name: str = "funnel"):
    with SessionLocal() as db:
        rows = db.execute(text(f"select * from v_{name}")).mappings().all()
        typer.echo(json.dumps([dict(r) for r in rows], indent=2, default=str))


@cli.command()
def sync():
    """Render the vault. Run it after any batch."""
    from app.obsidian.sync import sync as do_sync
    with SessionLocal() as db:
        typer.echo(json.dumps(do_sync(db)))


@cli.command()
def nudge():
    """Print applications past the 7-day silence window. Deterministic, no LLM."""
    with SessionLocal() as db:
        rows = db.execute(text("select * from v_needs_followup")).mappings().all()
        for r in rows:
            typer.echo(f"{r['days_since']:>3}d  {r['company']:<20} {r['title']}")


if __name__ == "__main__":
    cli()
