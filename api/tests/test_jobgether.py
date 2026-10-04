"""Tests de la fuente Jobgether.

Construidos contra la respuesta de ejemplo de la documentacion oficial. No se
pudo golpear el endpoint en vivo al escribirlos, asi que el adaptador es
deliberadamente tolerante: todo sale con .get() y un campo que falte o cambie de
nombre degrada el resultado en vez de romperlo.
"""
import pytest

from app.free.extractor import extract, geo_scope
from app.ingest.jobgether import (
    JobgetherConfigError, MAX_LIMIT, _params, normalize_salary, parse_job,
)
from app.rules.filters import Candidate, Decision, evaluate

# Copiado literal de la seccion Response de la documentacion.
DOC_JOB = {
    "id": "65f1a2b3c4d5e6f7a8b9c0d1",
    "title": "Senior Frontend Developer",
    "company": "Acme Inc.",
    "url": "https://www.jobgether.com/offer/senior-frontend-developer-acme-inc",
    "location": "Spain, France",
    "remote": "Full Remote",
    "contractType": "Full time",
    "experience": "Senior (5-10 years)",
    "salaryRange": "60000-80000 EUR",
    "jobFunctions": ["Frontend Developer"],
    "postedAt": "2026-07-01T00:00:00.000Z",
}


# --- sueldo: la moneda viene al final ---------------------------------------

def test_trailing_currency_range_is_rewritten():
    """'60000-80000 EUR' con la moneda atras. El extractor la espera adelante:
    sin esto, ningun sueldo de esta fuente se lee."""
    assert normalize_salary("60000-80000 EUR") == "EUR 60000 - EUR 80000 per year"


def test_trailing_currency_single_value():
    assert normalize_salary("90000 USD") == "USD 90000 per year"


def test_leading_currency_is_left_alone():
    assert normalize_salary("$90,000 - $120,000 per year") == "$90,000 - $120,000 per year"


def test_empty_salary_stays_empty():
    assert normalize_salary("") == ""
    assert normalize_salary(None) == ""


def test_the_salary_actually_reaches_the_extractor():
    p = parse_job(DOC_JOB)
    e = extract(p.raw_text, title=p.title, salary_hint=p.salary, location_hint=p.location)
    assert e["comp_published"] is True
    assert e["comp_currency"] == "EUR"
    assert e["comp_period"] == "year"
    assert e["comp_usd_year_max"] == round(80_000 * 1.08)


# --- forma del RawPosting ----------------------------------------------------

def test_title_uses_the_em_dash_separator():
    assert parse_job(DOC_JOB).title == "Senior Frontend Developer — Acme Inc."


def test_canonical_url_is_kept():
    p = parse_job(DOC_JOB)
    assert p.url == DOC_JOB["url"]


def test_experience_reaches_the_seniority_reader():
    p = parse_job(DOC_JOB)
    assert extract(p.raw_text, title=p.title)["seniority"] == "senior"


def test_the_missing_description_is_announced_in_the_text():
    assert "no description" in parse_job(DOC_JOB).raw_text.lower()


def test_a_job_with_almost_no_fields_still_parses():
    p = parse_job({"title": "Data Analyst"})
    assert p.title == "Data Analyst"
    assert p.raw_text


# --- geografia ---------------------------------------------------------------

def test_a_country_in_the_location_field_is_a_lock_on_its_own():
    """En el campo de ubicacion no hay prosa: nombrar un pais ES la restriccion.
    En el cuerpo del aviso hace falta una frase de restriccion alrededor."""
    p = parse_job(DOC_JOB)
    assert geo_scope("", location_hint=p.location)[0] == "spain"


def test_anywhere_is_global():
    p = parse_job({**DOC_JOB, "location": "Anywhere"})
    assert geo_scope("", location_hint=p.location)[0] == "global"


def test_latam_wins_over_another_country_in_the_same_field():
    p = parse_job({**DOC_JOB, "location": "Brazil, Spain"})
    assert geo_scope("", location_hint=p.location)[0] == "latam"


