"""Análisis de riesgo verificado contra propiedades y correlaciones conocidas."""

import numpy as np
import pandas as pd
import pytest

from modules import risk


def precios_desde_retornos(retornos: dict) -> pd.DataFrame:
    n = len(next(iter(retornos.values())))
    fechas = pd.bdate_range("2022-01-03", periods=n + 1)
    df = {}
    for t, rets in retornos.items():
        p = [100.0]
        for r in rets:
            p.append(p[-1] * (1 + r))
        df[t] = p
    return pd.DataFrame(df, index=fechas)


def test_correlacion_perfecta_y_negativa():
    rng = np.random.default_rng(0)
    base = rng.normal(0.0005, 0.01, 200)
    px = precios_desde_retornos({
        "A": list(base),
        "B": list(base * 1.5),      # perfectamente correlado con A
        "C": list(-base),           # perfectamente anticorrelado
    })
    res = risk.analyze(px, {"A": 1, "B": 1, "C": 1}, benchmark=None)

    tickers = res["correlaciones"]["tickers"]
    m = {(tickers[i], tickers[j]): res["correlaciones"]["valores"][i][j]
         for i in range(3) for j in range(3)}
    assert m[("A", "A")] == pytest.approx(1.0)
    assert m[("A", "B")] == pytest.approx(1.0, abs=1e-6)
    assert m[("A", "C")] == pytest.approx(-1.0, abs=1e-6)


def test_beta_frente_a_benchmark():
    rng = np.random.default_rng(1)
    idx = rng.normal(0.0004, 0.01, 200)
    px = precios_desde_retornos({"CARTERA": list(idx * 1.5), "SPY": list(idx)})
    res = risk.analyze(px, {"CARTERA": 1.0}, benchmark="SPY")
    assert res["cartera"]["beta"] == pytest.approx(1.5, abs=0.02)
    assert res["benchmark"]["nombre"] == "SPY"
    assert res["benchmark"]["beta"] is None  # el índice no tiene beta contra sí mismo


def test_var_y_cvar_presentes_y_ordenados():
    rng = np.random.default_rng(2)
    px = precios_desde_retornos({"A": list(rng.normal(0.0005, 0.02, 300))})
    res = risk.analyze(px, {"A": 1.0}, benchmark=None)
    c = res["cartera"]
    assert c["var_95"] < 0
    assert c["cvar_95"] <= c["var_95"]  # la cola es peor que el umbral
    assert c["sortino"] is not None


def test_sin_benchmark_beta_es_none():
    rng = np.random.default_rng(3)
    px = precios_desde_retornos({"A": list(rng.normal(0.0005, 0.01, 100))})
    res = risk.analyze(px, {"A": 1.0}, benchmark=None)
    assert res["cartera"]["beta"] is None
    assert res["benchmark"] is None


def test_historico_insuficiente():
    px = precios_desde_retornos({"A": [0.01] * 20, "B": [0.02] * 20})
    with pytest.raises(ValueError, match="Histórico insuficiente"):
        risk.analyze(px, {"A": 0.5, "B": 0.5}, benchmark=None)
