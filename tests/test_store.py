"""Persistencia SQLite de análisis guardados."""

import pytest

from core import store


@pytest.fixture()
def db(tmp_path):
    return tmp_path / "test.db"


def test_guardar_y_recuperar(db):
    params = {"ticker_0": "SXR8.DE", "peso_0": "100", "mensual": "200"}
    summary = {"final": "70.228,12 €", "cagr": "13,39 %"}
    id_ = store.save("backtester", "Mi S&P 500", params, summary, db_path=db)

    rec = store.get(id_, db_path=db)
    assert rec["name"] == "Mi S&P 500"
    assert rec["kind"] == "backtester"
    assert rec["params"] == params
    assert rec["summary"] == summary
    assert rec["created_at"]


def test_lista_ordenada_por_reciente(db):
    a = store.save("backtester", "A", {}, {}, db_path=db)
    b = store.save("backtester", "B", {}, {}, db_path=db)
    ids = [r["id"] for r in store.list_all(db_path=db)]
    assert ids == [b, a]  # el más reciente primero


def test_filtra_por_tipo(db):
    store.save("backtester", "bt", {}, {}, db_path=db)
    store.save("optimizer", "opt", {}, {}, db_path=db)
    assert len(store.list_all("backtester", db_path=db)) == 1
    assert len(store.list_all(db_path=db)) == 2


def test_borrar(db):
    id_ = store.save("backtester", "temporal", {}, {}, db_path=db)
    assert store.delete(id_, db_path=db) is True
    assert store.get(id_, db_path=db) is None
    assert store.delete(9999, db_path=db) is False


def test_nombre_vacio_por_defecto(db):
    id_ = store.save("backtester", "  ", {}, {}, db_path=db)
    assert store.get(id_, db_path=db)["name"] == "Sin nombre"
