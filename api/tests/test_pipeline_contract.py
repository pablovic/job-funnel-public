"""Contract tests that do not spend tokens: the shapes the agents must return."""
from app.agents.client import quoted_in_source
from app.agents.normalizer import to_usd_year


def test_quote_check_is_whitespace_and_case_insensitive():
    src = "We are looking for   a Senior\nData Analyst."
    assert quoted_in_source("senior data analyst", src)


def test_quote_check_rejects_paraphrase():
    assert not quoted_in_source("we want a senior analyst", "We are looking for a Senior Data Analyst.")


def test_brl_month_converts_to_usd_year():
    assert to_usd_year(30_000, "BRL", "month") == round(30_000 / 5.4 * 12)


def test_missing_amount_stays_none():
    assert to_usd_year(None, "USD", "year") is None


def test_remotive_parser_folds_company_and_salary_into_body():
    from app.ingest.remotive import parse_job
    job = {
        "id": 123, "title": "Senior Product Analyst", "company_name": "Acme",
        "salary": "$90k - $120k", "candidate_required_location": "Worldwide",
        "url": "https://remotive.com/remote-jobs/data/senior-product-analyst-123",
        "description": "<p>Own the <b>experimentation</b> program.</p>",
    }
    p = parse_job(job)
    assert p.title == "Senior Product Analyst — Acme"
    assert "Salary: $90k - $120k" in p.raw_text          # rule can see the range
    assert "experimentation" in p.raw_text                # html stripped
    assert p.url.startswith("https://remotive.com")       # attribution preserved
