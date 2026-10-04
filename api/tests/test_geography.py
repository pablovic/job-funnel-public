"""Tests de la regla geografica.

El caso que la motivo es real: veridata publica "US Remote" y en el cuerpo dice
"This role may be performed fully remotely within the United States", mientras
en el parrafo siguiente menciona sus oficinas. Una frase es un candado y la otra
no, y el filtro tiene que distinguirlas.
"""
from app.free.extractor import extract, geo_scope
from app.rules.filters import Candidate, Decision, evaluate

# --- deteccion ---------------------------------------------------------------


def test_remotely_within_the_us_is_a_lock():
    r, quote = geo_scope("This role may be performed fully remotely within the United States.")
    assert r == "us"
    assert "United States" in quote


def test_mentioning_a_us_office_is_not_a_lock():
    """El parrafo que sigue al candado en el aviso real. Solo dice donde queda
    la oficina; no restringe a nadie."""
    text = ("Please note that our US headquarters are located in NYC. We also have "
            "office hubs in Austin, Miami, and Mountain View.")
    assert geo_scope(text)[0] == "unknown"


def test_work_authorization_is_a_lock():
    assert geo_scope("You must be authorized to work in the United States.")[0] == "us"


def test_location_field_us_remote_is_a_lock():
    assert geo_scope("", location_hint="US Remote")[0] == "us"


def test_location_field_usa_only_is_a_lock():
    assert geo_scope("", location_hint="USA Only")[0] == "us"


def test_location_field_worldwide_is_global():
    assert geo_scope("", location_hint="Worldwide")[0] == "global"


def test_location_field_latam_is_allowed():
    assert geo_scope("", location_hint="LATAM")[0] == "latam"


def test_lowercase_us_pronoun_is_not_a_country():
    """'join us', 'contact us' — sin esto casi todos los avisos serian candados."""
    assert geo_scope("Join us and help us build the future. Contact us for details.")[0] == "unknown"


def test_listing_customer_countries_is_not_a_lock():
    text = "We serve customers in the United States, Brazil and Germany from our distributed team."
    assert geo_scope(text)[0] != "us"


def test_work_from_anywhere_is_global():
    assert geo_scope("Work from anywhere in the world. We are fully distributed.")[0] == "global"


def test_other_countries_are_detected_too():
    assert geo_scope("Candidates must be located in Canada.")[0] == "canada"
    assert geo_scope("Open to residents of the United Kingdom.")[0] == "uk"


def test_geo_scope_travels_through_extract():
    e = extract("Remote analytics role.", title="Data Analyst", location_hint="US Remote")
    assert e["geo_scope"] == "us"


# --- la regla ----------------------------------------------------------------


def _cand(**kw):
    d = dict(title="Senior Data Analyst", text="Fully remote role.",
             remote="remote_country", geo_scope="unknown")
    d.update(kw)
    return Candidate(**d)


def test_us_only_role_is_rejected():
    r = evaluate(_cand(geo_scope="us", geo_quote="US Remote"))
    assert r.decision == Decision.REJECT
    assert any("restricted to US" in x for x in r.reasons)


def test_the_reason_carries_the_evidence():
    """Un rechazo tiene que poder auditarse sin abrir el aviso."""
    r = evaluate(_cand(geo_scope="us", geo_quote="remotely within the United States"))
    assert any("United States" in x for x in r.reasons)


def test_global_and_latam_pass():
    for region in ("global", "latam"):
        r = evaluate(_cand(geo_scope=region))
        assert not any("restricted to" in x for x in r.reasons), region


def test_unknown_geography_never_rejects():
    """Silencio no es evidencia — mismo criterio que con el sueldo."""
    r = evaluate(_cand(geo_scope="unknown"))
    assert not any("restricted to" in x for x in r.reasons)


def test_eligible_regions_is_configurable():
    """Si algun dia puede trabajar desde EE.UU., se agrega a la config."""
    r = evaluate(_cand(geo_scope="us"), eligible_regions=("global", "latam", "us"))
    assert not any("restricted to" in x for x in r.reasons)
