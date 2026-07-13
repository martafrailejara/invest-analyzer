"""Tests de la página del simulador (sin red: motor sustituido)."""

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
    def run_falso(escenarios, start, end, **kwargs):
        fechas = pd.bdate_range(start, end)
        resultados = []
        for sc in escenarios:
            precios = pd.DataFrame(
                {t: [100.0 + i for i in range(len(fechas))] for t in sc.weights}, index=fechas
            )
            resultados.append((sc, engine.run_backtest(precios, Strategy(
                weights=sc.weights,
                initial_investment=sc.initial_investment,
                monthly_contribution=sc.monthly_contribution,
                rebalance_freq=sc.rebalance_freq,
            ))))
        return resultados

    import modules.simulator

    monkeypatch.setattr(modules.simulator, "run", run_falso)


FORM_VALIDO = {
    "start": "2024-01-01", "end": "2024-12-31",
    "nombre_a": "Aportación única", "ticker_a_0": "AAA", "peso_a_0": "100",
    "ticker_a_1": "", "peso_a_1": "", "inicial_a": "10000", "mensual_a": "0", "rebalance_a": "",
    "nombre_b": "DCA 12 meses", "ticker_b_0": "AAA", "peso_b_0": "100",
    "ticker_b_1": "", "peso_b_1": "", "inicial_b": "0", "mensual_b": "833,33", "rebalance_b": "",
    "nombre_c": "", "ticker_c_0": "", "peso_c_0": "",
    "ticker_c_1": "", "peso_c_1": "", "inicial_c": "", "mensual_c": "", "rebalance_c": "",
}


def test_get_muestra_formulario(client):
    r = client.get("/simulador")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Comparar escenarios" in html
    assert "DCA 12 meses" in html  # ejemplo del documento precargado
    assert "Fase 4" not in html    # ya no es placeholder


def test_post_valido_compara_dos_escenarios(client, motor_falso):
    r = client.post("/simulador", data=FORM_VALIDO)
    html = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "datos-grafico" in html
    assert "Aportación única" in html and "DCA 12 meses" in html
    assert "Máx. drawdown" in html


def test_post_con_escenario_c(client, motor_falso):
    datos = dict(FORM_VALIDO, nombre_c="Mixto", ticker_c_0="BBB", peso_c_0="100",
                 inicial_c="5000", mensual_c="0")
    r = client.post("/simulador", data=datos)
    assert "Mixto" in r.get_data(as_text=True)


def test_post_escenario_c_vacio_se_ignora(client, motor_falso):
    r = client.post("/simulador", data=FORM_VALIDO)
    html = r.get_data(as_text=True)
    # el gráfico solo lleva las series A y B
    assert "--chart-esc-b" in html
    assert "--chart-esc-c" not in html.split("datos-grafico")[1]


def test_post_pesos_incorrectos_en_un_escenario(client, motor_falso):
    datos = dict(FORM_VALIDO, peso_b_0="70")
    r = client.post("/simulador", data=datos)
    html = r.get_data(as_text=True)
    assert "Escenario B" in html and "deben sumar 100" in html
    assert "datos-grafico" not in html


def test_post_sin_aportaciones(client, motor_falso):
    datos = dict(FORM_VALIDO, inicial_a="0", mensual_a="0")
    r = client.post("/simulador", data=datos)
    assert "alguna aportación debe ser mayor que 0" in r.get_data(as_text=True)


def test_post_fecha_final_futura_se_recorta_con_aviso(client, motor_falso):
    """Una fecha final en el futuro (p. ej. 2056 por errata) no se acepta en
    silencio: se recorta a hoy y se muestra el aviso junto a los resultados."""
    datos = dict(FORM_VALIDO, start="2025-07-13", end="2056-07-06")
    r = client.post("/simulador", data=datos)
    html = r.get_data(as_text=True)
    assert "el rango se recorta" in html
    assert "datos-grafico" in html  # la simulación corre igualmente, hasta hoy


def test_inputs_de_fecha_limitados_a_hoy(client):
    from datetime import date

    html = client.get("/simulador").get_data(as_text=True)
    assert f'max="{date.today().isoformat()}"' in html


def test_post_meses_invalidos(client, motor_falso):
    datos = dict(FORM_VALIDO, meses_b="cero")
    r = client.post("/simulador", data=datos)
    assert "no son un número entero" in r.get_data(as_text=True)