def test_a_us_only_listing_is_rejected():
    p = parse_job({**DOC_JOB, "location": "United States"})
    geo, quote = geo_scope("", location_hint=p.location)
    r = evaluate(Candidate(title=p.title, text=p.raw_text, remote="remote_country",
                           geo_scope=geo, geo_quote=quote))
    assert r.decision == Decision.REJECT
    assert any("restricted to US" in x for x in r.reasons)


def test_a_us_office_mentioned_in_prose_is_still_not_a_lock():
    """La regla estructurada no debe contagiar al texto libre."""
    assert geo_scope("Our US headquarters are located in NYC.")[0] == "unknown"


# --- la bandera de aviso flaco ----------------------------------------------

def test_a_listing_with_no_description_is_flagged_not_rejected():
    """Con un puesto que SI es de los que busca: asi el unico motivo posible de
    rechazo seria la falta de descripcion, y no debe serlo."""
    p = parse_job({**DOC_JOB, "title": "Senior Data Analyst",
                   "jobFunctions": ["Data Analyst"], "location": "Anywhere"})
    r = evaluate(Candidate(title=p.title, text=p.raw_text, remote="remote_country",
                           geo_scope="global"))
    assert r.decision != Decision.REJECT, r.reasons
    assert any("no description" in f for f in r.flags)


def test_an_out_of_scope_role_is_still_rejected_even_from_this_source():
    """El ejemplo de la documentacion es un frontend developer: la bandera de
    aviso flaco no debe salvar a un puesto que no es de los que busca."""
    p = parse_job(DOC_JOB)
    r = evaluate(Candidate(title=p.title, text=p.raw_text, remote="remote_country",
                           geo_scope="global"))
    assert r.decision == Decision.REJECT
    assert any("role family" in x for x in r.reasons)


def test_a_real_posting_is_not_flagged():
    long_text = ("We are looking for a senior data analyst. " * 20)
    r = evaluate(Candidate(title="Senior Data Analyst — Acme", text=long_text,
                           remote="remote_global", geo_scope="global"))
    assert not any("no description" in f for f in r.flags)


# --- parametros --------------------------------------------------------------

def test_arrays_are_sent_comma_separated():
    p = _params({"locations": ["spain", "france"], "keyword": "data"}, page=1)
    assert p["locations"] == "spain,france"
    assert p["keyword"] == "data"


def test_a_plain_string_array_param_passes_through():
    assert _params({"locations": "anywhere"}, page=1)["locations"] == "anywhere"


def test_limit_is_capped_at_the_server_maximum():
    assert _params({"limit": 500}, page=1)["limit"] == MAX_LIMIT


def test_empty_values_are_not_sent():
    p = _params({"keyword": "", "sort": None, "industries": []}, page=2)
    assert "keyword" not in p and "sort" not in p and "industries" not in p
    assert p["page"] == 2


def test_config_error_is_loud_by_design():
    """Una fuente mal configurada que devuelve vacio parece una fuente sin
    resultados, y eso se descubre semanas despues."""
    assert issubclass(JobgetherConfigError, RuntimeError)
    with pytest.raises(JobgetherConfigError):
        raise JobgetherConfigError("x")


def test_the_adapter_emits_the_exact_marker_the_filter_looks_for():
    """Ata las dos puntas del acoplamiento. Si alguien cambia la frase en el
    adaptador, esto falla en vez de que la bandera deje de aparecer en silencio."""
    from app.rules.filters import NO_DESCRIPTION_MARKER
    assert NO_DESCRIPTION_MARKER in parse_job(DOC_JOB).raw_text


def test_a_long_jobgether_listing_is_still_flagged():
    """Un aviso con muchas funciones puede pasar el umbral de largo. La marca lo
    agarra igual: la deteccion no depende de contar caracteres."""
    from app.rules.filters import MIN_DESCRIPTION_CHARS, Candidate, Decision, evaluate
    fat = parse_job({**DOC_JOB, "title": "Senior Data Analyst",
                     "location": "Anywhere",
                     "jobFunctions": [f"Data Function Number {i}" for i in range(40)]})
    assert len(fat.raw_text) > MIN_DESCRIPTION_CHARS
    r = evaluate(Candidate(title=fat.title, text=fat.raw_text,
                           remote="remote_country", geo_scope="global"))
    assert r.decision is not Decision.REJECT
    assert any("no description" in f for f in r.flags)
