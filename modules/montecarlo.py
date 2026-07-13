"""Proyección Monte Carlo: abanico de escenarios futuros de una cartera.

Método: bootstrap de los retornos mensuales históricos de la cartera. Cada
simulación reordena al azar (con reemplazo) meses reales del histórico, así
que conserva la distribución empírica —incluidas colas gruesas— sin asumir
normalidad. Sobre cada camino se aplican las aportaciones mensuales.

Es descriptivo y explícitamente incierto: proyecta la distribución de lo que
*habría pasado* si el futuro se pareciese al pasado, no una predicción.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import market_data, metrics

MIN_MESES_HISTORICO = 24
PERCENTILES = (10, 25, 50, 75, 90)


def run(
    weights,
    start,
    end,
    *,
    years: int = 20,
    monthly_contribution: float = 0.0,
    initial: float = 0.0,
    n_sims: int = 1000,
    seed: int | None = None,
    cache_dir=None,
    downloader=None,
) -> dict:
    """Proyección Monte Carlo sobre precios reales (con caché local)."""
    prices = market_data.get_prices(list(weights), start, end,
                                    cache_dir=cache_dir, downloader=downloader)
    return project(prices, weights, years=years, monthly_contribution=monthly_contribution,
                   initial=initial, n_sims=n_sims, seed=seed)


def project(
    prices: pd.DataFrame,
    weights,
    *,
    years: int = 20,
    monthly_contribution: float = 0.0,
    initial: float = 0.0,
    n_sims: int = 1000,
    seed: int | None = None,
    objetivo: float | None = None,
) -> dict:
    if years < 1:
        raise ValueError("El horizonte debe ser de al menos 1 año")
    if initial == 0 and monthly_contribution == 0:
        raise ValueError("Indica una aportación inicial o mensual mayor que 0")
    pesos = _normaliza_pesos(weights, prices)

    diarios = metrics.simple_returns(prices[list(pesos)].sort_index().ffill().dropna())
    cartera_diaria = (diarios * pd.Series(pesos)).sum(axis=1)
    # retornos mensuales de la cartera compuestos a partir de los diarios
    mensuales = (1 + cartera_diaria).groupby(cartera_diaria.index.to_period("M")).prod() - 1
    if len(mensuales) < MIN_MESES_HISTORICO:
        raise ValueError(
            f"Histórico insuficiente: {len(mensuales)} meses con datos comunes "
            f"(mínimo {MIN_MESES_HISTORICO})"
        )

    meses = years * 12
    muestra = mensuales.to_numpy()
    rng = np.random.default_rng(seed)
    sorteos = rng.choice(muestra, size=(n_sims, meses), replace=True)

    # evolución de cada camino con aportación al principio de cada mes
    valores = np.empty((n_sims, meses + 1))
    valores[:, 0] = initial
    for m in range(meses):
        valores[:, m + 1] = (valores[:, m] + monthly_contribution) * (1 + sorteos[:, m])

    aportado = initial + monthly_contribution * meses
    bandas = {p: np.percentile(valores, p, axis=0) for p in PERCENTILES}
    terminal = valores[:, -1]

    return {
        "meses": meses,
        "aportado": float(aportado),
        "bandas": {p: [round(float(v), 2) for v in bandas[p]] for p in PERCENTILES},
        "terminal": {p: float(np.percentile(terminal, p)) for p in PERCENTILES},
        "prob_ganancia": float(np.mean(terminal > aportado)),
        "prob_doblar": float(np.mean(terminal > 2 * aportado)),
        "prob_objetivo": float(np.mean(terminal >= objetivo)) if objetivo else None,
        "n_sims": n_sims,
        "meses_historico": int(len(mensuales)),
        "ret_mensual_medio": float(mensuales.mean()),
    }


def _normaliza_pesos(weights, prices) -> dict:
    faltan = [t for t in weights if t not in prices.columns]
    if faltan:
        raise ValueError(f"Los precios no incluyen columnas para: {faltan}")
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Los pesos deben sumar un valor positivo")
    return {t: w / total for t, w in weights.items()}
