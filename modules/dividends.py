"""Agregador de dividendos: qué ha pagado cada posición y qué proyecta pagar.

Cruza el histórico de dividendos por acción (yfinance) con las unidades en
cartera en cada fecha ex-dividendo, derivadas del export de transacciones.
La proyección a 12 meses es el último año de dividendos por acción aplicado
a las unidades actuales — una extrapolación simple, no una promesa.

Simplificación documentada: los importes se tratan en la divisa de cotización
del ticker (EUR para las líneas europeas mapeadas en core/isin_map.py).
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import pandas as pd

from core import isin_map, market_data, portfolio


def run(csv_path: Path | str, *, cache_dir=None, downloader=None) -> dict:
    """Agregado de dividendos para un export de transacciones de Trade Republic."""
    transactions = portfolio.load_transactions(csv_path)
    return aggregate(transactions, cache_dir=cache_dir, downloader=downloader)


def aggregate(transactions: pd.DataFrame, *, cache_dir=None, downloader=None) -> dict:
    posiciones_actuales = portfolio.positions(transactions).set_index("symbol")
    hoy = pd.Timestamp.today().normalize()
    hace_un_anio = hoy - pd.Timedelta(days=365)

    posiciones: list[dict] = []
    por_anio: dict[int, float] = defaultdict(float)
    sin_mapear: list[str] = []

    for symbol, pos in posiciones_actuales.iterrows():
        grupo = transactions[transactions["symbol"] == symbol]
        entrada = {
            "symbol": symbol,
            "name": pos["name"],
            "ticker": pos["yf_ticker"],
            "shares": float(pos["shares"]),
            "cost_total": float(pos["cost_total"]),
            "cobrado_total": 0.0,
            "cobrado_por_anio": {},
            "dps_12m": 0.0,
            "proyeccion": 0.0,
            "yoc": 0.0,
        }
        if pos["asset_class"] == "CRYPTO":
            posiciones.append(entrada)  # las criptos no reparten: fila honesta a cero
            continue
        if pd.isna(pos["yf_ticker"]):
            sin_mapear.append(symbol)
            continue

        divs = market_data.get_dividends(pos["yf_ticker"], cache_dir=cache_dir, downloader=downloader)
        if divs.empty:  # activo de acumulación o sin histórico de dividendos
            posiciones.append(entrada)
            continue
        cobrado_por_anio: dict[int, float] = defaultdict(float)
        for fecha_ex, dps in divs.items():
            unidades = _unidades_antes_de(grupo, fecha_ex)
            if unidades > 1e-12:
                importe = unidades * float(dps)
                cobrado_por_anio[fecha_ex.year] += importe
                por_anio[fecha_ex.year] += importe

        dps_12m = float(divs[divs.index > hace_un_anio].sum())
        entrada.update(
            cobrado_total=float(sum(cobrado_por_anio.values())),
            cobrado_por_anio=dict(sorted(cobrado_por_anio.items())),
            dps_12m=dps_12m,
            proyeccion=dps_12m * entrada["shares"],
            yoc=(dps_12m * entrada["shares"] / entrada["cost_total"]) if entrada["cost_total"] > 0 else 0.0,
        )
        posiciones.append(entrada)

    return {
        "posiciones": sorted(posiciones, key=lambda p: -p["proyeccion"]),
        "por_anio": dict(sorted(por_anio.items())),
        "este_anio": por_anio.get(hoy.year, 0.0),
        "cobrado_total": float(sum(por_anio.values())),
        "proyeccion_total": float(sum(p["proyeccion"] for p in posiciones)),
        "sin_mapear": sin_mapear,
    }


def _unidades_antes_de(grupo: pd.DataFrame, fecha_ex: pd.Timestamp) -> float:
    """Unidades en cartera estrictamente antes de la fecha ex-dividendo."""
    fechas = grupo["datetime"].dt.tz_convert(None).dt.normalize()
    previas = grupo[fechas < fecha_ex]
    compradas = previas.loc[previas["type"] == "BUY", "shares"].sum()
    vendidas = previas.loc[previas["type"] == "SELL", "shares"].sum()
    return float(compradas - vendidas)
