"""Tests de la página de anomalías (sin red: motor sustituido)."""

import pandas as pd
import pytest

from app import create_app
from modules import anomalies


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def motor_falso(monkeypatch):
    def run_falso(ticker, start, end, *, window=60, threshold=3.0, **kwargs):
        precios = [100.0]
        for i in range(1, 200):
            r = 0.005 if i % 2 else -0.005
            if i == 150:
                r = -0.15
            precios.append(precios[-1] * (1 + r))
        serie = pd.Series(precios, index=pd.bdate_range(start, periods=200))
        return anomalies.detect(serie, window=window, threshold=threshold)

    monkeypatch.setattr(anomalies, "run", run_falso)


FORM_VALIDO = {
    "ticker": "AAA", "start": "2024-01-01", "end": "2024-12-31",
    "window": "60", "threshold": "3",
}


def test_get_muestra_formulario(client):
    r = client.get("/anomalias")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Detectar anomalías" in html
    assert "crash de COVID" in html  # el ejemplo precargado se explica


def test_post_valido_marca_el_evento(client, motor_falso):
    r = client.post("/anomalias", data=FORM_VALIDO)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "datos-grafico" in html
    assert "eventos detectados" in html
    assert "-15,00 %" in html  # la caída inyectada, en la tabla de eventos


def test_post_umbral_invalido(client, motor_falso):
    r = client.post("/anomalias", data=dict(FORM_VALIDO, threshold="cero"))
    assert "El umbral no es un número" in r.get_data(as_text=True)


def test_post_ventana_demasiado_corta(client, motor_falso):
    r = client.post("/anomalias", data=dict(FORM_VALIDO, window="5"))
    assert "al menos 10 sesiones" in r.get_data(as_text=True)


def test_post_sin_ticker(client, motor_falso):
    r = client.post("/anomalias", data=dict(FORM_VALIDO, ticker=""))
    assert "Indica un ticker" in r.get_data(as_text=True)