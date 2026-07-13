"""Tests del guardado de análisis en la web (sin red: motor y store sustituidos)."""

import pandas as pd
import pytest

from app import create_app
from core import engine, store
from core.engine import Strategy


@pytest.fixture()
def db(tmp_path, monkeypatch):
    ruta = tmp_path / "test.db"
    # el store usa DEFAULT_DB salvo db_path; redirigimos DEFAULT_DB al temporal
    monkeypatch.setattr(store, "DEFAULT_DB", ruta)
    return ruta


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def motor_falso(monkeypatch):
    def run_falso(weights, start, end, **kwargs):
        fechas = pd.bdate_range(start, end)
        precios = pd.DataFrame(
            {t: [100.0 + i for i in range(len(fechas))] for t in weights}, index=fechas
        )
        return engine.run_backtest(precios, Strategy(
            weights=weights,
            initial_investment=kwargs.get("initial_investment", 0),
            monthly_contribution=kwargs.get("monthly_contribution", 0),
            rebalance_freq=kwargs.get("rebalance_freq"),
        ))

    import modules.backtester

    monkeypatch.setattr(modules.backtester, "run", run_falso)


FORM = {
    "ticker_0": "AAA", "peso_0": "100",
    "ticker_1": "", "peso_1": "", "ticker_2": "", "peso_2": "", "ticker_3": "", "peso_3": "",
    "inicial": "1000", "mensual": "0", "start": "2024-01-01", "end": "2024-12-31",
    "rebalance": "", "benchmark": "",
}


def test_guardar_y_aparece_en_lista(client, motor_falso, db):
    r = client.post("/backtester/guardar", data=dict(FORM, nombre_guardar="Mi test"))
    assert "Backtest guardado" in r.get_data(as_text=True)

    lista = client.get("/guardados").get_data(as_text=True)
    assert "Mi test" in lista
    assert "Cargar" in lista


def test_recargar_rellena_el_formulario(client, motor_falso, db):
    client.post("/backtester/guardar", data=dict(FORM, ticker_0="ZZZ.MC", nombre_guardar="X"))
    id_ = store.list_all()[0]["id"]
    r = client.get(f"/backtester?cargar={id_}")
    html = r.get_data(as_text=True)
    assert 'value="ZZZ.MC"' in html
    assert "datos-grafico" in html  # se reejecuta al cargar


def test_borrar(client, motor_falso, db):
    client.post("/backtester/guardar", data=dict(FORM, nombre_guardar="Borrable"))
    id_ = store.list_all()[0]["id"]
    r = client.post(f"/guardados/borrar/{id_}", follow_redirects=True)
    assert "Análisis borrado" in r.get_data(as_text=True)
    assert store.get(id_) is None


def test_guardados_vacio(client, db):
    r = client.get("/guardados")
    assert "Aún no has guardado" in r.get_data(as_text=True)


def test_cargar_id_inexistente_no_rompe(client, db):
    r = client.get("/backtester?cargar=9999")
    assert r.status_code == 200  # cae al formulario por defecto
