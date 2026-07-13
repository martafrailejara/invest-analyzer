"""Motor de simulación de estrategias periodo a periodo.

Una ``Strategy`` es una configuración (pesos objetivo, aportaciones,
rebalanceo) y no una implementación: buy & hold, DCA y rebalanceo periódico
son casos particulares del mismo motor. Las compras se ejecutan al cierre del
día, con unidades fraccionarias y sin comisiones.

Los retornos del resultado son time-weighted (netos de aportaciones), que es
lo que permite calcular CAGR, volatilidad, Sharpe y drawdown sin que las
aportaciones periódicas distorsionen las métricas.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass
from typing import Mapping

import pandas as pd

from core import metrics

FREQ_VALIDAS = {"M", "Q", "Y"}


@dataclass(frozen=True)
class Strategy:
    """Configuración de una estrategia de inversión.

    - ``weights``: pesos objetivo por ticker; deben sumar 1, sin cortos.
    - ``initial_investment``: aportación única al inicio.
    - ``monthly_contribution``: aportación el primer día de negociación de cada mes.
    - ``contribution_months``: None (todo el rango) o número de meses durante
      los que se aporta — "repartir X en DCA durante 12 meses".
    - ``rebalance_freq``: None (nunca), "M", "Q" o "Y" — el rebalanceo se
      ejecuta el primer día de negociación de cada periodo.
    """

    weights: Mapping[str, float]
    initial_investment: float = 0.0
    monthly_contribution: float = 0.0
    contribution_months: int | None = None
    rebalance_freq: str | None = None

    @classmethod
    def buy_and_hold(cls, weights, initial_investment):
        return cls(weights=weights, initial_investment=initial_investment)

    @classmethod
    def dca(cls, weights, monthly_contribution, initial_investment=0.0, rebalance_freq=None):
        return cls(
            weights=weights,
            initial_investment=initial_investment,
            monthly_contribution=monthly_contribution,
            rebalance_freq=rebalance_freq,
        )


@dataclass
class BacktestResult:
    """Series diarias de la simulación + métricas agregadas."""

    value: pd.Series      # valor de la cartera al cierre
    invested: pd.Series   # aportaciones acumuladas
    flows: pd.Series      # aportación de cada día (0 si no hay)
    returns: pd.Series    # retornos time-weighted, netos de aportaciones
    strategy: Strategy

    def twr_index(self) -> pd.Series:
        """Índice de crecimiento (base 1.0) de los retornos time-weighted."""
        base = pd.Series([1.0], index=self.value.index[:1])
        return pd.concat([base, (1 + self.returns).cumprod()])

    def metrics(
        self,
        risk_free_annual: float = 0.0,
        periods_per_year: int = metrics.TRADING_DAYS_PER_YEAR,
    ) -> dict:
        indice = self.twr_index()
        final = float(self.value.iloc[-1])
        aportado = float(self.invested.iloc[-1])
        return {
            "final_value": final,
            "total_invested": aportado,
            "profit": final - aportado,
            "cagr": float(metrics.cagr(indice)),
            "volatility": float(metrics.annualized_volatility(self.returns, periods_per_year)),
            "sharpe": float(metrics.sharpe_ratio(self.returns, risk_free_annual, periods_per_year)),
            "max_drawdown": float(metrics.max_drawdown(indice)),
        }


def run_backtest(prices: pd.DataFrame, strategy: Strategy) -> BacktestResult:
    """Simula la estrategia sobre los precios dados, día a día.

    Los huecos internos de precio (festivos de una bolsa, fines de semana de
    los ETFs frente a cripto) se rellenan con el último precio conocido; los
    días previos a que todos los activos tengan histórico se descartan.
    """
    weights = dict(strategy.weights)
    _validate(prices, strategy, weights)

    px = prices[list(weights)].sort_index().ffill().dropna()
    if px.empty:
        raise ValueError("No hay ninguna fecha con precio para todos los activos del rango")
    primera_pedida = prices.index.min()
    if px.index[0] != primera_pedida:
        warnings.warn(
            f"No todos los activos tienen histórico desde {primera_pedida.date()}: "
            f"la simulación empieza el {px.index[0].date()}"
        )

    dias_aportacion = _first_days(px.index, "M") if strategy.monthly_contribution else set()
    if strategy.contribution_months is not None:
        dias_aportacion = set(sorted(dias_aportacion)[: strategy.contribution_months])
    dias_rebalanceo = (
        _first_days(px.index, strategy.rebalance_freq) - {px.index[0]}
        if strategy.rebalance_freq
        else set()
    )

    unidades = dict.fromkeys(weights, 0.0)
    valores: list[float] = []
    aportaciones: list[float] = []
    for i, (dia, p) in enumerate(px.iterrows()):
        aportacion = strategy.initial_investment if i == 0 else 0.0
        if dia in dias_aportacion:
            aportacion += strategy.monthly_contribution
        if aportacion:
            for ticker, peso in weights.items():
                unidades[ticker] += aportacion * peso / p[ticker]
        if dia in dias_rebalanceo:
            total = sum(unidades[t] * p[t] for t in weights)
            for ticker, peso in weights.items():
                unidades[ticker] = total * peso / p[ticker]
        valores.append(sum(unidades[t] * p[t] for t in weights))
        aportaciones.append(aportacion)

    value = pd.Series(valores, index=px.index, name="value")
    flows = pd.Series(aportaciones, index=px.index, name="flow")
    # la aportación se compra al cierre: el retorno del día es el del
    # patrimonio preexistente, excluyendo el flujo entrante
    returns = ((value - flows) / value.shift(1) - 1).iloc[1:]
    return BacktestResult(
        value=value,
        invested=flows.cumsum(),
        flows=flows,
        returns=returns,
        strategy=strategy,
    )


def _validate(prices: pd.DataFrame, strategy: Strategy, weights: dict) -> None:
    desconocidos = sorted(set(weights) - set(prices.columns))
    if desconocidos:
        raise ValueError(f"Los precios no incluyen columnas para: {desconocidos}")
    if any(w < 0 for w in weights.values()):
        raise ValueError("No se admiten pesos negativos (posiciones cortas)")
    suma = sum(weights.values())
    if abs(suma - 1.0) > 1e-6:
        raise ValueError(f"Los pesos deben sumar 1 (suman {suma})")
    if strategy.initial_investment < 0 or strategy.monthly_contribution < 0:
        raise ValueError("Las aportaciones no pueden ser negativas")
    if strategy.initial_investment == 0 and strategy.monthly_contribution == 0:
        raise ValueError("La estrategia no invierte nada: initial_investment y monthly_contribution a 0")
    if strategy.rebalance_freq is not None and strategy.rebalance_freq not in FREQ_VALIDAS:
        raise ValueError(f"rebalance_freq debe ser None o una de {sorted(FREQ_VALIDAS)}")
    if strategy.contribution_months is not None and strategy.contribution_months < 1:
        raise ValueError("contribution_months debe ser al menos 1 (o None para todo el rango)")


def _first_days(index: pd.DatetimeIndex, freq: str) -> set:
    """Primer día de negociación de cada periodo (mes/trimestre/año) del índice."""
    return set(index.to_series().groupby(index.to_period(freq)).first())
