"""Optimizador verificado contra propiedades y un caso analítico calculado a mano."""

import numpy as np
import pandas as pd
import pytest

from modules import optimizer


def precios_desde_retornos(retornos: dict) -> pd.DataFrame:
    """Construye precios sintéticos (base 100) a partir de retornos diarios."""
    n = len(next(iter(retornos.values())))
    fechas = pd.bdate_range("2022-01-03", periods=n + 1)
    df = {}
    for ticker, rets in retornos.items():
        precios = [100.0]
        for r in rets:
            precios.append(precios[-1] * (1 + r))
        df[ticker] = precios
    return pd.DataFrame(df, index=fechas)


def test_minima_varianza_caso_analitico():
    """Dos activos incorrelados con var(B) = 4·var(A): el peso de mínima
    varianza es w_A = σ²_B / (σ²_A + σ²_B) = 0.8 (cálculo a mano)."""
    ciclos = 100
    ret_a = [0.01, -0.01, 0.01, -0.01] * ciclos          # σ diaria 1%
    ret_b = [0.02, 0.02, -0.02, -0.02] * ciclos          # σ diaria 2%, incorrelado con A
    res = optimizer.efficient_frontier(precios_desde_retornos({"A": ret_a, "B": ret_b}))

    assert res["min_var"]["weights"]["A"] == pytest.approx(0.8, abs=0.01)
    assert res["min_var"]["weights"]["B"] == pytest.approx(0.2, abs=0.01)


def test_pesos_validos_en_toda_la_frontera():
    rng = np.random.default_rng(7)
    retornos = {t: list(rng.normal(m, s, 300)) for t, m, s in
                [("A", 0.0006, 0.010), ("B", 0.0004, 0.014), ("C", 0.0002, 0.006)]}
    res = optimizer.efficient_frontier(precios_desde_retornos(retornos))

    puntos = res["frontera"] + [res["min_var"], res["max_sharpe"]]
    for punto in puntos:
        pesos = punto["weights"].values()
        assert sum(pesos) == pytest.approx(1.0, abs=1e-3)
        assert all(p >= 0 for p in pesos)  # sin cortos

    # la frontera arranca en mínima varianza: ningún punto tiene menos volatilidad
    assert all(p["vol"] >= res["min_var"]["vol"] - 1e-6 for p in res["frontera"])
    # y el retorno crece a lo largo del barrido
    rets = [p["ret"] for p in res["frontera"]]
    assert rets == sorted(rets)


def test_activo_dominante_se_lleva_el_extremo():
    """El extremo de máximo retorno de la frontera es 100% del activo con más retorno."""
    rng = np.random.default_rng(3)
    retornos = {
        "MEJOR": list(rng.normal(0.0010, 0.010, 300)),
        "PEOR": list(rng.normal(0.0001, 0.010, 300)),
    }
    res = optimizer.efficient_frontier(precios_desde_retornos(retornos))
    extremo = res["frontera"][-1]
    assert extremo["weights"].get("MEJOR", 0) == pytest.approx(1.0, abs=0.01)


def test_historico_insuficiente():
    retornos = {"A": [0.01] * 20, "B": [0.02] * 20}
    with pytest.raises(ValueError, match="Histórico insuficiente"):
        optimizer.efficient_frontier(precios_desde_retornos(retornos))


def test_run_exige_dos_activos(tmp_path):
    with pytest.raises(ValueError, match="al menos dos activos"):
        optimizer.run(["AAA"], "2024-01-01", "2024-12-31", cache_dir=tmp_path)
