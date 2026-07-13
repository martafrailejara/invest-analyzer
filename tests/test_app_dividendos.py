"""Tests de la página de dividendos (sin red: motor sustituido)."""

import pytest

from app import create_app
from modules import dividends


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def resultado_con_dividendos():
    return {
        "posiciones": [{
            "symbol": "IE00B3XXRP09", "name": "S&P 500 Dist", "ticker": "VUSA.AS",
            "shares": 20.0, "cost_total": 1572.0, "cobrado_total": 30.0,
            "cobrado_por_anio": {2024: 12.0, 2025: 18.0},
            "dps_12m": 1.5, "proyeccion": 30.0, "yoc": 0.019,
        }],
        "por_anio": {2024: 12.0, 2025: 18.0},
        "este_anio": 18.0,
        "cobrado_total": 30.0,
        "proyeccion_total": 30.0,
        "sin_mapear": [],
    }


def resultado_todo_cero():
    return {
        "posiciones": [{
            "symbol": "IE00B5BMR087", "name": "Core S&P 500 (Acc)", "ticker": "SXR8.DE",
            "shares": 0.15, "cost_total": 103.75, "cobrado_total": 0.0,
            "cobrado_por_anio": {}, "dps_12m": 0.0, "proyeccion": 0.0, "yoc": 0.0,
        }],
        "por_anio": {},
        "este_anio": 0.0,
        "cobrado_total": 0.0,
        "proyeccion_total": 0.0,
        "sin_mapear": [],
    }


def test_cartera_con_dividendos(client, monkeypatch):
    monkeypatch.setattr(dividends, "run", lambda csv, **kw: resultado_con_dividendos())
    r = client.get("/dividendos?cartera=ejemplo")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Dividendos cobrados este año" in html
    assert "datos-grafico" in html
    assert "Yield on cost" in html
    assert "VUSA.AS" in html


def test_cartera_sin_dividendos_explica_por_que(client, monkeypatch):
    monkeypatch.setattr(dividends, "run", lambda csv, **kw: resultado_todo_cero())
    r = client.get("/dividendos")
    html = r.get_data(as_text=True)
    assert "no reparten dividendos" in html
    assert "acumulación" in html
    assert "datos-grafico" not in html  # sin años con importes no hay gráfico


def test_sin_csv_muestra_instrucciones(client, monkeypatch):
    from app import dividends_web

    monkeypatch.setattr(dividends_web, "CSV_REAL", dividends_web.RAIZ / "no-existe.csv")
    r = client.get("/dividendos")
    assert "data/transacciones.csv" in r.get_data(as_text=True)


def test_error_de_datos_legible(client, monkeypatch):
    def revienta(csv, **kw):
        raise ValueError("El CSV no parece un export de transacciones de Trade Republic")

    monkeypatch.setattr(dividends, "run", revienta)
    r = client.get("/dividendos")
    assert "no parece un export" in r.get_data(as_text=True)
