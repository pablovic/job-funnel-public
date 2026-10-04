"""Deterministic gate. Runs before any model call.

Two jobs. It cuts token spend by rejecting the obvious, and — more importantly —
it makes the filtering rules auditable. Every rule here was derived from a real
decision in the labeled set, and each one names why it exists. A rule that lives
in a prompt cannot be tested; a rule that lives here can.

Nothing in this module calls an LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

# Demo list: these agencies are fictional. In a real instance, list the staffing
# agencies and body shops you've learned to skip.
STAFFING = {
    "talentbridge staffing", "nearshore squad", "codeforce partners",
    "staffwise", "devhire collective",
}

ONSITE_MARKERS = re.compile(
    r"\b(on[- ]?site|presencial|híbrido|hybrid|"
    r"\d\s*(days?|dias?)\s*(a|per|por)\s*(week|semana))\b", re.I)

# Familias de puesto que interesan. Se busca SOLO en el titulo (sin el
# " — empresa" del final), porque el titulo es el dato mas confiable.
# Los boards de empresas publican todo junto: una empresa de comida publica
# lavaplatos, y una de datos publica vendedores. Sin esta regla, esos puestos
# solo se caian si pagaban poco, que es un accidente, no un criterio.
# EDITAR ESTA LISTA ES LA FORMA DE AMPLIAR O ACHICAR LA BUSQUEDA.
TARGET_FAMILIES = re.compile(
    r"\b(data|datos|dados|analyst|analytics|analytic|analista|an[áa]lise|"
    r"bi|business intelligence|insights?|scientist|science|cientista|cient[íi]fico|"
    r"machine learning|ml|ai|growth|product|experimentation|statistic\w*|quant\w*|etl)\b",
    re.I)

REMOTE_MARKERS = re.compile(
    r"\b(fully remote|100% remote|remote[- ]first|remoto|trabalho remoto|"
    r"work from anywhere|anywhere)\b", re.I)


# Dos formas de detectar un aviso sin descripcion, a proposito.
#
# La marca es el camino exacto: los adaptadores que saben que la fuente no
# entrega descripcion la escriben en el texto (ver app/ingest/jobgether.py).
# Hay un test que ata las dos puntas, asi que si alguien cambia esa frase en el
# adaptador, falla ruidosamente en vez de dejar de marcar en silencio.
#
# El largo es la red de seguridad: agarra cualquier fuente futura que no sepa
# avisar, y tambien las filas cargadas con `funnel backfill` sin el texto.
NO_DESCRIPTION_MARKER = "carries no description"
MIN_DESCRIPTION_CHARS = 400


class Decision(str, Enum):
    PASS = "pass"
    FLAG = "flag"          # continues to scoring, but the reason is surfaced
    REJECT = "reject"      # never reaches an LLM, never reaches the triage deck


@dataclass
class RuleResult:
    decision: Decision
    reasons: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)


@dataclass
class Candidate:
    """The minimum an opportunity needs to be judged. Deliberately not the ORM
    model, so rules stay unit-testable without a database."""
    title: str
    text: str
    company: str = ""
    remote: str = "unknown"
    comp_published: bool = False
    comp_usd_year_min: float | None = None
    comp_usd_year_max: float | None = None
    lang: str = "en"
    geo_scope: str = "unknown"
    geo_quote: str = ""


def evaluate(c: Candidate, *, comp_floor_usd: int = 85_000,
             require_remote: bool = True, languages: tuple[str, ...] = ("en", "es", "pt"),
             target_families: re.Pattern | None = TARGET_FAMILIES,
             eligible_regions: tuple[str, ...] = ("global", "latam")) -> RuleResult:
    reasons: list[str] = []
    flags: list[str] = []

    # 0. Familia de puesto. Un lavaplatos no se descarta porque paga poco,
    #    se descarta porque no es el trabajo que se busca.
    if target_families is not None:
        role = c.title.split(" — ")[0]
        if not target_families.search(role):
            reasons.append(f"role family out of scope: {role.strip()}")

    # 1. Channel. ~29% of the Sep 2026 saved set was staffing and body shops,
    #    with near-zero conversion. This is the single highest-yield filter.
    if c.company.strip().lower() in STAFFING:
        reasons.append(f"staffing channel: {c.company}")

    # 2. Remote is a hard requirement for this candidate.
    if require_remote:
        if c.remote in ("onsite", "hybrid"):
            reasons.append(f"remote policy is {c.remote}")
        elif c.remote == "unknown" and ONSITE_MARKERS.search(c.text) and not REMOTE_MARKERS.search(c.text):
            reasons.append("posting describes on-site or hybrid attendance")

    # 2b. Elegibilidad geografica. "Remote" no quiere decir "remoto desde donde
    #     vos estas": una parte enorme de los avisos remotos son "US Remote", y
    #     piden estar en Estados Unidos. Es una restriccion dura, igual que lo
    #     presencial, y hasta ahora no se estaba mirando.
    #
    #     'unknown' NUNCA rechaza: mismo criterio que con el sueldo, el silencio
    #     no es evidencia. Solo rechaza un candado explicito a otra region.
    if c.geo_scope not in eligible_regions and c.geo_scope != "unknown":
        detalle = f": “{c.geo_quote}”" if c.geo_quote else ""
        reasons.append(f"hiring is restricted to {c.geo_scope.upper()}{detalle}")

    # 3. Compensation. Reject only on a *published* number below the floor.
    #
    #    This asymmetry is the whole point. In the labeled set, all ten "no"
    #    verdicts cited overqualification and not one of them published a range —
    #    the filter was firing on HR disclosure policy, which most companies in
    #    Brazil and LatAm do not have. Silence about pay is not evidence about pay.
    if c.comp_published and c.comp_usd_year_max is not None and c.comp_usd_year_max < comp_floor_usd:
        reasons.append(f"published ceiling ${c.comp_usd_year_max:,.0f} is below the ${comp_floor_usd:,} floor")
    if not c.comp_published:
        flags.append("no published range — ask in the first screening call")

    # 3b. Avisos sin descripcion. Jobgether devuelve metadatos pero no el texto
    #     del puesto, y `craft` y `domain` —el 56% del puntaje— salen de buscar
    #     palabras en ese texto. Sin texto quedan artificialmente bajos.
    #
    #     Es una BANDERA, no un rechazo: el aviso puede ser excelente, solo que
    #     el puntaje no lo sabe. La pantalla lo dice en vez de fingir precision.
    if NO_DESCRIPTION_MARKER in c.text or len(c.text.strip()) < MIN_DESCRIPTION_CHARS:
        flags.append("no description in the listing — the score is partial, open the posting")

    # 4. Language.
    if c.lang not in languages:
        reasons.append(f"language {c.lang} not in {','.join(languages)}")

    # 5. Seniority is deliberately NOT a filter. A mid-level title paying USD
    #    beats a manager title paying BRL, and that trade is the strategy. Level
    #    is a scoring dimension, not a gate.

    if reasons:
        return RuleResult(Decision.REJECT, reasons, flags)
    if flags:
        return RuleResult(Decision.FLAG, [], flags)
    return RuleResult(Decision.PASS)
