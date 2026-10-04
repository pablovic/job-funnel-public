"""Tests del importador de postulaciones pasadas.

Toda la validacion vive en parse_row(), que es una funcion pura: se puede probar
sin Postgres, y es donde estan los errores que de verdad importan (una fecha mal
escrita que corre el tiempo de respuesta, una etapa que inventa una contestacion
que nunca llego).
"""
import datetime as dt

from app.cli import RESPONSE_STAGES, parse_row


def row(**kw):
    base = {"date": "2026-08-14", "company": "Kestrel Markets", "role": "Lead Data Analyst",
            "url": "", "cv_variant": "", "salary_asked": "", "response_date": "",
            "stage": "", "note": "", "text": ""}
    base.update(kw)
    return base


# --- lo minimo -------------------------------------------------------------

def test_minimal_row_parses():
    r, errors = parse_row(row())
    assert errors == []
    assert r is not None
    assert r.company == "Kestrel Markets"
    assert r.applied_at.date() == dt.date(2026, 8, 14)


def test_title_uses_the_em_dash_separator():
    """La regla de familia de puesto parte el titulo por ' — '. Con otro
    separador, el puesto no se reconoce."""
    r, _ = parse_row(row())
    assert r.title == "Lead Data Analyst — Kestrel Markets"
    assert r.title.split(" — ")[0] == "Lead Data Analyst"


def test_missing_company_is_skipped_not_guessed():
    r, errors = parse_row(row(company=""))
    assert r is None and errors


def test_an_unreadable_date_stops_that_row_only():
    """Texto que no es una fecha de ninguna manera. La fila se saltea y el error
    nombra el valor, para poder encontrarlo en la planilla."""
    r, errors = parse_row(row(date="la semana pasada"))
    assert r is None
    assert any("la semana pasada" in e for e in errors)


# --- sueldo y CV -----------------------------------------------------------

def test_salary_accepts_the_way_people_actually_type_it():
    for raw in ("90000", "90,000", "$90,000", " $90000 "):
        r, _ = parse_row(row(salary_asked=raw))
        assert r.comp_asked_usd == 90_000.0, raw


def test_unreadable_salary_warns_and_continues():
    r, _ = parse_row(row(salary_asked="noventa mil"))
    assert r is not None
    assert r.comp_asked_usd is None and r.posted is None
    assert any("sueldo" in w for w in r.warnings)


# --- las dos cosas distintas que puede traer la columna de sueldo ------------

def test_a_bare_number_is_what_you_asked_for():
    r, _ = parse_row(row(salary_asked="90000"))
    assert r.comp_asked_usd == 90_000.0
    assert r.posted is None


def test_a_range_with_currency_is_what_the_posting_published():
    """'USD 75000 - 100000 Yearly' no es lo que pediste: es lo que ofrecia el
    aviso. Son datos distintos y van a lugares distintos."""
    r, _ = parse_row(row(salary_asked="USD 75000 - 100000 Yearly"))
    assert r.comp_asked_usd is None
    assert r.posted["currency"] == "USD"
    assert r.posted["comp_max"] == 100_000.0
    assert r.posted["period"] == "year"


def test_reais_written_without_the_symbol_are_understood():
    """'RS 24000' es como se escribe R$ sin el simbolo."""
    r, _ = parse_row(row(salary_asked="RS 24000 - 30000 Monthly"))
    assert r.posted["currency"] == "BRL"
    assert r.posted["period"] == "month"


def test_reais_without_a_period_are_read_as_monthly():
    """R$33.000 al mes es un sueldo senior en Brasil; al ano seria absurdo."""
    r, _ = parse_row(row(salary_asked="RS 33000"))
    assert r.posted["period"] == "month"


def test_not_published_is_not_an_error():
    for texto in ("not published", "N/A", "-", ""):
        r, _ = parse_row(row(salary_asked=texto))
        assert r.comp_asked_usd is None and r.posted is None
        assert not any("sueldo" in w for w in r.warnings), texto


# --- acuses sin fecha --------------------------------------------------------

def test_an_ack_without_a_date_is_not_counted_by_default():
    r, _ = parse_row(row(stage="ack", response_date=""))
    assert r.stage == "" and r.response_at is None


def test_ack_same_day_counts_it_at_the_application_date():
    r, _ = parse_row(row(stage="ack", response_date=""), ack_same_day=True)
    assert r.stage == "ack"
    assert r.response_at == r.applied_at


def test_ack_same_day_does_not_apply_to_a_screening_invite():
    """Un acuse automatico llega el mismo dia. Una invitacion a screening puede
    llegar tres semanas despues, y ahi la fecha es el dato."""
    r, _ = parse_row(row(stage="screening", response_date=""), ack_same_day=True)
    assert r.stage == "" and r.response_at is None


