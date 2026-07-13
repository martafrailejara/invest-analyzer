"""Tests de la página del optimizador (sin red: motor sustituido)."""

import pandas as pd
import pytest

from app import create_app
from modules import optimizer


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def motor_falso(monkeypatch):
    """Optimiza de verdad (scipy) pero sobre precios sintéticos, sin red."""

    def run_falso(tickers, start, end, **kwargs):
        fechas = pd.bdate_range(start, periods=300)
        precios = pd.DataFrame({
            t: [100 * (1 + 0.0003 * (i + 1)) ** k * (1 + (0.01 if (k + i) % 2 else -0.009))
                for k in range(300)]
            for i, t in enumerate(tickers)
        }, index=fechas)
        return optimizer.efficient_frontier(precios, n_points=10,
                                            target_vol=kwargs.get("target_vol"))

    monkeypatch.setattr(optimizer, "run", run_falso)


FORM_VALIDO = {
    "ticker_0": "AAA", "ticker_1": "BBB", "ticker_2": "", "ticker_3": "",
    "start": "2023-01-01", "end": "2024-06-01",
}


def test_get_muestra_formulario(client):
    r = client.get("/optimizador")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Calcular frontera" in html
    assert "Fase 5" not in html  # ya no es placeholder


def test_post_valido_muestra_frontera(client, motor_falso):
    r = client.post("/optimizador", data=FORM_VALIDO)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "datos-grafico" in html
    assert "Mínima varianza" in html
    assert "Máximo Sharpe" in html
    assert "puntos de la frontera" in html


def test_post_un_solo_activo(client, motor_falso):
    datos = dict(FORM_VALIDO, ticker_1="", ticker_2="", ticker_3="")
    r = client.post("/optimizador", data=datos)
    assert "al menos dos activos" in r.get_data(as_text=True)


def test_post_activos_duplicados_cuentan_una_vez(client, motor_falso):
    datos = dict(FORM_VALIDO, ticker_1="AAA")
    r = client.post("/optimizador", data=datos)
    assert "al menos dos activos" in r.get_data(as_text=True)


def test_post_con_volatilidad_objetivo(client, motor_falso):
    r = client.post("/optimizador", data=dict(FORM_VALIDO, vol_objetivo="15"))
    html = r.get_data(as_text=True)
    assert "Con volatilidad" in html or "no alcanzable" in html


def test_post_volatilidad_objetivo_invalida(client, motor_falso):
    r = client.post("/optimizador", data=dict(FORM_VALIDO, vol_objetivo="abc"))
    assert "no es un número" in r.get_data(as_text=True)
