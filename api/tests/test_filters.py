"""The rules gate is the only component with no model in it, so it is the only
one that can be tested deterministically. Each test names the real decision it
encodes."""
from app.rules.filters import Candidate, Decision, evaluate

# El texto tiene largo de aviso real a proposito. Desde que existe la bandera de
# "aviso sin descripcion", el LARGO de este campo es una senal, no relleno: un
# stub de tres palabras hace que TODA candidata de prueba salga marcada, y los
# tests dejan de hablar de lo que dicen hablar. Este texto no menciona ninguna
# herramienta ni dominio, para no mover el puntaje de las pruebas que lo usan.
POSTING = (
    "Fully remote role. We are looking for an analyst to own reporting and "
    "experimentation across the product funnel. You will work closely with the "
    "growth and engineering teams, define the metrics that matter, and present "
    "findings to leadership on a regular cadence. Requirements: strong "
    "analytical thinking, comfort with ambiguity, and a track record of turning "
    "messy information into decisions that people actually act on. We care more "
    "about how you reason through a problem than about the specific tools you "
    "have used before. The team is distributed across several time zones and "
    "works asynchronously, with a short overlap window in the afternoon. We "
    "review applications on a rolling basis and aim to reply within two weeks."
)


def base(**kw):
    d = dict(title="Senior Data Analyst", text=POSTING, company="Acme",
             remote="remote_global", comp_published=True, comp_usd_year_min=90_000,
             comp_usd_year_max=120_000, lang="en")
    d.update(kw)
    return Candidate(**d)


def test_staffing_channel_is_rejected():
    r = evaluate(base(company="Talentbridge Staffing"))
    assert r.decision is Decision.REJECT


def test_onsite_is_rejected_because_the_move_to_rio_depends_on_remote():
    assert evaluate(base(remote="onsite")).decision is Decision.REJECT
    assert evaluate(base(remote="hybrid")).decision is Decision.REJECT


def test_published_range_below_floor_is_rejected():
    r = evaluate(base(comp_usd_year_max=60_000))
    assert r.decision is Decision.REJECT
    assert "below" in r.reasons[0]


def test_missing_range_is_flagged_not_rejected():
    """The finding that changed the strategy: ten of ten rejections cited
    overqualification and none published a range. Silence is not evidence."""
    r = evaluate(base(comp_published=False, comp_usd_year_min=None, comp_usd_year_max=None))
    assert r.decision is Decision.FLAG
    assert r.flags


def test_mid_level_title_is_not_rejected():
    """A mid title paying USD beats a manager title paying BRL. Level is a
    scoring dimension, never a gate."""
    r = evaluate(base(title="Data Analyst II"))
    assert r.decision is Decision.PASS


def test_a_listing_with_no_description_is_flagged_not_rejected():
    """Jobgether devuelve metadatos sin el texto del puesto. craft y domain
    salen de buscar palabras ahi, asi que sin texto el puntaje es parcial — pero
    el aviso puede ser excelente. Se marca, nunca se descarta."""
    r = evaluate(base(text="Senior Data Analyst at Acme. Location: Anywhere."))
    assert r.decision is not Decision.REJECT
    assert any("no description" in f for f in r.flags)


def test_a_real_posting_is_not_flagged_as_thin():
    """La contracara: el umbral no debe dispararse con un aviso normal."""
    assert not any("no description" in f for f in evaluate(base()).flags)
