"""Mi cartera: las posiciones reales valoradas a precio de mercado.

Reconstruye día a día las unidades en cartera desde el export de
transacciones, las valora con los precios de cierre (con caché) y produce
la curva de valor frente al aportado neto, el P&L por posición y las
métricas time-weighted de la cartera real.
"""

from __future__ import annotations

import pandas as pd

from core import market_data, metrics, portfolio


def run(csv_path, *, cache_dir=None, downloader=None) -> dict:
    txs = portfolio.load_transactions(csv_path)
    pos = portfolio.positions(txs)
    mapeadas = pos[pos["yf_ticker"].notna()]
    sin_mapear = pos.loc[pos["yf_ticker"].isna(), "symbol"].tolist()
    if mapeadas.empty:
        raise ValueError(
            "Ninguna posición de la cartera está mapeada a un ticker de yfinance "
            "(ver core/isin_map.py)"
        )

    fechas_tx = txs["datetime"].dt.tz_convert(None).dt.normalize()
    inicio = fechas_tx.min()
    tickers = mapeadas["yf_ticker"].tolist()
    px = market_data.get_prices(
        tickers, inicio, pd.Timestamp.today().normalize() + pd.Timedelta(days=1),
        cache_dir=cache_dir, downloader=downloader,
    ).sort_index().ffill()

    # unidades en cartera por día (función escalón desde las transacciones)
    unidades = pd.DataFrame(0.0, index=px.index, columns=tickers)
    for _, fila in mapeadas.iterrows():
        grupo = txs[txs["symbol"] == fila["symbol"]]
        signo = grupo["type"].map({"BUY": 1.0, "SELL": -1.0})
        deltas = (grupo["shares"] * signo).groupby(fechas_tx[grupo.index]).sum()
        acumulado = deltas.sort_index().cumsum()
        unidades[fila["yf_ticker"]] = (
            acumulado.reindex(px.index, method="ffill").fillna(0.0)
        )

    valor = (unidades * px).fillna(0.0).sum(axis=1)

    # aportado neto por día: compras suman, ventas devuelven
    flujo_tx = (-txs["amount"] - txs["fee"]).groupby(fechas_tx).sum()
    # una transacción en día sin sesión (p. ej. festivo) se asigna a la siguiente
    flujo = pd.Series(0.0, index=px.index)
    for fecha, importe in flujo_tx.items():
        posicion = px.index.searchsorted(fecha)
        if posicion >= len(px.index):
            posicion = len(px.index) - 1
        flujo.iloc[posicion] += importe
    invertido = flujo.cumsum()

    retornos = ((valor - flujo) / valor.shift(1) - 1).iloc[1:].dropna()
    indice_twr = (1 + retornos).cumprod()

    ganancia = valor - invertido  # la parte de la curva que NO es aportación
    flujo_mensual = {
        str(periodo): float(importe)
        for periodo, importe in flujo.groupby(flujo.index.to_period("M")).sum().items()
        if abs(importe) > 1e-9
    }
    hoy = px.index.max()
    aportado_30d = float(flujo[flujo.index > hoy - pd.Timedelta(days=30)].sum())
    variacion_dia = float(valor.iloc[-1] - valor.iloc[-2]) if len(valor) > 1 else 0.0
    variacion_dia_pct = variacion_dia / float(valor.iloc[-2]) if len(valor) > 1 and valor.iloc[-2] else 0.0

    posiciones = []
    valor_total = float(valor.iloc[-1])
    for _, fila in mapeadas.iterrows():
        serie_px = px[fila["yf_ticker"]]
        precio_actual = float(serie_px.iloc[-1])
        var_dia = (precio_actual / float(serie_px.iloc[-2]) - 1) if len(serie_px) > 1 else 0.0
        valor_actual = float(fila["shares"]) * precio_actual
        pnl = valor_actual - float(fila["cost_total"])
        posiciones.append({
            "var_dia": var_dia,
            "symbol": fila["symbol"],
            "name": fila["name"],
            "ticker": fila["yf_ticker"],
            "shares": float(fila["shares"]),
            "avg_cost": float(fila["avg_cost"]),
            "precio_actual": precio_actual,
            "valor": valor_actual,
            "pnl": pnl,
            "pnl_pct": pnl / float(fila["cost_total"]) if fila["cost_total"] else 0.0,
            "peso": valor_actual / valor_total if valor_total else 0.0,
        })

    aportado = float(invertido.iloc[-1])
    transacciones = [
        {
            "fecha": fechas_tx[i],
            "tipo": "Compra" if txs.loc[i, "type"] == "BUY" else "Venta",
            "name": txs.loc[i, "name"],
            "shares": float(txs.loc[i, "shares"]),
            "price": float(txs.loc[i, "price"]),
            "caja": float(txs.loc[i, "amount"] + txs.loc[i, "fee"]),
        }
        for i in reversed(txs.index)
    ]
    return {
        "posiciones": sorted(posiciones, key=lambda p: -p["valor"]),
        "valor_total": valor_total,
        "aportado_neto": aportado,
        "pnl_total": valor_total - aportado,
        "pnl_pct": (valor_total - aportado) / aportado if aportado else 0.0,
        "cagr": float(metrics.cagr(indice_twr)) if len(indice_twr) > 1 else float("nan"),
        "max_drawdown": float(metrics.max_drawdown(indice_twr)) if len(indice_twr) else 0.0,
        "variacion_dia": variacion_dia,
        "variacion_dia_pct": variacion_dia_pct,
        "aportado_30d": aportado_30d,
        "flujo_mensual": flujo_mensual,
        "curva": {"valor": valor, "invertido": invertido, "ganancia": ganancia},
        "transacciones": transacciones,
        "desde": inicio,
        "sin_mapear": sin_mapear,
    }
