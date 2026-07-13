"""Tests de la página del chequeo (sin red: motor y config sustituidos)."""

import pytest

from app import create_app
from core import config
from modules import checkup


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUTA", tmp_path / "config.json")
    from app import checkup_web

    csv = tmp_path / "transacciones.csv"
    csv.write_text("existe")  # solo se comprueba la existencia
    monkeypatch.setattr(checkup_web, "CSV_REAL", csv)
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def resultado_falso():
    return {
        "hallazgos": [
            {"severidad": "aviso", "regla": "Concentración",
             "titulo": "BTC-EUR concentra el 72.0 % de la cartera",
             "detalle": "Por encima del umbral."},
        ],
        "correctos": ["Ninguna compra pagó más del 1 % en comisiones."],
        "posiciones": [
            {"symbol": "ISIN1", "ticker": "AAA.DE", "name": "ETF A", "peso": 0.28, "valor": 280.0},
            {"symbol": "BTC", "ticker": "BTC-EUR", "name": "Bitcoin", "peso": 0.72, "valor": 720.0},
        ],
        "valor_total": 1000.0,
    }


def test_chequeo_muestra_hallazgos(client, monkeypatch):
    monkeypatch.setattr(checkup, "run", lambda csv, **kw: resultado_falso())
    r = client.get("/chequeo")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "No es asesoramiento profesional" in html
    assert "concentra el 72.0" in html
    assert "correcto" in html
    assert "Pesos objetivo" in html  # el formulario está


def test_guardar_objetivos_validos(client, monkeypatch):
    monkeypatch.setattr(checkup, "run", lambda csv, **kw: resultado_falso())
    r = client.post("/chequeo/objetivos", data={"obj_ISIN1": "80", "obj_BTC": "20"},
                    follow_redirects=True)
    assert "guardados" in r.get_data(as_text=True)
    assert config.get("objetivos") == {"ISIN1": 0.8, "BTC": 0.2}


def test_objetivos_que_no_suman_100_no_se_guardan(client, monkeypatch):
    monkeypatch.setattr(checkup, "run", lambda csv, **kw: resultado_falso())
    r = client.post("/chequeo/objetivos", data={"obj_ISIN1": "80", "obj_BTC": "80"},
                    follow_redirects=True)
    assert "deben sumar 100" in r.get_data(as_text=True)
    assert config.get("objetivos") is None


def test_objetivos_vacios_borran(client, monkeypatch):
    monkeypatch.setattr(checkup, "run", lambda csv, **kw: resultado_falso())
    config.set("objetivos", {"ISIN1": 1.0})
    r = client.post("/chequeo/objetivos", data={"obj_ISIN1": ""}, follow_redirects=True)
    assert "borrados" in r.get_data(as_text=True)
    assert config.get("objetivos") == {}
