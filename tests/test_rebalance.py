"""Plan de rebalanceo verificado contra casos calculados a mano."""

import pytest

from modules import rebalance

POSICIONES = [
    {"symbol": "A", "ticker": "AAA.DE", "valor": 700.0, "peso": 0.7, "precio_actual": 70.0},
    {"symbol": "B", "ticker": "BBB.DE", "valor": 300.0, "peso": 0.3, "precio_actual": 30.0},
]
OBJETIVOS = {"A": 0.5, "B": 0.5}


def test_ordenes_clasicas_a_mano():
    """70/30 hacia 50/50 con 1000 €: vender 200 de A y comprar 200 de B."""
    ordenes = rebalance.ordenes_clasicas(POSICIONES, OBJETIVOS, 1000.0)
    assert len(ordenes) == 2
    venta = next(o for o in ordenes if o["symbol"] == "A")
    compra = next(o for o in ordenes if o["symbol"] == "B")
    assert venta["accion"] == "vender"
    assert venta["importe"] == pytest.approx(200.0)
    assert venta["unidades"] == pytest.approx(200 / 70)
    assert compra["accion"] == "comprar"
    assert compra["importe"] == pytest.approx(200.0)


def test_orden_minuscula_se_omite():
    casi = [
        {"symbol": "A", "ticker": "AAA.DE", "valor": 500.4, "peso": 0.5004, "precio_actual": 50.0},
        {"symbol": "B", "ticker": "BBB.DE", "valor": 499.6, "peso": 0.4996, "precio_actual": 50.0},
    ]
    assert rebalance.ordenes_clasicas(casi, OBJETIVOS, 1000.0) == []


def test_aportacion_dirigida_insuficiente():
    """Con 200 € y déficit solo en B (300 €), todo va a B."""
    plan = rebalance.aportacion_dirigida(POSICIONES, OBJETIVOS, 1000.0, 200.0)
    assert len(plan) == 1
    assert plan[0]["symbol"] == "B"
    assert plan[0]["importe"] == pytest.approx(200.0)
    # B pasa de 300/1000 a 500/1200 = 41,7 %: converge hacia el 50 %
    assert plan[0]["peso_resultante"] == pytest.approx(500 / 1200)


def test_aportacion_dirigida_alcanza_el_objetivo():
    """Con 1000 € (déficits A=300, B=700 sobre 2000): reparto exacto y 50/50."""
    plan = rebalance.aportacion_dirigida(POSICIONES, OBJETIVOS, 1000.0, 1000.0)
    a = next(o for o in plan if o["symbol"] == "A")
    b = next(o for o in plan if o["symbol"] == "B")
    assert a["importe"] == pytest.approx(300.0)
    assert b["importe"] == pytest.approx(700.0)
    assert a["peso_resultante"] == pytest.approx(0.5)
    assert b["peso_resultante"] == pytest.approx(0.5)


def test_aportacion_sobrante_se_reparte_por_objetivos():
    """Déficit total 1000; con 1400 €, los 400 extra van 50/50."""
    plan = rebalance.aportacion_dirigida(POSICIONES, OBJETIVOS, 1000.0, 1400.0)
    a = next(o for o in plan if o["symbol"] == "A")
    b = next(o for o in plan if o["symbol"] == "B")
    # déficits sobre 2400: A = 1200-700 = 500, B = 1200-300 = 900; total 1400 = aportación
    assert a["importe"] + b["importe"] == pytest.approx(1400.0)
    assert a["peso_resultante"] == pytest.approx(0.5)


def test_run_sin_objetivos():
    with pytest.raises(ValueError, match="pesos objetivo"):
        rebalance.run("no-importa.csv", {})
