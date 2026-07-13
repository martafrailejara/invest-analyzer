"""Backtester de estrategias: orquesta la capa de datos y el motor de simulación.

La lógica vive en core/engine.py y core/metrics.py; este módulo solo une
piezas para poder responder a "¿cómo habría rendido esta estrategia?" con una
llamada.
"""

from __future__ import annotations

from core import engine, market_data


def run(
    weights: dict[str, float],
    start,
    end,
    *,
    initial_investment: float = 0.0,
    monthly_contribution: float = 0.0,
    contribution_months: int | None = None,
    rebalance_freq: str | None = None,
    cache_dir=None,
    downloader=None,
) -> engine.BacktestResult:
    """Backtest de una estrategia sobre precios reales (con caché local).

    ``weights`` usa tickers de yfinance (ver core/isin_map.py para traducir
    ISINs de la cartera personal).
    """
    prices = market_data.get_prices(
        list(weights), start, end, cache_dir=cache_dir, downloader=downloader
    )
    strategy = engine.Strategy(
        weights=weights,
        initial_investment=initial_investment,
        monthly_contribution=monthly_contribution,
        contribution_months=contribution_months,
        rebalance_freq=rebalance_freq,
    )
    return engine.run_backtest(prices, strategy)
