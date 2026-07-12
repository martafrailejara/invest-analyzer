"""Demo del backtester (Fase 2) con el caso de ejemplo del proyecto:

"Si hubiera invertido 200€/mes en el S&P 500 desde 2015 con rebalanceo anual
80/20, ¿cuánto tendría hoy y cuál fue el máximo drawdown?"

Cartera 80% S&P 500 (SXR8.DE) / 20% IBEX 35 (LYXIB.MC), en EUR.
Se usa LYXIB.MC (línea de Madrid) y no CS1.PA (la de la cartera personal)
porque CS1.PA solo tiene histórico en yfinance desde 2024, tras la fusión
Lyxor -> Amundi, y este backtest arranca en 2015.

Uso:
    .venv/bin/python scripts/demo_fase2.py
"""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from modules import backtester  # noqa: E402


def main() -> None:
    res = backtester.run(
        {"SXR8.DE": 0.8, "LYXIB.MC": 0.2},
        "2015-01-01",
        "2026-07-10",
        monthly_contribution=200,
        rebalance_freq="Y",
    )
    m = res.metrics()

    print("== 200€/mes en 80% S&P 500 / 20% IBEX 35, rebalanceo anual, 2015 → hoy ==\n")
    print(f"  Total aportado:     {m['total_invested']:>12,.2f} €")
    print(f"  Valor final:        {m['final_value']:>12,.2f} €")
    print(f"  Ganancia:           {m['profit']:>12,.2f} €")
    print(f"  CAGR (TWR):         {m['cagr']:>12.2%}")
    print(f"  Volatilidad anual:  {m['volatility']:>12.2%}")
    print(f"  Sharpe:             {m['sharpe']:>12.2f}")
    print(f"  Máximo drawdown:    {m['max_drawdown']:>12.2%}")


if __name__ == "__main__":
    main()
