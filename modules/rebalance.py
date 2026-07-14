"""Plan de rebalanceo hacia los pesos objetivo. Dos modos:

- **Clásico** (comprar y vender): las órdenes exactas para volver al objetivo
  hoy. Las ventas generan plusvalía: se estima su cuota con el módulo fiscal.
- **Aportación dirigida** (solo comprando): reparte tu próxima aportación
  entre los activos infraponderados para converger al objetivo sin vender —
  y por tanto sin generar plusvalías.

Cálculo mecánico sobre precios de cierre; no es asesoramiento profesional.
"""

from __future__ import annotations

from modules import holdings, taxes


def run(csv_path, objetivos: dict, aportacion: float = 0.0,
        *, cache_dir=None, downloader=None) -> dict:
    if not objetivos:
        raise ValueError("Define primero tus pesos objetivo en el chequeo")
    cartera = holdings.run(csv_path, cache_dir=cache_dir, downloader=downloader)
    posiciones = [p for p in cartera["posiciones"] if p["symbol"] in objetivos]
    if not posiciones:
        raise ValueError("Ninguna posición de la cartera tiene peso objetivo definido")
    valor_total = cartera["valor_total"]

    clasico = ordenes_clasicas(posiciones, objetivos, valor_total)
    for orden in clasico:
        if orden["accion"] == "vender":
            venta = taxes.simulate_sale(csv_path, orden["symbol"],
                                        orden["unidades"], orden["precio"])
            orden["plusvalia"] = venta["plusvalia"]
            orden["cuota"] = venta["cuota"]

    dirigida = aportacion_dirigida(posiciones, objetivos, valor_total, aportacion) \
        if aportacion > 0 else []

    return {
        "clasico": clasico,
        "cuota_total": sum(o.get("cuota", 0.0) for o in clasico),
        "dirigida": dirigida,
        "aportacion": aportacion,
        "valor_total": valor_total,
    }


def ordenes_clasicas(posiciones: list[dict], objetivos: dict, valor_total: float) -> list[dict]:
    """Órdenes de compra/venta para dejar cada posición en su peso objetivo hoy."""
    ordenes = []
    for p in posiciones:
        delta = objetivos[p["symbol"]] * valor_total - p["valor"]
        if abs(delta) < 1.0:  # menos de 1 €: no vale la pena una orden
            continue
        ordenes.append({
            "symbol": p["symbol"],
            "ticker": p["ticker"],
            "accion": "comprar" if delta > 0 else "vender",
            "importe": abs(delta),
            "unidades": abs(delta) / p["precio_actual"],
            "precio": p["precio_actual"],
        })
    return sorted(ordenes, key=lambda o: -o["importe"])


def aportacion_dirigida(posiciones: list[dict], objetivos: dict,
                        valor_total: float, aportacion: float) -> list[dict]:
    """Reparte la aportación entre los activos por debajo de su peso objetivo.

    El objetivo se mide sobre el valor futuro (cartera + aportación). Si el
    dinero no alcanza para cubrir todos los déficits, se reparte proporcional
    al déficit; si sobra, el resto se reparte según los pesos objetivo.
    """
    valor_futuro = valor_total + aportacion
    deficits = {
        p["symbol"]: max(objetivos[p["symbol"]] * valor_futuro - p["valor"], 0.0)
        for p in posiciones
    }
    total_deficit = sum(deficits.values())

    asignacion: dict[str, float] = {}
    if total_deficit <= aportacion:
        sobra = aportacion - total_deficit
        for p in posiciones:
            asignacion[p["symbol"]] = deficits[p["symbol"]] + sobra * objetivos[p["symbol"]]
    else:
        for p in posiciones:
            asignacion[p["symbol"]] = aportacion * deficits[p["symbol"]] / total_deficit

    por_ticker = {p["symbol"]: p for p in posiciones}
    return sorted(
        ({"symbol": s, "ticker": por_ticker[s]["ticker"], "importe": imp,
          "peso_resultante": (por_ticker[s]["valor"] + imp) / valor_futuro}
         for s, imp in asignacion.items() if imp > 0.5),
        key=lambda o: -o["importe"],
    )