def test_unknown_cv_variant_falls_back_to_ic():
    r, _ = parse_row(row(cv_variant="manager"))
    assert r.cv_variant == "ic"
    assert any("cv_variant" in w for w in r.warnings)


# --- respuestas: donde se inventan los datos ---------------------------------

def test_response_stage_without_a_date_does_not_invent_one():
    """Sin fecha de respuesta no se puede medir cuanto tardaron. Antes que
    inventar un valor, se carga como 'applied' y se avisa."""
    r, _ = parse_row(row(stage="screening", response_date=""))
    assert r.stage == ""
    assert any("response_date" in w for w in r.warnings)


def test_response_stage_with_a_date_is_kept():
    r, _ = parse_row(row(stage="screening", response_date="2026-08-21"))
    assert r.stage == "screening"
    assert r.response_at.date() == dt.date(2026, 8, 21)


def test_ghosted_never_counts_as_a_response():
    """El silencio es ausencia de respuesta. Un evento 'ghosted' haria que
    first_response_at marque una contestacion que nunca existio."""
    assert "ghosted" not in RESPONSE_STAGES
    r, _ = parse_row(row(stage="ghosted"))
    assert r.stage == "ghosted"
    assert r.response_at is None


def test_a_response_before_the_application_is_dropped():
    r, _ = parse_row(row(date="2026-08-14", response_date="2026-08-01", stage="rejected"))
    assert r.response_at is None and r.stage == ""
    assert any("anterior" in w for w in r.warnings)


def test_invented_stage_is_ignored_with_the_valid_list():
    r, _ = parse_row(row(stage="entrevista", response_date="2026-08-21"))
    assert r.stage == ""
    assert any("screening" in w for w in r.warnings)


def test_every_response_stage_is_accepted():
    for s in sorted(RESPONSE_STAGES):
        r, _ = parse_row(row(stage=s, response_date="2026-08-21"))
        assert r.stage == s, s


# --- como lo guarda Excel de verdad -----------------------------------------

def _tmp_csv(tmp_path, contenido):
    f = tmp_path / "a.csv"
    f.write_text(contenido, encoding="utf-8")
    return str(f)


def test_semicolons_from_spanish_excel_are_detected(tmp_path):
    from app.cli import read_rows
    rows, delim, _ = read_rows(_tmp_csv(tmp_path,
        "date;company;role\n2026-08-14;Kestrel Markets;Lead Data Analyst\n"))
    assert delim == ";"
    assert rows[0]["company"] == "Kestrel Markets"


def test_header_casing_and_spaces_do_not_matter(tmp_path):
    from app.cli import read_rows
    rows, _, _ = read_rows(_tmp_csv(tmp_path,
        " Date , Company , Role \n2026-08-14,Kestrel Markets,Lead Data Analyst\n"))
    assert {"date", "company", "role"} <= set(rows[0])


def test_a_bom_does_not_break_the_first_column(tmp_path):
    from app.cli import read_rows
    rows, _, _ = read_rows(_tmp_csv(tmp_path,
        "﻿date,company,role\n2026-08-14,Kestrel Markets,Lead Data Analyst\n"))
    assert "date" in rows[0]


def test_a_slash_date_is_refused_when_the_format_is_unknown():
    """Sin saber el formato, una fecha con barras no se interpreta."""
    r, errors = parse_row(row(date="14/08/2026"))
    assert r is None
    assert errors


def test_an_empty_file_returns_nothing(tmp_path):
    from app.cli import read_rows
    assert read_rows(_tmp_csv(tmp_path, "\n"))[0] == []


def test_a_file_saved_by_excel_in_windows_1252_is_read(tmp_path):
    """El caso real que fallo: la raya larga se guarda como el byte 0x97, que no
    es UTF-8 valido. Excel en Windows guarda asi por defecto."""
    from app.cli import read_rows
    f = tmp_path / "w.csv"
    f.write_bytes(
        ("date,company,role,note\n"
         "2026-08-14,Kestrel Markets,Lead Data Analyst,\"Charla con María — muy buena\"\n"
         ).encode("cp1252"))
    rows, _, enc = read_rows(str(f))
    assert enc == "cp1252"
    assert "María — muy buena" in rows[0]["note"]


def test_a_quoted_note_spanning_two_lines_stays_one_row(tmp_path):
    from app.cli import read_rows
    rows, _, _ = read_rows(_tmp_csv(tmp_path,
        'date,company,role,note\n2026-08-14,Acme,Data Analyst,"linea uno\nlinea dos"\n'))
    assert len(rows) == 1
    assert "\n" in rows[0]["note"]


