"""Detector de anomalías de precio: movimientos inusuales frente al histórico.

Método: z-score del retorno diario contra la media y desviación típica de una
ventana móvil *previa* (sin incluir el propio día, para no contaminar la
referencia con el movimiento que se está evaluando). Un día es anómalo si
|z| supera el umbral. Las bandas de Bollinger (media ± 2σ del precio, 20
sesiones) se calculan para acompañar la visualización.
"""

from __future__ import annotations

import pandas as pd

from core import market_data, metrics

BOLLINGER_WINDOW = 20
BOLLINGER_STD = 2.0
MIN_WINDOW = 10


def run(
    ticker: str,
    start,
    end,
    *,
    window: int = 60,
    threshold: float = 3.0,
    cache_dir=None,
    downloader=None,
) -> dict:
    """Detección sobre precios reales (con caché local)."""
    prices = market_data.get_prices([ticker], start, end,
                                    cache_dir=cache_dir, downloader=downloader)[ticker]
    return detect(prices, window=window, threshold=threshold)


def detect(prices: pd.Series, *, window: int = 60, threshold: float = 3.0) -> dict:
    if window < MIN_WINDOW:
        raise ValueError(f"La ventana debe ser de al menos {MIN_WINDOW} sesiones")
    if threshold <= 0:
        raise ValueError("El umbral de desviaciones debe ser mayor que 0")
    prices = prices.dropna()
    if len(prices) < window + 20:
        raise ValueError(
            f"Histórico insuficiente: {len(prices)} sesiones para una ventana de {window} "
            f"(mínimo {window + 20})"
        )

    retornos = metrics.simple_returns(prices)
    # estadísticos de la ventana anterior al día evaluado (shift evita lookahead)
    media_previa = retornos.rolling(window).mean().shift(1)
    std_previa = retornos.rolling(window).std(ddof=1).shift(1)
    z = (retornos - media_previa) / std_previa
    anomalos = z.abs() > threshold

    bollinger_media = prices.rolling(BOLLINGER_WINDOW).mean()
    bollinger_std = prices.rolling(BOLLINGER_WINDOW).std(ddof=1)

    eventos = [
        {
            "fecha": fecha,
            "precio": float(prices[fecha]),
            "retorno": float(retornos[fecha]),
            "z": float(z[fecha]),
        }
        for fecha in retornos.index[anomalos.fillna(False)]
    ]

    dias_evaluados = int(z.notna().sum())
    return {
        "precios": prices,
        "bollinger": {
            "media": bollinger_media,
            "superior": bollinger_media + BOLLINGER_STD * bollinger_std,
            "inferior": bollinger_media - BOLLINGER_STD * bollinger_std,
        },
        "eventos": eventos,
        "dias_evaluados": dias_evaluados,
        "tasa_anomalias": len(eventos) / dias_evaluados if dias_evaluados else 0.0,
        "window": window,
        "threshold": threshold,
    }
