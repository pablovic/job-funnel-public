"""The free path has no model in it, so all of it is testable for nothing."""
from app.free.extractor import extract, to_usd_year
from app.free.scorer import score


def test_extracts_usd_range_from_salary_hint():
    e = extract("Remote analytics role.", salary_hint="$90,000 - $120,000 per year")
    assert e["comp_published"] is True
    assert e["comp_usd_year_max"] == 120_000


def test_brl_monthly_is_normalized_and_falls_below_floor():
    e = extract("Vaga remota.", salary_hint="R$ 20.000 / mês")
    assert e["comp_currency"] == "BRL"
    assert e["comp_usd_year_max"] < 85_000


def test_hybrid_beats_the_word_remote():
    e = extract("Fully remote role, hybrid 2 days a week in the office.")
    assert e["remote"] == "hybrid"


def test_tech_and_domain_tags_are_found():
    e = extract("You will run A/B tests on our two-sided marketplace using SQL and Python.")
    assert {"sql", "python", "ab_testing"} <= set(e["tech_tags"])
    assert "marketplace" in e["domain_tags"]


def test_portuguese_detected():
    e = extract("Você vai atuar com nossa equipe de dados, não é necessário conhecimento prévio.")
    assert e["lang"] == "pt"


def test_marketplace_experimentation_role_scores_high():
    text = "Senior Product Analyst. Run A/B tests and incrementality studies on our marketplace using SQL and Python."
    s = score(extract(text, title="Senior Product Analyst"), text, company_kind="product")
    assert s["fit"] >= 70
    assert s["recommended_cv"] == "ic"


def test_manager_role_recommends_lead_cv():
    text = "Head of Analytics. Lead a team across our fintech platform."
    s = score(extract(text, title="Head of Analytics"), text)
    assert s["recommended_cv"] == "lead"


def test_unpublished_pay_scores_five_not_zero():
    s = score(extract("Competitive salary. SQL and Python."), "SQL and Python.")
    assert s["dimensions"]["comp"] == 5.0


def test_dbt_produces_a_grounded_gap_quote():
    text = "You will build models in dbt. Strong SQL required."
    s = score(extract(text), text)
    gap = next(g for g in s["gaps"] if "dbt" in g["requirement"])
    assert gap["quote"] in text or gap["quote"] in " ".join(text.split())


def test_lead_in_an_ic_title_still_gets_the_ic_cv():
    """'Lead Data Analyst' is an IC title. Sending the manager CV to an IC role is
    exactly what gets read as overqualified."""
    text = "Lead Data Analyst. Own our experimentation program. SQL and Python daily."
    assert score(extract(text, title="Lead Data Analyst"), text)["recommended_cv"] == "ic"


def test_lead_with_real_reports_gets_the_lead_cv():
    text = "Lead Data Analyst. You will manage a team of 4 analysts and own hiring."
    assert score(extract(text, title="Lead Data Analyst"), text)["recommended_cv"] == "lead"
