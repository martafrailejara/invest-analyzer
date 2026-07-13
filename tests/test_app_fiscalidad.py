"""Tests de la página de fiscalidad (con el fixture sintético, sin red)."""

from pathlib import Path

import pytest

from app import create_app

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def client(monkeypatch):
    from app import taxes_web

    monkeypatch.setattr(taxes_web, "CSV_REAL", FIXTURES / "transacciones_sintetico.csv")
    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_get_muestra_lotes_y_realizadas(client):
    r = client.get("/fiscalidad")
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "no asesoría fiscal" in html
    assert "Lotes vivos en cartera" in html
    assert "Plusvalía realizada" in html
    assert "58,50 €" in html  # la venta del fixture, FIFO a mano


def test_post_simula_venta_con_precio_manual(client):
    r = client.post("/fiscalidad", data={"symbol": "XX0000000001",
                                         "unidades": "8", "precio": "30"})
    html = r.get_data(as_text=True)
    # plusvalía 129,50 y cuota al 19%
    assert "129,50 €" in html
    assert "24,61 €" in html
    assert "Lotes consumidos" in html


def test_post_unidades_de_mas(client):
    r = client.post("/fiscalidad", data={"symbol": "XX0000000001",
                                         "unidades": "999", "precio": "30"})
    assert "Solo hay" in r.get_data(as_text=True)
