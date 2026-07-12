"""Simulador qué-pasaría-si: compara N escenarios de inversión en paralelo.

Cada escenario es una ejecución independiente del backtester (mismo motor,
mismos datos con caché), de modo que los resultados del simulador coinciden
por construcción con los del módulo backtester.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from core.engine import BacktestResult
from modules import backtester


@dataclass(frozen=True)
class Scenario:
    name: str
    weights: Mapping[str, float]
    initial_investment: float = 0.0
    monthly_contribution: float = 0.0
    rebalance_freq: str | None = None


def run(
    scenarios: list[Scenario],
    start,
    end,
    *,
    cache_dir=None,
    downloader=None,
) -> list[tuple[Scenario, BacktestResult]]:
    """Ejecuta todos los escenarios sobre el mismo rango de fechas."""
    if len(scenarios) < 2:
        raise ValueError("El simulador necesita al menos dos escenarios que comparar")
    return [
        (
            sc,
            backtester.run(
                dict(sc.weights),
                start,
                end,
                initial_investment=sc.initial_investment,
                monthly_contribution=sc.monthly_contribution,
                rebalance_freq=sc.rebalance_freq,
                cache_dir=cache_dir,
                downloader=downloader,
            ),
        )
        for sc in scenarios
    ]
