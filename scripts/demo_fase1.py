"""Demo de la capa de datos (Fase 1) contra datos reales.

Uso:
    .venv/bin/python scripts/demo_fase1.py [ruta/al/export_trade_republic.csv]

Si no se pasa ruta, busca la cartera en data/transacciones.csv. Descarga
precios reales de yfinance (la segunda ejecución sale de la caché en
data/market/).
"""

import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from core import market_data, portfolio  # noqa: E402

TICKERS_DEMO = ["SXR8.DE", "CS1.PA", "BTC-EUR"]


def main() -> None:
    print(f"== Precios ({', '.join(TICKERS_DEMO)}), último año ==")
    t0 = time.perf_counter()
    precios = market_data.get_prices(TICKERS_DEMO, "2025-07-01", "2026-07-10")
    print(f"[{time.perf_counter() - t0:.2f}s] {len(precios)} sesiones\n")
    print(precios.tail(), "\n")

    csv = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "data" / "transacciones.csv"
    if not csv.exists():
        print(f"(No hay cartera en {csv}; guarda ahí tu export de Trade Republic para verla)")
        return

    print(f"== Posiciones derivadas de {csv.name} ==")
    pos = portfolio.load_positions(csv)
    print(pos.to_string(index=False), "\n")

    sin_mapear = pos[pos["yf_ticker"].isna()]
    if not sin_mapear.empty:
        print("ISINs sin mapear a yfinance (añádelos a core/isin_map.py):")
        print(sin_mapear[["symbol", "name"]].to_string(index=False))


if __name__ == "__main__":
    main()
