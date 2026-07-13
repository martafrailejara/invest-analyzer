"""Tests de la página Monte Carlo (sin red: motor sustituido)."""

import numpy as np
import pandas as pd
import pytest

from app import create_app
from modules import montecarlo


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def motor_falso(monkeypatch):
    def run_falso(weights, start, end, **kwargs):
        fechas = pd.date_range("2015-01-01", periods=60, freq="MS")
        rng = np.random.default_rng(0)
        serie = 100 * np.cumprod(1 + rng.normal(0.006, 0.03, 60))
        px = pd.DataFrame({t: serie for t in weights}, index=fechas)
        return montecarlo.project(px, weights, **{k: v for k, v in kwargs.items()
                                                  if k in ("years", "initial", "monthly_contribution")},
                                  n_sims=200, seed=1)

    monkeypatch.setattr(montecarlo, "run", run_falso)


FORM_VALIDO = {
    "ticker_0": "AAA", "peso_0": "100",
    "ticker_1": "", "peso_1": "", "ticker_2": "", "peso_2": "", "ticker_3": "", "peso_3": "",
    "inicial": "5000", "mensual": "200", "years": "20",
    "start": "2010-01-01", "end": "2024-12-31",
}


def test_get_muestra_formulario(client):
    r = client.get("/montecarlo")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Proyectar" in html
    assert "bootstrap" in html


def test_post_valido_muestra_abanico(client, motor_falso):
    r = client.post("/montecarlo", data=FORM_VALIDO)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "datos-grafico" in html
    assert "Escenario mediano" in html
    assert "Prob. de ganar" in html
    assert "Percentil 10&#8211;90" in html or "Percentil 10–90" in html


def test_post_horizonte_invalido(client, motor_falso):
    r = client.post("/montecarlo", data=dict(FORM_VALIDO, years="99"))
    assert "entre 1 y 50" in r.get_data(as_text=True)


def test_post_sin_aportacion(client, motor_falso):
    r = client.post("/montecarlo", data=dict(FORM_VALIDO, inicial="0", mensual="0"))
    assert "aportación" in r.get_data(as_text=True)
