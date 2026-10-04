"""Tests de regresion del primer pull real (211 vacantes de Greenhouse).

Cada test corresponde a un bug que se vio en datos reales. Si alguno vuelve a
fallar, el bug volvio.
"""
from app.free.extractor import extract
from app.rules.filters import Candidate, Decision, evaluate


# --- Sueldos ----------------------------------------------------------------

def test_monthly_word_elsewhere_does_not_multiply_annual_salary():
    """Bug real: $130,000 anuales guardado como $1,560,000 porque el aviso
    decia 'monthly' en otra frase."""
    text = ("We host monthly team offsites. "
            "The annual base salary range for this role is $130,000 - $160,000.")
    e = extract(text, title="AI Native Engineer")
    assert e["comp_usd_year_max"] == 160_000


def test_benefit_stipend_is_not_a_salary():
    """Bug real: 45 vacantes de veridata rechazadas por un beneficio de $475/mes."""
    text = ("Fully remote. We offer a $475 monthly stipend for wellness and home office. "
            "Great team.")
    e = extract(text, title="AI Product Manager")
    assert e["comp_published"] is False


def test_stipend_before_real_salary_picks_the_salary():
    text = ("Perks include a $475 monthly wellness stipend. "
            "The salary range for this position is $140,000 - $170,000 per year.")
    e = extract(text, title="AI Product Manager")
    assert e["comp_usd_year_max"] == 170_000


def test_hourly_wage_with_cents_is_read_as_hourly():
    """Bug real: '$19.50' leido como 1950 mensuales."""
    text = "Pay rate: $19.50 per hour."
    e = extract(text, title="Cooling Specialist")
    assert e["comp_max"] == 19.5
    assert e["comp_period"] == "hour"
    assert e["comp_usd_year_max"] == round(19.5 * 2080)


def test_hourly_without_explicit_period_is_inferred():
    """Bug real: '$18' leido como mensual, dando $216 al año."""
    text = "Compensation: $18 - $22 depending on experience."
    e = extract(text, title="Dishwasher")
    assert e["comp_period"] == "hour"


def test_em_dash_range_from_greenhouse_pay_block():
    """Greenhouse usa raya larga (—) en sus bloques de 'Pay Range'."""
    text = "Pay Range\n$150,000—$180,000 USD\n\nAbout us..."
    e = extract(text, title="Senior Data Analyst")
    assert e["comp_usd_year_max"] == 180_000


def test_brazilian_thousands_separator_still_works():
    e = extract("Vaga remota.", salary_hint="R$ 20.000 / mês")
    assert e["comp_max"] == 20_000
    assert e["comp_period"] == "month"


def test_lone_dollar_amount_without_context_is_ignored():
    """Ante la duda, 'no publicado': solo genera una bandera, no un rechazo."""
    text = "We raised $40 million last year and serve 500 clients."
    e = extract(text, title="Data Analyst")
    assert e["comp_published"] is False


# --- Familia de puesto --------------------------------------------------------

def _cand(title):
    return Candidate(title=title, text="Fully remote role.", remote="remote_global")


def test_kitchen_role_is_rejected_by_family_not_by_pay():
    r = evaluate(_cand("Dishwasher — driftwoodfoods"))
    assert r.decision == Decision.REJECT
    assert any("role family" in x for x in r.reasons)


def test_data_role_passes_family_rule():
    r = evaluate(_cand("Senior Data Analyst, Growth Analytics (CRM) — driftwoodfoods"))
    assert not any("role family" in x for x in r.reasons)


def test_company_name_does_not_rescue_an_out_of_scope_role():
    """'veridata' contiene 'data', pero es la empresa, no el puesto."""
    r = evaluate(_cand("Account Executive — veridata"))
    assert any("role family" in x for x in r.reasons)
