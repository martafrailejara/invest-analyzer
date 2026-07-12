"""Carga del export de transacciones de Trade Republic y derivación de posiciones.

El export es un CSV con todas las operaciones de la cuenta (compras, ventas,
recargas, pagos con tarjeta…). Aquí nos quedamos solo con las filas de trading
y derivamos las posiciones actuales acumulando transacciones, con el coste
medio como método de valoración al vender.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from core import isin_map

REQUIRED_COLUMNS = [
    "datetime",
    "category",
    "type",
    "asset_class",
    "name",
    "symbol",
    "shares",
    "price",
    "amount",
    "fee",
    "currency",
]

TRADING_TYPES = {"BUY", "SELL"}


def load_transactions(path: Path | str) -> pd.DataFrame:
    """Transacciones de trading del export, normalizadas y en orden cronológico.

    Filtra el ruido de cash (recargas, transferencias, tarjeta) y descarta con
    aviso los tipos de trading aún no soportados.
    """
    df = pd.read_csv(path, dtype=str)
    missing = [col for col in REQUIRED_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(
            f"El CSV no parece un export de transacciones de Trade Republic: "
            f"faltan las columnas {missing}"
        )

    trading = df[df["category"] == "TRADING"].copy()
    desconocidos = sorted(set(trading["type"]) - TRADING_TYPES)
    if desconocidos:
        warnings.warn(
            f"Tipos de transacción de trading no soportados todavía "
            f"(se ignoran): {desconocidos}"
        )
        trading = trading[trading["type"].isin(TRADING_TYPES)]

    trading["datetime"] = pd.to_datetime(trading["datetime"], format="ISO8601", utc=True)
    for col in ("shares", "price", "amount"):
        trading[col] = pd.to_numeric(trading[col])
    trading["fee"] = pd.to_numeric(trading["fee"]).fillna(0.0)

    incompletas = trading[trading[["symbol", "shares", "price", "amount"]].isna().any(axis=1)]
    if not incompletas.empty:
        raise ValueError(
            "Transacciones de trading con campos vacíos (symbol/shares/price/amount): "
            f"{incompletas['datetime'].dt.date.tolist()}"
        )

    return (
        trading[REQUIRED_COLUMNS]
        .sort_values("datetime")
        .reset_index(drop=True)
    )


def positions(transactions: pd.DataFrame) -> pd.DataFrame:
    """Posiciones actuales derivadas de las transacciones.

    Devuelve una fila por activo con unidades, coste total desembolsado
    (comisiones incluidas), coste medio por unidad, fecha de primera compra
    y el ticker de yfinance correspondiente (None si el ISIN no está mapeado).
    """
    acumulado: dict[str, dict] = {}
    for tx in transactions.itertuples(index=False):
        pos = acumulado.setdefault(
            tx.symbol,
            {
                "symbol": tx.symbol,
                "name": tx.name,
                "asset_class": tx.asset_class,
                "shares": 0.0,
                "cost_total": 0.0,
                "first_buy": tx.datetime,
            },
        )
        if tx.type == "BUY":
            pos["shares"] += tx.shares
            # amount y fee vienen negativos (salida de caja)
            pos["cost_total"] += -tx.amount - tx.fee
        elif tx.type == "SELL":
            if tx.shares > pos["shares"] + 1e-9:
                raise ValueError(
                    f"Venta de {tx.shares} unidades de {tx.symbol} el "
                    f"{tx.datetime.date()} pero solo hay {pos['shares']} en cartera. "
                    "¿Export incompleto?"
                )
            fraccion = tx.shares / pos["shares"]
            pos["cost_total"] *= 1 - fraccion
            pos["shares"] -= tx.shares

    filas = [pos for pos in acumulado.values() if pos["shares"] > 1e-9]
    if not filas:
        return pd.DataFrame(
            columns=["symbol", "name", "asset_class", "yf_ticker", "shares",
                     "cost_total", "avg_cost", "first_buy"]
        )

    resultado = pd.DataFrame(filas)
    resultado["avg_cost"] = resultado["cost_total"] / resultado["shares"]
    resultado["yf_ticker"] = [
        isin_map.to_yf_ticker(s, ac)
        for s, ac in zip(resultado["symbol"], resultado["asset_class"])
    ]
    return (
        resultado[["symbol", "name", "asset_class", "yf_ticker", "shares",
                   "cost_total", "avg_cost", "first_buy"]]
        .sort_values("cost_total", ascending=False)
        .reset_index(drop=True)
    )


def load_positions(path: Path | str) -> pd.DataFrame:
    """Atajo: posiciones actuales directamente desde el CSV del export."""
    return positions(load_transactions(path))