def test_an_em_dash_inside_the_role_does_not_break_the_separator(tmp_path):
    """Sin normalizar, 'Lead Data Analyst — Growth' en Kestrel Markets daria un
    titulo con tres rayas largas y partirlo dejaria de dar la empresa."""
    r, _ = parse_row(row(role="Lead Data Analyst — Growth"))
    assert r.title == "Lead Data Analyst - Growth — Kestrel Markets"
    assert r.title.split(" — ") == ["Lead Data Analyst - Growth", "Kestrel Markets"]


# --- deduccion del formato de fecha -----------------------------------------

def test_the_format_is_proven_by_a_day_over_twelve():
    """'8/23/2026' solo puede ser mes/dia: 23 no es un mes. Esa prueba vale para
    todo el archivo, porque una planilla no mezcla formatos."""
    from app.cli import detect_date_format
    fmt, prueba = detect_date_format([{"date": "8/23/2026"}, {"date": "9/1/2026"}])
    assert fmt == "mdy"
    assert "23" in prueba


def test_the_european_format_is_proven_the_same_way():
    from app.cli import detect_date_format
    assert detect_date_format([{"date": "23/08/2026"}])[0] == "dmy"


def test_an_unprovable_file_is_refused_not_guessed():
    """Todos los numeros son 12 o menos: no hay evidencia. Adivinar aca correria
    las fechas y envenenaria el tiempo de respuesta."""
    from app.cli import detect_date_format
    fmt, motivo = detect_date_format([{"date": "9/1/2026"}, {"date": "5/6/2026"}])
    assert fmt is None
    assert "no hay forma de saberlo" in motivo


def test_a_file_that_mixes_both_formats_is_refused():
    from app.cli import detect_date_format
    fmt, motivo = detect_date_format([{"date": "23/08/2026"}, {"date": "8/23/2026"}])
    assert fmt is None
    assert "mezcla" in motivo


def test_iso_dates_need_no_detection():
    from app.cli import detect_date_format
    assert detect_date_format([{"date": "2026-08-23"}])[0] == "iso"


def test_the_response_date_column_also_counts_as_evidence():
    from app.cli import detect_date_format
    assert detect_date_format([{"date": "9/1/2026", "response_date": "9/23/2026"}])[0] == "mdy"


def test_the_detected_format_is_applied_to_every_row():
    fmt = "mdy"
    r, _ = parse_row(row(date="8/23/2026"), fmt)
    assert (r.applied_at.month, r.applied_at.day) == (8, 23)
    r, _ = parse_row(row(date="9/1/2026"), fmt)
    assert (r.applied_at.month, r.applied_at.day) == (9, 1)


def test_the_same_string_read_the_other_way_gives_the_other_date():
    """La razon por la que esto no se adivina: '9/1/2026' son dos dias
    distintos segun el formato."""
    assert parse_row(row(date="9/1/2026"), "mdy")[0].applied_at.date().isoformat() == "2026-09-01"
    assert parse_row(row(date="9/1/2026"), "dmy")[0].applied_at.date().isoformat() == "2026-01-09"


def test_an_impossible_date_is_reported_not_silently_dropped():
    r, errors = parse_row(row(date="2/30/2026"), "mdy")
    assert r is None
    assert errors


# --- etapas de cierre: se registran, pero no son una respuesta ---------------

def test_ghosted_is_kept_without_needing_a_date():
    from app.cli import CLOSING_STAGES
    assert "ghosted" in CLOSING_STAGES
    r, _ = parse_row(row(stage="ghosted"))
    assert r.stage == "ghosted"
    assert r.response_at is None
    assert not any("response_date" in w for w in r.warnings)


def test_withdrawn_does_not_demand_a_date_either():
    r, _ = parse_row(row(stage="withdrawn"))
    assert r.stage == "withdrawn"
    assert not any("necesita" in w for w in r.warnings)


def test_no_closing_stage_counts_as_a_company_reply():
    """v_application_state excluye estas etapas de first_response_at. Si alguna
    se colara en RESPONSE_STAGES, la tasa de respuesta mentiria."""
    from app.cli import CLOSING_STAGES, RESPONSE_STAGES
    assert not (CLOSING_STAGES & RESPONSE_STAGES)


def test_waiting_for_a_reply_means_an_empty_stage():
    """'mande y espero' NO es 'ack'. ack es que la empresa contesto algo."""
    r, _ = parse_row(row(stage=""))
    assert r.stage == "" and r.response_at is None
