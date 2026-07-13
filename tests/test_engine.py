"""Motor de simulación verificado contra escenarios calculados a mano."""

import math

import pandas as pd
import pytest

from core import engine
from core.engine import Strategy


def precios(datos: dict, fechas) -> pd.DataFrame:
    return pd.DataFrame(datos, index=pd.DatetimeIndex(fechas), dtype="float64")


def test_buy_and_hold_sigue_al_precio():
    px = precios({"A": [50, 60, 40, 80]},
                 ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"])
    res = engine.run_backtest(px, Strategy.buy_and_hold({"A": 1.0}, 1000))

    # 20 unidades a 50: el valor replica el precio
    assert res.value.tolist() == pytest.approx([1000, 1200, 800, 1600])
    assert res.invested.iloc[-1] == pytest.approx(1000)
    m = res.metrics()
    assert m["final_value"] == pytest.approx(1600)
    assert m["profit"] == pytest.approx(600)
    # pico 1200, valle 800
    assert m["max_drawdown"] == pytest.approx(800 / 1200 - 1)


def test_dca_precio_constante_no_gana_ni_pierde():
    fechas = pd.bdate_range("2024-01-01", "2024-03-29")
    px = precios({"A": [100.0] * len(fechas)}, fechas)
    res = engine.run_backtest(px, Strategy.dca({"A": 1.0}, monthly_contribution=300))

    # 3 aportaciones mensuales (ene, feb, mar)
    assert res.invested.iloc[-1] == pytest.approx(900)
    assert res.value.iloc[-1] == pytest.approx(900)
    assert (res.returns == 0).all()
    m = res.metrics()
    assert m["profit"] == pytest.approx(0)
    assert m["max_drawdown"] == pytest.approx(0)
    assert math.isnan(m["sharpe"])


def test_dca_calculado_a_mano():
    # ene: compra 1 ud a 100; feb: compra 100/110 uds a 110; cierre a 121
    px = precios(
        {"A": [100, 110, 110, 121]},
        ["2024-01-01", "2024-01-15", "2024-02-01", "2024-02-15"],
    )
    res = engine.run_backtest(px, Strategy.dca({"A": 1.0}, monthly_contribution=100))

    unidades_finales = 1 + 100 / 110
    assert res.value.iloc[-1] == pytest.approx(unidades_finales * 121)  # 231.0
    assert res.invested.iloc[-1] == pytest.approx(200)

    # retornos time-weighted: +10%, 0% (día de aportación), +10%
    assert res.returns.tolist() == pytest.approx([0.10, 0.0, 0.10])
    # el índice TWR acumula 1.21 aunque el "profit" en euros sea solo 31
    assert res.twr_index().iloc[-1] == pytest.approx(1.21)


def test_rebalanceo_anual_calculado_a_mano():
    fechas = ["2024-12-30", "2024-12-31", "2025-01-02", "2025-01-03"]
    px = precios({"A": [100, 200, 200, 200], "B": [100, 100, 100, 200]}, fechas)
    pesos = {"A": 0.5, "B": 0.5}

    # sin rebalanceo: 5A + 5B -> 5*200 + 5*200 = 2000
    sin = engine.run_backtest(px, Strategy.buy_and_hold(pesos, 1000))
    assert sin.value.iloc[-1] == pytest.approx(2000)

    # con rebalanceo el 2025-01-02 (V=1500 -> 750/750 = 3.75A + 7.5B):
    # 3.75*200 + 7.5*200 = 2250
    con = engine.run_backtest(
        px, Strategy(weights=pesos, initial_investment=1000, rebalance_freq="Y")
    )
    assert con.value.iloc[-1] == pytest.approx(2250)
    # el rebalanceo en sí no crea ni destruye valor ese día
    assert con.value.loc["2025-01-02"] == pytest.approx(1500)


def test_huecos_de_precio_se_rellenan_y_cabecera_nan_se_descarta():
    fechas = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"]
    px = precios(
        {"A": [float("nan"), 100, 100, 100], "B": [50, 50, float("nan"), 60]},
        fechas,
    )
    # el recorte del inicio debe avisarse, no ocurrir en silencio
    with pytest.warns(UserWarning, match="la simulación empieza el 2024-01-02"):
        res = engine.run_backtest(px, Strategy.buy_and_hold({"A": 0.5, "B": 0.5}, 1000))

    # el primer día (A sin histórico) se descarta
    assert res.value.index[0] == pd.Timestamp("2024-01-02")
    # el hueco de B el día 3 se rellena con 50 -> valor sin cambios
    assert res.value.loc["2024-01-03"] == pytest.approx(1000)
    # día 4: B sube de 50 a 60 -> la mitad de la cartera gana 20%
    assert res.value.iloc[-1] == pytest.approx(1100)


def test_validaciones():
    px = precios({"A": [100, 110]}, ["2024-01-01", "2024-01-02"])

    with pytest.raises(ValueError, match="deben sumar 1"):
        engine.run_backtest(px, Strategy.buy_and_hold({"A": 0.8}, 1000))
    with pytest.raises(ValueError, match="no incluyen columnas"):
        engine.run_backtest(px, Strategy.buy_and_hold({"A": 0.5, "Z": 0.5}, 1000))
    px_dos = precios({"A": [100, 110], "B": [50, 55]}, ["2024-01-01", "2024-01-02"])
    with pytest.raises(ValueError, match="pesos negativos"):
        engine.run_backtest(
            px_dos, Strategy.buy_and_hold({"A": 1.5, "B": -0.5}, 1000)
        )
    with pytest.raises(ValueError, match="no invierte nada"):
        engine.run_backtest(px, Strategy(weights={"A": 1.0}))
    with pytest.raises(ValueError, match="rebalance_freq"):
        engine.run_backtest(
            px, Strategy(weights={"A": 1.0}, initial_investment=1, rebalance_freq="W")
        )


def test_backtester_modulo_usa_capa_de_datos(tmp_path):
    """El módulo backtester encadena get_prices (con su caché) y el motor."""
    from modules import backtester

    def downloader(ticker, start, end):
        fechas = pd.bdate_range(start, end)
        return pd.Series([100.0 + i for i in range(len(fechas))], index=fechas)

    res = backtester.run(
        {"AAA": 1.0}, "2024-01-01", "2024-02-01",
        initial_investment=1000,
        cache_dir=tmp_path, downloader=downloader,
    )
    assert res.value.iloc[-1] > 1000  # el precio sintético siempre sube
    assert res.metrics()["max_drawdown"] == pytest.approx(0.0)


def test_aportacion_limitada_a_n_meses():
    """DCA de 3 meses en un rango de 6: solo se aporta en los 3 primeros."""
    fechas = pd.bdate_range("2024-01-01", "2024-06-28")
    px = precios({"A": [100.0] * len(fechas)}, fechas)
    res = engine.run_backtest(
        px, Strategy(weights={"A": 1.0}, monthly_contribution=100, contribution_months=3)
    )
    assert res.invested.iloc[-1] == pytest.approx(300)
    # sin límite habrían sido 6 aportaciones
    sin_limite = engine.run_backtest(px, Strategy.dca({"A": 1.0}, monthly_contribution=100))
    assert sin_limite.invested.iloc[-1] == pytest.approx(600)


def test_contribution_months_invalido():
    px = precios({"A": [100, 110]}, ["2024-01-01", "2024-01-02"])
    with pytest.raises(ValueError, match="al menos 1"):
        engine.run_backtest(
            px, Strategy(weights={"A": 1.0}, monthly_contribution=100, contribution_months=0)
        )
