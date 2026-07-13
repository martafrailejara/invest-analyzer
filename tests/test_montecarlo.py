"""Monte Carlo verificado contra propiedades y un caso determinista."""

import numpy as np
import pandas as pd
import pytest

from modules import montecarlo


def precios_con_retorno(mensual: float, meses: int = 60) -> pd.DataFrame:
    """Precios diarios cuyo retorno mensual compuesto es ~`mensual` constante."""
    fechas = pd.bdate_range("2015-01-01", periods=meses * 21)
    diario = (1 + mensual) ** (1 / 21) - 1
    serie = 100 * (1 + diario) ** np.arange(len(fechas))
    return pd.DataFrame({"A": serie}, index=fechas)


def precios_mensuales(mensual: float, meses: int = 60) -> pd.DataFrame:
    """Un precio por mes creciendo un `mensual` constante: el retorno mensual
    de calendario es idéntico en todos los meses, por construcción."""
    fechas = pd.date_range("2015-01-01", periods=meses, freq="MS")
    serie = 100.0 * (1 + mensual) ** np.arange(meses)
    return pd.DataFrame({"A": serie}, index=fechas)


def test_retorno_constante_es_determinista():
    """Si todos los meses históricos rinden lo mismo, el bootstrap no tiene
    varianza: todos los percentiles del valor terminal coinciden."""
    px = precios_mensuales(0.01, meses=60)
    res = montecarlo.project(px, {"A": 1.0}, years=2, initial=1000,
                             monthly_contribution=0, n_sims=200, seed=1)

    terminales = [res["terminal"][p] for p in montecarlo.PERCENTILES]
    assert terminales == pytest.approx([terminales[0]] * len(terminales), rel=1e-9)
    assert res["ret_mensual_medio"] == pytest.approx(0.01, abs=1e-9)
    assert res["terminal"][50] == pytest.approx(1000 * 1.01 ** 24, rel=1e-6)
    assert res["prob_ganancia"] == pytest.approx(1.0)


def test_percentiles_ordenados_y_bandas_crecen():
    rng = np.random.default_rng(0)
    fechas = pd.bdate_range("2015-01-01", periods=252 * 5)
    serie = 100 * np.cumprod(1 + rng.normal(0.0004, 0.01, len(fechas)))
    px = pd.DataFrame({"A": serie}, index=fechas)
    res = montecarlo.project(px, {"A": 1.0}, years=10, initial=0,
                             monthly_contribution=100, n_sims=500, seed=42)

    # en cada mes p10 <= p25 <= p50 <= p75 <= p90
    bandas = res["bandas"]
    for i in range(res["meses"] + 1):
        fila = [bandas[p][i] for p in montecarlo.PERCENTILES]
        assert fila == sorted(fila)
    # la mediana terminal supera lo aportado con deriva positiva
    assert res["terminal"][50] > res["aportado"]
    assert 0 <= res["prob_ganancia"] <= 1


def test_reproducible_con_semilla():
    px = precios_con_retorno(0.005, meses=48)
    a = montecarlo.project(px, {"A": 1.0}, years=5, monthly_contribution=200, n_sims=300, seed=7)
    b = montecarlo.project(px, {"A": 1.0}, years=5, monthly_contribution=200, n_sims=300, seed=7)
    assert a["terminal"] == b["terminal"]


def test_aportado_incluye_inicial_y_mensual():
    px = precios_con_retorno(0.003, meses=48)
    res = montecarlo.project(px, {"A": 1.0}, years=10, initial=5000,
                             monthly_contribution=150, n_sims=100, seed=1)
    assert res["aportado"] == pytest.approx(5000 + 150 * 120)


def test_validaciones():
    px = precios_con_retorno(0.01, meses=48)
    with pytest.raises(ValueError, match="al menos 1 año"):
        montecarlo.project(px, {"A": 1.0}, years=0, initial=1000)
    with pytest.raises(ValueError, match="aportación inicial o mensual"):
        montecarlo.project(px, {"A": 1.0}, years=5, initial=0, monthly_contribution=0)
    with pytest.raises(ValueError, match="Histórico insuficiente"):
        montecarlo.project(precios_con_retorno(0.01, meses=12), {"A": 1.0}, years=5, initial=1000)
