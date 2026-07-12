"""Métricas de rendimiento y riesgo compartidas por todos los módulos.

Funciones puras sobre Series/DataFrames de pandas. Las que reciben precios o
valores esperan un índice de fechas; las que reciben retornos esperan retornos
simples por periodo (salida de ``simple_returns``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25


def simple_returns(prices):
    """Retornos simples por periodo: p_t / p_{t-1} - 1."""
    return prices.pct_change().dropna()


def log_returns(prices):
    """Retornos logarítmicos por periodo: ln(p_t / p_{t-1})."""
    return np.log(prices / prices.shift(1)).dropna()


def cumulative_return(prices):
    """Retorno acumulado del rango completo: p_final / p_inicial - 1."""
    return prices.iloc[-1] / prices.iloc[0] - 1


def cagr(values):
    """Tasa de crecimiento anual compuesto, anualizada por días de calendario.

    ``values`` es una serie de precios o de valor de cartera con índice de
    fechas que abarque más de un día.
    """
    dias = (values.index[-1] - values.index[0]).days
    if dias <= 0:
        raise ValueError("Para calcular el CAGR hacen falta al menos dos fechas distintas")
    total = values.iloc[-1] / values.iloc[0]
    return total ** (CALENDAR_DAYS_PER_YEAR / dias) - 1


def annualized_volatility(returns, periods_per_year: int = TRADING_DAYS_PER_YEAR):
    """Desviación típica de los retornos, anualizada."""
    return returns.std(ddof=1) * np.sqrt(periods_per_year)


def max_drawdown(values):
    """Máxima caída desde un pico previo, como número negativo (p. ej. -0.35)."""
    return (values / values.cummax() - 1).min()


def sharpe_ratio(
    returns,
    risk_free_annual: float = 0.0,
    periods_per_year: int = TRADING_DAYS_PER_YEAR,
):
    """Ratio de Sharpe anualizado.

    ``risk_free_annual`` es la tasa libre de riesgo anual (p. ej. 0.02); se
    convierte a la periodicidad de los retornos antes de restarla. Devuelve
    NaN si los retornos no tienen dispersión.
    """
    rf_periodo = (1 + risk_free_annual) ** (1 / periods_per_year) - 1
    exceso = returns - rf_periodo
    desviacion = exceso.std(ddof=1)
    if desviacion == 0:
        return float("nan")
    return exceso.mean() / desviacion * np.sqrt(periods_per_year)
