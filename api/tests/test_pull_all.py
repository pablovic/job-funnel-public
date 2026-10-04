"""Tests de pull-all, el comando que corre la automatizacion.

Lo que importa probar no es que traiga avisos —eso ya lo prueban los adaptadores—
sino como se comporta cuando algo sale mal un martes a las 8 sin nadie mirando:
una fuente caida no puede tumbar a las demas, y el resumen tiene que decir la
verdad sobre que corrio y que no.
"""
import json
import sys
import types

import pytest
from typer.testing import CliRunner

import app.cli as cli_mod
from app.ingest.base import RawPosting


class FakeSource:
    def __init__(self, name, adapter, enabled=True):
        self.id = name
        self.name = name
        self.adapter = adapter
        self.config = {}
        self.enabled = enabled
        self.last_run_at = None


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows

    def filter(self, *a, **k):
        return self

    def order_by(self, *a, **k):
        return self

    def all(self):
        return self.rows


class FakeDB:
    def __init__(self, sources):
        self.sources = sources
        self.commits = 0
        self.rollbacks = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def query(self, *a, **k):
        return FakeQuery(self.sources)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


def _adapter(name, fetch):
    mod = types.ModuleType(f"app.ingest.{name}")
    mod.fetch = fetch
    sys.modules[f"app.ingest.{name}"] = mod


@pytest.fixture
def run(monkeypatch):
    """Corre pull-all contra fuentes falsas y devuelve (resultado, resumen, db)."""
    _adapter("fake_ok", lambda cfg: [RawPosting(title="Data Analyst — A", raw_text="x"),
                                     RawPosting(title="Data Analyst — B", raw_text="y")])
    _adapter("fake_boom", lambda cfg: (_ for _ in ()).throw(RuntimeError("API caida")))
    _adapter("fake_empty", lambda cfg: [])

    outcomes = iter(["scored", "duplicate"] * 10)
    monkeypatch.setattr(cli_mod, "ingest", lambda db, **kw: (None, next(outcomes)))

    def _run(sources):
        db = FakeDB(sources)
        monkeypatch.setattr(cli_mod, "SessionLocal", lambda: db)
        res = CliRunner().invoke(cli_mod.cli, ["pull-all"])
        line = [l for l in res.output.splitlines() if l.startswith(cli_mod.SUMMARY_MARK)]
        summary = json.loads(line[-1][len(cli_mod.SUMMARY_MARK):]) if line else None
        return res, summary, db
    return _run


def test_one_broken_source_does_not_stop_the_others(run):
    res, summary, db = run([FakeSource("a_ok", "fake_ok"),
                            FakeSource("b_boom", "fake_boom"),
                            FakeSource("c_ok", "fake_ok")])
    assert res.exit_code == 0, res.output
    assert summary["sources"] == 2
    assert summary["failed"] == ["b_boom"]
    assert "FALLO" in res.output and "API caida" in res.output
    assert db.rollbacks == 1


def test_totals_add_up_across_sources(run):
    _, summary, _ = run([FakeSource("a", "fake_ok"), FakeSource("b", "fake_ok")])
    assert summary["found"] == 4
    assert summary["scored"] + summary["duplicate"] == 4


def test_every_successful_source_is_committed_on_its_own(run):
    """Si una fuente del medio falla, lo que trajeron las anteriores ya esta
    guardado. Un commit por fuente, no uno al final."""
    _, _, db = run([FakeSource("a", "fake_ok"), FakeSource("b", "fake_ok")])
    assert db.commits == 2


def test_last_run_is_recorded(run):
    src = FakeSource("a", "fake_ok")
    run([src])
    assert src.last_run_at is not None


def test_exit_code_is_1_only_when_everything_failed(run):
    res, summary, _ = run([FakeSource("a", "fake_boom"), FakeSource("b", "fake_boom")])
    assert res.exit_code == 1
    assert summary["sources"] == 0
    assert summary["failed"] == ["a", "b"]


def test_a_quiet_day_is_not_a_failure(run):
    res, summary, _ = run([FakeSource("a", "fake_empty")])
    assert res.exit_code == 0
    assert summary["scored"] == 0 and summary["sources"] == 1


def test_no_sources_is_not_a_failure_either(run):
    res, summary, _ = run([])
    assert res.exit_code == 0
    assert summary["sources"] == 0


def test_the_summary_is_the_last_line_and_ascii_only():
    """El script de Windows lee la ultima linea con esta marca. Sin acentos: la
    consola de Windows PowerShell 5.1 los rompe al capturar la salida de docker."""
    assert cli_mod.SUMMARY_MARK == "SUMMARY "
    assert cli_mod.SUMMARY_MARK.isascii()


def test_boards_can_sleep_between_tokens():
    """El comando boards pausa entre empresas. Faltaba el import y se caia en la
    segunda empresa con NameError."""
    assert hasattr(cli_mod, "time")
