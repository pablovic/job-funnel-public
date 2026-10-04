"""Extraction with no model. Regex, keyword lists and source metadata.

The insight that makes this viable: the automated sources already hand over
structured data. Greenhouse and Remotive JSON include company, title, salary text
and location as fields — there is nothing to "extract". Only the paste path needs
parsing, and for that, regex covers comp, remote policy, seniority and tech tags
well enough to sort a list.

Free, instant, deterministic, unit-testable. No API key, no rate limit, no bill.
"""
from __future__ import annotations

import re

TECH = {
    "sql": r"\bsql\b", "python": r"\bpython\b", "r": r"\bR\b(?!\w)",
    "dbt": r"\bdbt\b", "airflow": r"\bairflow\b", "spark": r"\bspark\b",
    "snowflake": r"\bsnowflake\b", "bigquery": r"\bbig\s?query\b",
    "databricks": r"\bdatabricks\b", "redshift": r"\bredshift\b",
    "looker": r"\blooker\b", "tableau": r"\btableau\b", "powerbi": r"\bpower\s?bi\b",
    "amplitude": r"\bamplitude\b", "mixpanel": r"\bmixpanel\b",
    "segment": r"\bsegment\b", "ga4": r"\bga4|google analytics\b",
    "ab_testing": r"\ba/?b test|experiment|incrementality|causal\b",
    "statistics": r"\bstatistic|regression|econometric|bayesian\b",
}

DOMAIN = {
    "marketplace": r"\bmarketplace|two[- ]sided|supply and demand\b",
    "fintech": r"\bfintech|payments?|lending|credit\b",
    "ecommerce": r"\be[- ]?commerce|retail|merchant\b",
    "saas": r"\bb2b|saas\b",
    "growth": r"\bgrowth|acquisition|retention|churn|funnel\b",
    "logistics": r"\blogistics|delivery|fleet\b",
}

SENIORITY = [
    ("head", r"\bhead of|director\b"),
    ("manager", r"\bmanager|gerente\b"),
    ("lead", r"\blead|líder|principal\b"),
    ("staff", r"\bstaff\b"),
    ("senior", r"\bsenior|sr\.?|sênior|pleno/?s[êe]nior\b"),
    ("junior", r"\bjunior|jr\.?|entry[- ]level|intern\b"),
    ("mid", r"\bmid[- ]level|pleno\b"),
]

REMOTE_GLOBAL = r"\bwork from anywhere|remote[- ](?:global|worldwide|anywhere)|anywhere in the world\b"
REMOTE_ANY = r"\bfully remote|100% remote|remote[- ]first|remoto|trabalho remoto|home ?office\b"
HYBRID = r"\bhybrid|híbrido|h[íi]brido\b"
ONSITE = r"\bon[- ]?site|presencial|in[- ]office|\d\s*(?:days?|dias?)\s*(?:a|per|por)\s*(?:week|semana)\b"

# ----------------------------------------------------------------- geografia
#
# "Remote" y "remote DESDE DONDE" son dos preguntas distintas, y la segunda es
# la que decide si se puede postular. Una enorme parte de los avisos remotos
# dicen "US Remote": remoto, si, pero hay que estar en Estados Unidos.
#
# Lo dificil es separar la restriccion de la mencion. Estas dos frases aparecen
# en el MISMO aviso:
#   "This role may be performed fully remotely within the United States."  <- candado
#   "Please note that our US headquarters are located in NYC."             <- solo un dato
# Por eso no alcanza con buscar el nombre del pais: hace falta una frase de
# restriccion inmediatamente ANTES del pais, que es como se construye la
# restriccion en ingles ("located in X", "must reside in X", "within X").

# "US" solo en MAYUSCULAS: en minuscula es el pronombre ingles ("join us") y
# aparecería en practicamente todos los avisos.
COUNTRY_PATTERNS = [
    ("us",          r"(?i:united states)|U\.S\.A?\.?|(?<![A-Za-z])USA?(?![A-Za-z])"),
    ("canada",      r"(?i:canada|canadian)"),
    ("uk",          r"(?i:united kingdom|great britain)|(?<![A-Za-z])UK(?![A-Za-z])"),
    ("eu",          r"(?i:european union)|(?<![A-Za-z])(?:EEA|EU)(?![A-Za-z])"),
    ("india",       r"(?i:india(?!n ocean))"),
    ("australia",   r"(?i:australia)"),
    ("germany",     r"(?i:germany|deutschland)"),
    ("poland",      r"(?i:poland)"),
    ("philippines", r"(?i:philippines)"),
    ("spain",       r"(?i:spain|espa[nñ]a)"),
    ("france",      r"(?i:france)"),
    ("portugal",    r"(?i:portugal)"),
    ("netherlands", r"(?i:netherlands|holland)"),
    ("ireland",     r"(?i:ireland)"),
    ("italy",       r"(?i:italy|italia)"),
    ("mexico",      r"(?i:m[eé]xico|mexico)"),
    ("colombia",    r"(?i:colombia)"),
    ("chile",       r"(?i:chile)"),
]

