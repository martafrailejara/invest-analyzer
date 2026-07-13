"""Optimizador de cartera: frontera eficiente de Markowitz (solo posiciones largas).

A partir de los retornos históricos anualizados calcula, con scipy, la cartera
de mínima varianza, la de máximo Sharpe y la frontera eficiente completa.
Es una herramienta descriptiva: muestra combinaciones y sus propiedades,
no emite recomendaciones.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.optimize import minimize

from core import market_data, metrics

MIN_SESIONES = 60


def run(
    tickers: list[str],
    start,
    end,
    *,
    n_points: int = 25,
    risk_free_annual: float = 0.0,
    cache_dir=None,
    downloader=None,
) -> dict:
    """Frontera eficiente sobre precios reales (con caché local)."""
    if len(set(tickers)) < 2:
        raise ValueError("El optimizador necesita al menos dos activos distintos")
    prices = market_data.get_prices(list(dict.fromkeys(tickers)), start, end,
                                    cache_dir=cache_dir, downloader=downloader)
    return efficient_frontier(prices, n_points=n_points, risk_free_annual=risk_free_annual)


def efficient_frontier(
    prices: pd.DataFrame,
    *,
    n_points: int = 25,
    risk_free_annual: float = 0.0,
) -> dict:
    """Frontera eficiente, cartera de mínima varianza y de máximo Sharpe.

    Restricciones: pesos entre 0 y 1 (sin cortos) que suman 1.
    Retornos y covarianza anualizados con 252 sesiones/año.
    """
    rets = metrics.simple_returns(prices.sort_index().ffill().dropna()).dropna()
    if len(rets) < MIN_SESIONES:
        raise ValueError(
            f"Histórico insuficiente para optimizar: {len(rets)} sesiones "
            f"con datos comunes (mínimo {MIN_SESIONES})"
        )

    tickers = list(rets.columns)
    mu = rets.mean().to_numpy() * metrics.TRADING_DAYS_PER_YEAR
    cov = rets.cov().to_numpy() * metrics.TRADING_DAYS_PER_YEAR
    n = len(tickers)

    def volatilidad(w: np.ndarray) -> float:
        return float(np.sqrt(w @ cov @ w))

    def optimiza(objetivo, restricciones) -> np.ndarray | None:
        resultado = minimize(
            objetivo,
            x0=np.full(n, 1 / n),
            method="SLSQP",
            bounds=[(0.0, 1.0)] * n,
            constraints=restricciones,
            options={"ftol": 1e-12, "maxiter": 1000},
        )
        return resultado.x if resultado.success else None

    suma_1 = {"type": "eq", "fun": lambda w: np.sum(w) - 1}

    def como_punto(w: np.ndarray) -> dict:
        return {
            "ret": float(w @ mu),
            "vol": volatilidad(w),
            "weights": {t: round(float(p), 4) for t, p in zip(tickers, w) if p > 1e-4},
        }

    w_min_var = optimiza(lambda w: w @ cov @ w, [suma_1])
    if w_min_var is None:
        raise ValueError("La optimización de mínima varianza no convergió")

    rf = risk_free_annual

    def sharpe_negativo(w: np.ndarray) -> float:
        return -((w @ mu - rf) / max(volatilidad(w), 1e-12))

    w_max_sharpe = optimiza(sharpe_negativo, [suma_1])

    # barrido de retornos objetivo entre el de mínima varianza y el máximo alcanzable
    ret_min = float(w_min_var @ mu)
    ret_max = float(mu.max())
    frontera = []
    for objetivo_ret in np.linspace(ret_min, ret_max, n_points):
        w = optimiza(
            lambda w: w @ cov @ w,
            [suma_1, {"type": "eq", "fun": lambda w, r=objetivo_ret: w @ mu - r}],
        )
        if w is not None:
            frontera.append(como_punto(w))

    return {
        "frontera": frontera,
        "min_var": como_punto(w_min_var),
        "max_sharpe": como_punto(w_max_sharpe) if w_max_sharpe is not None else None,
        "activos": [
            {"ticker": t, "ret": float(mu[i]), "vol": float(np.sqrt(cov[i, i]))}
            for i, t in enumerate(tickers)
        ],
        "sesiones": int(len(rets)),
    }
