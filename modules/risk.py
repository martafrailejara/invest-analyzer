"""Análisis de riesgo de una cartera: métricas avanzadas y correlaciones.

Reúne rendimiento/riesgo de la cartera frente a un índice de referencia
(Sharpe, Sortino, VaR, CVaR, beta, drawdown) y la matriz de correlación
entre los activos. Todo sobre retornos diarios reales.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core import market_data, metrics

MIN_SESIONES = 60


def run(weights, benchmark, start, end, *, cache_dir=None, downloader=None) -> dict:
    """Análisis de riesgo sobre precios reales (con caché local)."""
    pesos = _normaliza(weights)
    tickers = list(pesos)
    todos = tickers + ([benchmark] if benchmark and benchmark not in tickers else [])
    prices = market_data.get_prices(todos, start, end, cache_dir=cache_dir, downloader=downloader)
    return analyze(prices, pesos, benchmark)


def analyze(prices: pd.DataFrame, weights, benchmark: str | None) -> dict:
    pesos = _normaliza(weights)
    tickers = list(pesos)
    rets = metrics.simple_returns(prices.sort_index().ffill().dropna())
    if len(rets) < MIN_SESIONES:
        raise ValueError(
            f"Histórico insuficiente: {len(rets)} sesiones comunes (mínimo {MIN_SESIONES})"
        )

    cartera = (rets[tickers] * pd.Series(pesos)).sum(axis=1)
    bench_rets = rets[benchmark] if benchmark and benchmark in rets else None

    def bloque(serie, ref=None):
        return {
            "ret_anual": float(serie.mean() * metrics.TRADING_DAYS_PER_YEAR),
            "volatilidad": float(metrics.annualized_volatility(serie)),
            "sharpe": metrics.sharpe_ratio(serie),
            "sortino": metrics.sortino_ratio(serie),
            "var_95": metrics.value_at_risk(serie, 0.05),
            "cvar_95": metrics.conditional_var(serie, 0.05),
            "max_drawdown": float(metrics.max_drawdown((1 + serie).cumprod())),
            "beta": metrics.beta(serie, ref) if ref is not None else None,
        }

    matriz = rets[tickers].corr()
    correlaciones = {
        "tickers": tickers,
        "valores": [[float(matriz.loc[a, b]) for b in tickers] for a in tickers],
    }

    return {
        "cartera": bloque(cartera, bench_rets),
        "benchmark": {"nombre": benchmark, **bloque(bench_rets)} if bench_rets is not None else None,
        "correlaciones": correlaciones,
        "sesiones": int(len(rets)),
    }


def _normaliza(weights) -> dict:
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("Los pesos deben sumar un valor positivo")
    if len(weights) < 1:
        raise ValueError("Indica al menos un activo")
    return {t: w / total for t, w in weights.items()}
