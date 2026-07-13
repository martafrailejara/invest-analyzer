"""Tests de la página de riesgo (sin red: motor sustituido)."""

import numpy as np
import pandas as pd
import pytest

from app import create_app
from modules import risk


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def motor_falso(monkeypatch):
    def run_falso(weights, benchmark, start, end, **kwargs):
        rng = np.random.default_rng(0)
        fechas = pd.bdate_range("2022-01-03", periods=250)
        cols = list(weights) + ([benchmark] if benchmark and benchmark not in weights else [])
        px = pd.DataFrame(
            {c: 100 * np.cumprod(1 + rng.normal(0.0004, 0.012, 250)) for c in cols},
            index=fechas,
        )
        return risk.analyze(px, weights, benchmark)

    monkeypatch.setattr(risk, "run", run_falso)


FORM_VALIDO = {
    "ticker_0": "AAA", "peso_0": "50", "ticker_1": "BBB", "peso_1": "50",
    "ticker_2": "", "peso_2": "", "ticker_3": "", "peso_3": "",
    "benchmark": "SPY", "start": "2022-01-01", "end": "2023-12-31",
}


def test_get_muestra_formulario(client):
    r = client.get("/riesgo")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Analizar riesgo" in html
    assert "Fase" not in html


def test_post_valido_muestra_metricas_y_heatmap(client, motor_falso):
    r = client.post("/riesgo", data=FORM_VALIDO)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Sortino" in html
    assert "VaR 95%" in html
    assert "Beta vs índice" in html
    assert "heatmap" in html
    assert "Matriz de correlación" in html
    # la diagonal de la matriz es 1,00
    assert "1,00" in html


def test_post_sin_benchmark(client, motor_falso):
    datos = dict(FORM_VALIDO, benchmark="")
    r = client.post("/riesgo", data=datos)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "heatmap" in html  # sigue habiendo correlaciones


def test_post_sin_activos(client, motor_falso):
    datos = dict(FORM_VALIDO, ticker_0="", peso_0="", ticker_1="", peso_1="")
    r = client.post("/riesgo", data=datos)
    assert "al menos un activo" in r.get_data(as_text=True)