# Termina en $ porque solo cuenta si esta pegada al pais, no en cualquier lado.
RESTRICTION = re.compile(r"""(?ix)
  (?: must\s+(?:be|reside|live|work|have)
    | only
    | exclusively
    | based\s+(?:in|out\s+of)
    | located\s+(?:in|within)
    | resid(?:e|ing)\s+(?:in|within)
    | living\s+in
    | remote(?:ly)?\s+(?:with)?in
    | within
    | authori[sz]ed\s+to\s+work
    | eligible\s+to\s+work
    | work\s+authori[sz]ation
    | legally\s+authori[sz]ed
    | citizens?
    | residents?\s+of
    | permanent\s+residents?
    | hiring\s+(?:in|only)
    | candidates?\s+(?:must|located|based|in)
    | open\s+to\s+candidates
    | employment\s+in
    | anywhere\s+in
  )\s*(?:the\s+)?[\w\s,]{0,12}$
""")

# "US-only", "USA Only", "US Remote" — aca el pais va primero.
SUFFIX_LOCK = re.compile(r"^[\s\-–—,()]*(?i:only|based|residents?|remote)\b")
# "Remote (US)", "Remote - USA"
PREFIX_REMOTE = re.compile(r"(?i:remote)[\s\-–—,()]{0,4}$")

# Campo de ubicacion de la fuente: es una declaracion, no prosa, asi que alcanza
# con la palabra suelta.
OPEN_HINT = re.compile(r"(?i:worldwide|anywhere|global)")
# En prosa hace falta ser estricto: "customers worldwide" no es una politica.
OPEN_TEXT = re.compile(
    r"(?i:work from anywhere|anywhere in the world|fully distributed|"
    r"globally distributed|hire (?:from )?anywhere|remote[- ](?:global|worldwide|anywhere))")
LATAM = re.compile(
    r"(?i:lat(?:in\s+)?am(?:erica)?|south america|brazil|brasil|argentina|americas)")


def _first_lock(blob: str, *, structured: bool = False) -> tuple[str, str] | None:
    """Region bloqueada y la frase que lo dice, o None.

    `structured=True` es para el campo de ubicacion de la fuente. Ahi el nombre
    de un pais YA ES la restriccion —"United States", "Spain, France"— y no hace
    falta buscar una frase alrededor, porque no hay prosa: es una declaracion de
    donde hay que estar. En el cuerpo del aviso, en cambio, mencionar un pais no
    restringe nada ("nuestra oficina queda en NYC"), y por eso ahi si se exige
    una frase de restriccion pegada al pais.
    """
    for region, pat in COUNTRY_PATTERNS:
        for m in re.finditer(pat, blob):
            if structured:
                return region, " ".join(blob.split())
            before = blob[max(0, m.start() - 48):m.start()]
            after = blob[m.end():m.end() + 24]
            if RESTRICTION.search(before) or SUFFIX_LOCK.match(after) or PREFIX_REMOTE.search(before):
                quote = blob[max(0, m.start() - 45):m.end() + 20]
                return region, " ".join(quote.split())
    return None


def geo_scope(text: str, title: str = "", location_hint: str = "") -> tuple[str, str]:
    """Desde donde se puede trabajar. Devuelve (region, cita).

    'global'  : contrata desde cualquier lado
    'latam'   : menciona LatAm / Brasil / Argentina explicitamente
    '<pais>'  : hay que estar en ese pais
    'unknown' : el aviso no lo dice — NO es motivo de rechazo
    """
    hint = location_hint or ""
    if hint:
        if OPEN_HINT.search(hint):
            return "global", hint.strip()
        if LATAM.search(hint):
            return "latam", hint.strip()
        lock = _first_lock(hint, structured=True)
        if lock:
            return lock

    blob = f"{title}\n{text}"
    lock = _first_lock(blob)
    if lock:
        return lock
    if OPEN_TEXT.search(blob):
        return "global", ""
    if LATAM.search(blob):
        return "latam", ""
    return "unknown", ""


