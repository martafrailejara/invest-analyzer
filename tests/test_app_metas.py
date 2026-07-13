"""Tests de la página de metas (sin red: motor y config sustituidos)."""

import pytest

from app import create_app
from core import config
from modules import goals


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RUTA", tmp_path / "config.json")
    from app import goals_web

    csv = tmp_path / "transacciones.csv"
    csv.write_text("existe")
    monkeypatch.setattr(goals_web, "CSV_REAL", csv)
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def resultado_falso(**params):
    return {
        "valor_actual": 206.56,
        "importe_objetivo": params.get("importe_objetivo", 100000),
        "anio_objetivo": params.get("anio_objetivo", 2040),
        "anios": 14,
        "aportacion_mensual": params.get("aportacion_mensual", 200),
        "progreso": 0.002,
        "variantes": [
            {"factor": 0.5, "aportacion": 100, "prob": 0.12, "mediana": 60000},
            {"factor": 1.0, "aportacion": 200, "prob": 0.44, "mediana": 95000},
            {"factor": 1.5, "aportacion": 300, "prob": 0.71, "mediana": 130000},
            {"factor": 2.0, "aportacion": 400, "prob": 0.88, "mediana": 165000},
        ],
        "proyeccion": None,
        "meses_historico": 120,
    }


def test_get_muestra_formulario(client):
    r = client.get("/metas")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Calcular probabilidad" in html


def test_post_muestra_probabilidad_y_variantes(client, monkeypatch):
    monkeypatch.setattr(goals, "run", lambda csv, **kw: resultado_falso(**kw))
    r = client.post("/metas", data={"importe": "100000", "anio": "2040", "mensual": "200"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "44,00 %" in html          # probabilidad base
    assert "progreso-barra" in html
    assert html.count("<tr") >= 5      # cabecera + 4 variantes
    # la meta queda guardada para la próxima visita
    assert config.get("meta")["importe"] == 100000.0


def test_post_anio_invalido(client, monkeypatch):
    def revienta(csv, **kw):
        raise ValueError("El año objetivo debe quedar entre 1 y 60 años vista")

    monkeypatch.setattr(goals, "run", revienta)
    r = client.post("/metas", data={"importe": "1000", "anio": "2026", "mensual": "0"})
    assert "año objetivo" in r.get_data(as_text=True)
