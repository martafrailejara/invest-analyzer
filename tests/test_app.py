"""Tests de la web Flask (sin red: el motor de backtest se sustituye)."""

import pandas as pd
import pytest

from app import create_app
from core import engine
from core.engine import Strategy


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def motor_falso(monkeypatch):
    """Sustituye modules.backtester.run por un backtest sobre precios sintéticos."""

    def run_falso(weights, start, end, **kwargs):
        fechas = pd.bdate_range(start, end)
        precios = pd.DataFrame(
            {t: [100.0 + i for i in range(len(fechas))] for t in weights}, index=fechas
        )
        return engine.run_backtest(
            precios,
            Strategy(
                weights=weights,
                initial_investment=kwargs.get("initial_investment", 0),
                monthly_contribution=kwargs.get("monthly_contribution", 0),
                rebalance_freq=kwargs.get("rebalance_freq"),
            ),
        )

    import modules.backtester

    monkeypatch.setattr(modules.backtester, "run", run_falso)


FORM_VALIDO = {
    "ticker_0": "AAA", "peso_0": "80",
    "ticker_1": "BBB", "peso_1": "20",
    "ticker_2": "", "peso_2": "",
    "ticker_3": "", "peso_3": "",
    "inicial": "1000", "mensual": "200",
    "start": "2024-01-01", "end": "2024-12-31",
    "rebalance": "Y",
}


def test_index_redirige_al_backtester(client):
    r = client.get("/")
    assert r.status_code == 302
    assert "/backtester" in r.headers["Location"]


def test_get_backtester_muestra_formulario(client):
    r = client.get("/backtester")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Ejecutar backtest" in html
    assert "SXR8.DE" in html  # ejemplo precargado


def test_modulos_pendientes_y_404(client):
    r = client.get("/anomalias")
    assert r.status_code == 200
    assert "Fase 7" in r.get_data(as_text=True)
    assert client.get("/no-existe").status_code == 404


def test_post_valido_muestra_resultados(client, motor_falso):
    r = client.post("/backtester", data=FORM_VALIDO)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Valor final" in html
    assert "datos-grafico" in html
    assert "Total aportado" in html
    assert "Máx. drawdown" in html


def test_post_pesos_no_suman_100(client, motor_falso):
    datos = dict(FORM_VALIDO, peso_0="50", peso_1="20")
    r = client.post("/backtester", data=datos)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "deben sumar 100" in html
    assert "datos-grafico" not in html


def test_post_fechas_invertidas(client, motor_falso):
    datos = dict(FORM_VALIDO, start="2025-01-01", end="2024-01-01")
    r = client.post("/backtester", data=datos)
    assert "anterior a la final" in r.get_data(as_text=True)


def test_post_sin_activos(client, motor_falso):
    datos = dict(FORM_VALIDO, ticker_0="", peso_0="", ticker_1="", peso_1="")
    r = client.post("/backtester", data=datos)
    assert "al menos un activo" in r.get_data(as_text=True)


def test_post_conserva_lo_introducido(client, motor_falso):
    datos = dict(FORM_VALIDO, ticker_0="ZZZ.MC", peso_0="150")
    r = client.post("/backtester", data=datos)
    assert "ZZZ.MC" in r.get_data(as_text=True)