# Salary. Handles "$90,000 - $120,000", "$150,000—$180,000 USD", "USD 90k-120k",
# "R$ 20.000/mês", "$18.50/hr".
MONEY = re.compile(
    r"(?P<cur>US\$|USD|R\$|BRL|\$|€|EUR)\s?(?P<a>\d[\d.,]*)\s?(?P<ka>k|mil)?"
    r"(?:\s*(?:-|–|—|to|a|até)\s*(?:US\$|USD|R\$|BRL|\$|€|EUR)?\s?(?P<b>\d[\d.,]*)\s?(?P<kb>k|mil)?)?",
    re.I)

# El periodo se busca SOLO pegado al monto (misma frase), nunca en todo el aviso.
# Antes, un "monthly team offsites" en cualquier parte del texto convertia un
# sueldo anual en mensual y lo multiplicaba por 12.
HOUR = re.compile(r"/\s*h(?:ou)?r\b|per hour|an hour|hourly|/\s*hora|por hora", re.I)
MONTH = re.compile(r"/\s*mo(?:nth)?\b|per month|a month|monthly|/\s*m[êe]s|mensal|por m[êe]s|al mes|mensual", re.I)
YEAR = re.compile(r"/\s*y(?:ea)?r\b|per year|a year|annual|annually|yearly|per annum|/\s*ano\b|anual|al año|por año", re.I)

# Un monto es sueldo solo si hay contexto de sueldo cerca. Los avisos mencionan
# muchos otros montos: stipends, 401(k), presupuestos de formacion, etc.
SALARY_CTX = re.compile(
    r"\b(salary|salaries|compensation|base pay|pay range|pay rate|pay band|base|"
    r"range|OTE|on[- ]target|wage|hourly rate|remunera\w*|sal[áa]rio|sueldo|"
    r"faixa salarial|rango salarial)\b", re.I)
BENEFIT_CTX = re.compile(
    r"(stipend|allowance|reimburs|401\s?\(?k|retirement|matching|match up|wellness|"
    r"wellbeing|well-being|learning|education|tuition|home[- ]office|equipment|budget|"
    r"perk|gym|meal|commuter|phone|internet|coworking|referral|relocation|sign(?:ing|-on)|"
    r"per diem|discount|credit|gift|childcare|fertility|donation|charit)", re.I)

FX_USD = {"USD": 1.0, "BRL": 1 / 5.4, "ARS": 1 / 1400, "EUR": 1.08}
CUR_MAP = {"us$": "USD", "usd": "USD", "$": "USD", "r$": "BRL", "brl": "BRL", "€": "EUR", "eur": "EUR"}


def _num(raw: str, k: str | None) -> float | None:
    """90,000 / 90.000 / 90k / 20.000 / 19.50 / 18.00

    Regla: si despues del ultimo separador hay 1 o 2 digitos, son centavos
    ("19.50" = 19,5). Si hay 3, son miles ("20.000" = 20000). Antes "19.50"
    se leia como 1950.
    """
    if not raw:
        return None
    raw = raw.strip(".,")
    if not raw:
        return None
    m = re.fullmatch(r"(\d[\d.,]*?)[.,](\d{1,2})", raw)
    try:
        if m:
            v = float(re.sub(r"[.,]", "", m.group(1)) + "." + m.group(2))
        else:
            v = float(re.sub(r"[.,]", "", raw))
    except ValueError:
        return None
    if k:
        v *= 1000
    return v


def _clause_before(pre: str) -> str:
    """La parte de la frase que termina justo antes del monto."""
    cut = max(pre.rfind("\n"), *(pre.rfind(p) for p in (". ", "! ", "? ")))
    return pre[cut + 1:] if cut >= 0 else pre


def _clause_after(post: str) -> str:
    """La parte de la frase que empieza justo despues del monto."""
    m = re.search(r"\n|[.!?](?:\s|$)", post)
    return post[:m.start()] if m else post


def _period_near(after: str, before: str) -> str | None:
    for window in (after, before):
        for name, rx in (("hour", HOUR), ("month", MONTH), ("year", YEAR)):
            if rx.search(window):
                return name
    return None


def _guess_period(value: float, currency: str | None) -> str:
    """Sin periodo explicito, se infiere por el tamano del numero."""
    if value <= 300:
        return "hour"
    monthly_ceiling = 60_000 if currency == "BRL" else 15_000
    return "month" if value < monthly_ceiling else "year"


def _parse_money(m: re.Match, before: str, after: str) -> dict:
    currency = CUR_MAP.get((m.group("cur") or "").lower())
    comp_min = _num(m.group("a"), m.group("ka"))
    comp_max = _num(m.group("b"), m.group("kb")) or comp_min
    period = _period_near(after, before)
    if period is None and comp_max is not None:
        period = _guess_period(comp_max, currency)
    return {"currency": currency, "comp_min": comp_min, "comp_max": comp_max,
            "period": period, "is_range": m.group("b") is not None}


