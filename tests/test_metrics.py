"""Métricas verificadas contra casos calculados a mano."""

import math

import pandas as pd
import pytest

from core import metrics


def serie(valores, fechas):
    return pd.Series(valores, index=pd.DatetimeIndex(fechas), dtype="float64")


def test_simple_returns():
    precios = serie([100, 110, 99], ["2024-01-01", "2024-01-02", "2024-01-03"])
    r = metrics.simple_returns(precios)
    assert r.tolist() == pytest.approx([0.10, -0.10])


def test_log_returns():
    precios = serie([100, 110, 99], ["2024-01-01", "2024-01-02", "2024-01-03"])
    r = metrics.log_returns(precios)
    assert r.tolist() == pytest.approx([math.log(1.1), math.log(0.9)])


def test_cumulative_return():
    precios = serie([100, 110, 99], ["2024-01-01", "2024-01-02", "2024-01-03"])
    # 100 -> 99: -1%
    assert metrics.cumulative_return(precios) == pytest.approx(-0.01)


def test_cagr_dos_anios():
    # 100 -> 121 en dos años (21% total) debe dar ~10% anual compuesto
    precios = serie([100, 121], ["2020-01-01", "2022-01-01"])
    assert metrics.cagr(precios) == pytest.approx(0.0999, abs=1e-3)


def test_cagr_un_solo_dia_error():
    precios = serie([100, 105], ["2024-01-01", "2024-01-01"])
    with pytest.raises(ValueError, match="dos fechas distintas"):
        metrics.cagr(precios)


def test_max_drawdown():
    # pico en 120, valle en 60: caída del 50%
    valores = serie(
        [100, 120, 60, 90, 130],
        ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
    )
    assert metrics.max_drawdown(valores) == pytest.approx(-0.5)


def test_max_drawdown_serie_creciente_es_cero():
    valores = serie([100, 110, 120], ["2024-01-01", "2024-01-02", "2024-01-03"])
    assert metrics.max_drawdown(valores) == pytest.approx(0.0)


def test_annualized_volatility():
    # std muestral de [0.01, -0.01, 0.01, -0.01]: media 0,
    # var = 4*0.0001/3 -> std = 0.0115470
    r = serie([0.01, -0.01, 0.01, -0.01],
              ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"])
    esperado = 0.0115470 * math.sqrt(252)
    assert metrics.annualized_volatility(r) == pytest.approx(esperado, rel=1e-4)


def test_sharpe_ratio_sin_tasa_libre():
    # retornos [0.02, 0.0]: media 0.01, std muestral 0.0141421
    r = serie([0.02, 0.0], ["2024-01-01", "2024-01-02"])
    esperado = (0.01 / 0.0141421) * math.sqrt(252)
    assert metrics.sharpe_ratio(r) == pytest.approx(esperado, rel=1e-4)


def test_sharpe_ratio_baja_con_tasa_libre():
    r = serie([0.02, 0.0, 0.01], ["2024-01-01", "2024-01-02", "2024-01-03"])
    assert metrics.sharpe_ratio(r, risk_free_annual=0.03) < metrics.sharpe_ratio(r)


def test_sharpe_ratio_sin_dispersion_es_nan():
    r = serie([0.01, 0.01, 0.01], ["2024-01-01", "2024-01-02", "2024-01-03"])
    assert math.isnan(metrics.sharpe_ratio(r))


def test_downside_deviation():
    # retornos [0.02, -0.01, 0.03, -0.02]: solo cuentan -0.01 y -0.02
    # media de cuadrados = (0 + 0.0001 + 0 + 0.0004)/4 = 0.000125 -> sqrt
    r = serie([0.02, -0.01, 0.03, -0.02],
              ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04"])
    assert metrics.downside_deviation(r) == pytest.approx(math.sqrt(0.000125))


def test_sortino_mayor_que_sharpe_con_cola_positiva():
    # una serie con más dispersión al alza que a la baja: Sortino > Sharpe
    r = serie([0.05, -0.01, 0.04, -0.01, 0.06],
              ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    assert metrics.sortino_ratio(r) > metrics.sharpe_ratio(r)


def test_value_at_risk_historico():
    # 20 retornos: -0.10..0.09; el cuantil 5% cae en el peor extremo
    r = serie([(-10 + i) / 100 for i in range(20)],
              [f"2024-01-{d:02d}" for d in range(1, 21)])
    # np.quantile con 5% sobre 20 puntos interpola cerca de -0.10
    assert metrics.value_at_risk(r, level=0.05) == pytest.approx(-0.0905, abs=1e-4)


def test_cvar_peor_que_var():
    r = serie([(-10 + i) / 100 for i in range(20)],
              [f"2024-01-{d:02d}" for d in range(1, 21)])
    var = metrics.value_at_risk(r, level=0.10)
    cvar = metrics.conditional_var(r, level=0.10)
    assert cvar <= var  # la media de la cola es aún más negativa


def test_beta_calculada_a_mano():
    # cartera = 2 × índice exactamente -> beta = 2
    indice = serie([0.01, -0.02, 0.03, -0.01, 0.02],
                   ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"])
    cartera = indice * 2
    assert metrics.beta(cartera, indice) == pytest.approx(2.0)
    # sin correlación con el índice -> beta ~ 0 no se garantiza, pero
    # un activo idéntico al índice tiene beta 1
    assert metrics.beta(indice, indice) == pytest.approx(1.0)
