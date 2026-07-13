"""Fiscalidad española (estimación): plusvalías FIFO y tramos del ahorro.

- Reconstruye los lotes de compra por activo y aplica FIFO a las ventas,
  como exige la normativa española, para calcular plusvalías realizadas.
- Simula una venta hipotética: coste FIFO de las unidades, plusvalía y
  cuota estimada por los tramos de la base del ahorro.

Estimación simplificada y descriptiva, no asesoría fiscal: calcula la cuota
del ahorro sobre la plusvalía aislada (sin otras rentas del ahorro, sin
mínimos, sin regla de los dos meses ni compensaciones de pérdidas).
"""

from __future__ import annotations

import pandas as pd

from core import portfolio

# Tramos de la base imponible del ahorro (IRPF estatal + autonómico, 2025)
TRAMOS_AHORRO = [
    (6_000, 0.19),
    (50_000, 0.21),
    (200_000, 0.23),
    (300_000, 0.27),
    (float("inf"), 0.30),
]


def run(csv_path) -> dict:
    """Lotes vivos, plusvalías realizadas por año y datos para el simulador."""
    txs = portfolio.load_transactions(csv_path)
    lotes_vivos, realizadas = _fifo(txs)
    por_anio: dict[int, float] = {}
    for r in realizadas:
        por_anio[r["anio"]] = por_anio.get(r["anio"], 0.0) + r["plusvalia"]

    return {
        "lotes": lotes_vivos,
        "realizadas": realizadas,
        "por_anio": dict(sorted(por_anio.items())),
        "cuota_por_anio": {a: cuota_ahorro(max(g, 0.0)) for a, g in sorted(por_anio.items())},
    }


def simulate_sale(csv_path, symbol: str, unidades: float, precio_actual: float) -> dict:
    """Venta hipotética: coste FIFO, plusvalía y cuota estimada del ahorro."""
    if unidades <= 0:
        raise ValueError("Las unidades a vender deben ser mayores que 0")
    if precio_actual <= 0:
        raise ValueError("El precio actual debe ser mayor que 0")
    txs = portfolio.load_transactions(csv_path)
    lotes_vivos, _ = _fifo(txs)
    del_activo = [l for l in lotes_vivos if l["symbol"] == symbol]
    disponibles = sum(l["unidades"] for l in del_activo)
    if not del_activo:
        raise ValueError(f"No hay unidades de {symbol} en cartera")
    if unidades > disponibles + 1e-9:
        raise ValueError(
            f"Solo hay {disponibles:.6f} unidades de {symbol} en cartera"
        )

    restantes = unidades
    coste = 0.0
    consumidos = []
    for lote in del_activo:  # ya en orden FIFO
        if restantes <= 1e-12:
            break
        toma = min(lote["unidades"], restantes)
        coste += toma * lote["coste_unitario"]
        consumidos.append({"fecha": lote["fecha"], "unidades": toma,
                           "coste_unitario": lote["coste_unitario"]})
        restantes -= toma

    importe = unidades * precio_actual
    plusvalia = importe - coste
    return {
        "symbol": symbol,
        "unidades": unidades,
        "importe": importe,
        "coste_fifo": coste,
        "plusvalia": plusvalia,
        "cuota": cuota_ahorro(max(plusvalia, 0.0)),
        "lotes_consumidos": consumidos,
    }


def cuota_ahorro(ganancia: float) -> float:
    """Cuota estimada por los tramos de la base del ahorro (ganancia aislada)."""
    cuota = 0.0
    base_anterior = 0.0
    for tope, tipo in TRAMOS_AHORRO:
        if ganancia <= base_anterior:
            break
        tramo = min(ganancia, tope) - base_anterior
        cuota += tramo * tipo
        base_anterior = tope
    return cuota


def _fifo(txs: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Lotes vivos tras aplicar FIFO y lista de ventas con su plusvalía.

    El coste unitario del lote incluye la parte proporcional de la comisión
    de compra; la comisión de venta reduce el importe obtenido.
    """
    lotes: dict[str, list[dict]] = {}
    realizadas: list[dict] = []
    fechas = txs["datetime"].dt.tz_convert(None)

    for i in txs.index:
        t = txs.loc[i]
        symbol = t["symbol"]
        cola = lotes.setdefault(symbol, [])
        if t["type"] == "BUY":
            coste_total = -t["amount"] - t["fee"]
            cola.append({
                "symbol": symbol,
                "name": t["name"],
                "fecha": fechas[i],
                "unidades": float(t["shares"]),
                "coste_unitario": coste_total / float(t["shares"]),
            })
        elif t["type"] == "SELL":
            restantes = float(t["shares"])
            importe_neto = float(t["amount"] + t["fee"])  # lo que entra en caja
            precio_neto = importe_neto / restantes
            coste = 0.0
            vendidas = restantes
            while restantes > 1e-12 and cola:
                lote = cola[0]
                toma = min(lote["unidades"], restantes)
                coste += toma * lote["coste_unitario"]
                lote["unidades"] -= toma
                restantes -= toma
                if lote["unidades"] <= 1e-12:
                    cola.pop(0)
            if restantes > 1e-9:
                raise ValueError(
                    f"Venta de {t['shares']} unidades de {symbol} sin lotes "
                    "suficientes: ¿export incompleto?"
                )
            realizadas.append({
                "symbol": symbol,
                "name": t["name"],
                "fecha": fechas[i],
                "anio": int(fechas[i].year),
                "unidades": vendidas,
                "importe": vendidas * precio_neto,
                "coste": coste,
                "plusvalia": vendidas * precio_neto - coste,
            })

    vivos = [l for cola in lotes.values() for l in cola if l["unidades"] > 1e-9]
    return vivos, realizadas