def find_salary(text: str, salary_hint: str = "") -> dict | None:
    """Devuelve el sueldo publicado, o None si no hay uno confiable.

    salary_hint viene de un campo estructurado de la fuente: se confia en el.
    En el texto libre, un monto cuenta como sueldo solo si:
      - no esta en una frase de beneficios (stipend, 401k, presupuesto...), y
      - tiene contexto de sueldo cerca, o es un rango anual plausible.
    Ante la duda devuelve None: "no publicado" solo genera una bandera,
    mientras que un numero equivocado puede rechazar una vacante buena.
    """
    if salary_hint:
        m = MONEY.search(salary_hint)
        if m:
            return _parse_money(m, salary_hint[:m.start()], salary_hint[m.end():])

    fallback = None
    for m in MONEY.finditer(text):
        pre = text[max(0, m.start() - 120):m.start()]
        post = text[m.end():m.end() + 80]
        before, after = _clause_before(pre), _clause_after(post)
        if BENEFIT_CTX.search(before[-60:]) or BENEFIT_CTX.search(after[:40]):
            continue
        parsed = _parse_money(m, before, after)
        if parsed["comp_max"] is None:
            continue
        if SALARY_CTX.search(pre) or SALARY_CTX.search(after):
            return parsed
        yearly = to_usd_year(parsed["comp_max"], parsed["currency"], parsed["period"]) or 0
        if fallback is None and parsed["is_range"] and yearly >= 20_000:
            fallback = parsed
    return fallback


def detect_lang(text: str) -> str:
    t = text.lower()
    pt = sum(w in t for w in (" você ", " nossa ", " vaga ", " atuar ", " conhecimento ", "não"))
    es = sum(w in t for w in (" nuestro ", " puesto ", " conocimiento ", " deberás ", " años "))
    if pt >= 2 and pt > es:
        return "pt"
    if es >= 2:
        return "es"
    return "en"


def extract(text: str, title: str = "", company_hint: str = "",
            salary_hint: str = "", location_hint: str = "") -> dict:
    """Everything the rules gate and the keyword scorer need. `*_hint` fields come
    from source JSON (Greenhouse, Remotive) and always win over regex."""
    blob = f"{title}\n{salary_hint}\n{location_hint}\n{text}"
    low = blob.lower()

    seniority = "unknown"
    for name, pat in SENIORITY:
        if re.search(pat, f"{title} {text[:400]}", re.I):
            seniority = name
            break

    if re.search(HYBRID, low):
        remote = "hybrid"
    elif re.search(ONSITE, low) and not re.search(REMOTE_ANY, low):
        remote = "onsite"
    elif re.search(REMOTE_GLOBAL, low):
        remote = "remote_global"
    elif re.search(REMOTE_ANY, low) or "remote" in (location_hint or "").lower():
        remote = "remote_country"
    else:
        remote = "unknown"

    geo, geo_quote = geo_scope(text, title=title, location_hint=location_hint)

    sal = find_salary(text, salary_hint)
    comp_min = sal["comp_min"] if sal else None
    comp_max = sal["comp_max"] if sal else None
    currency = sal["currency"] if sal else None
    period = sal["period"] if sal else None
    published = comp_min is not None

    return {
        "company": company_hint or "",
        "seniority": seniority,
        "remote": remote,
        "lang": detect_lang(text),
        "comp_published": published,
        "comp_min": comp_min, "comp_max": comp_max,
        "comp_currency": currency, "comp_period": period,
        "comp_usd_year_min": to_usd_year(comp_min, currency, period),
        "comp_usd_year_max": to_usd_year(comp_max, currency, period),
        "tech_tags": sorted(k for k, p in TECH.items() if re.search(p, blob, re.I)),
        "domain_tags": sorted(k for k, p in DOMAIN.items() if re.search(p, blob, re.I)),
        "asks_instrumentation": bool(re.search(
            r"\b(event (schema|tracking)|instrument\w*|tracking plan|taxonomy)\b", low)),
        "asks_dbt": bool(re.search(r"\bdbt\b", low)),
        "geo_scope": geo,
        "geo_quote": geo_quote,
    }


def to_usd_year(amount: float | None, currency: str | None, period: str | None) -> float | None:
    if amount is None or not currency:
        return None
    per_year = {"year": 1, "month": 12, "hour": 2080}.get(period or "year", 1)
    return round(amount * FX_USD.get(currency, 1.0) * per_year)
