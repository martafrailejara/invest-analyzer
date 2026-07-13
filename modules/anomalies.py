"""Detector de anomalías de precio: movimientos inusuales frente al histórico.

Dos métodos conmutables:

- **z-score** (estadístico): z del retorno diario contra la media y desviación
  de una ventana móvil *previa* (shift, sin lookahead). Anómalo si |z| supera
  el umbral.
- **Isolation Forest** (ML): aísla observaciones raras en el espacio
  (retorno, volatilidad reciente); marca como anómala una fracción configurable
  (``contamination``). No supervisado, capta combinaciones raras que un umbral
  fijo sobre el retorno no ve.

Las bandas de Bollinger (media ± 2σ, 20 sesiones) acompañan la visualización
en ambos métodos.
"""

from __future__ import annotations

import numpy as np
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
    method: str = "zscore",
    window: int = 60,
    threshold: float = 3.0,
    contamination: float = 0.02,
    cache_dir=None,
    downloader=None,
) -> dict:
    """Detección sobre precios reales (con caché local)."""
    prices = market_data.get_prices([ticker], start, end,
                                    cache_dir=cache_dir, downloader=downloader)[ticker]
    return detect(prices, method=method, window=window,
                  threshold=threshold, contamination=contamination)


def detect(
    prices: pd.Series,
    *,
    method: str = "zscore",
    window: int = 60,
    threshold: float = 3.0,
    contamination: float = 0.02,
) -> dict:
    if method not in ("zscore", "iforest"):
        raise ValueError("method debe ser 'zscore' o 'iforest'")
    if window < MIN_WINDOW:
        raise ValueError(f"La ventana debe ser de al menos {MIN_WINDOW} sesiones")
    if method == "zscore" and threshold <= 0:
        raise ValueError("El umbral de desviaciones debe ser mayor que 0")
    if method == "iforest" and not 0 < contamination < 0.5:
        raise ValueError("La contaminación debe estar entre 0 y 0.5")
    prices = prices.dropna()
    if len(prices) < window + 20:
        raise ValueError(
            f"Histórico insuficiente: {len(prices)} sesiones para una ventana de {window} "
            f"(mínimo {window + 20})"
        )

    retornos = metrics.simple_returns(prices)
    if method == "zscore":
        anomalos, score, score_label = _zscore(retornos, window, threshold)
    else:
        anomalos, score, score_label = _iforest(retornos, window, contamination)

    bollinger_media = prices.rolling(BOLLINGER_WINDOW).mean()
    bollinger_std = prices.rolling(BOLLINGER_WINDOW).std(ddof=1)

    eventos = [
        {
            "fecha": fecha,
            "precio": float(prices[fecha]),
            "retorno": float(retornos[fecha]),
            "score": float(score[fecha]),
        }
        for fecha in retornos.index[anomalos.fillna(False)]
    ]

    dias_evaluados = int(score.notna().sum())
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
        "method": method,
        "score_label": score_label,
        "window": window,
        "threshold": threshold,
        "contamination": contamination,
    }


def _zscore(retornos, window, threshold):
    """z del retorno contra la ventana previa (sin incluir el día evaluado)."""
    media_previa = retornos.rolling(window).mean().shift(1)
    std_previa = retornos.rolling(window).std(ddof=1).shift(1)
    z = (retornos - media_previa) / std_previa
    return z.abs() > threshold, z, "z-score"


def _iforest(retornos, window, contamination):
    """Isolation Forest sobre (retorno, volatilidad reciente)."""
    from sklearn.ensemble import IsolationForest

    vol = retornos.rolling(window).std(ddof=1).shift(1)
    features = pd.DataFrame({"ret": retornos, "vol": vol}).dropna()
    modelo = IsolationForest(contamination=contamination, random_state=0, n_estimators=200)
    etiquetas = modelo.fit_predict(features.to_numpy())
    # score_samples: cuanto más bajo, más anómalo; lo invertimos para que
    # "más alto = más anómalo", coherente con el |z|
    bruto = pd.Series(-modelo.score_samples(features.to_numpy()), index=features.index)
    score = bruto.reindex(retornos.index)
    anomalos = pd.Series(etiquetas == -1, index=features.index).reindex(retornos.index, fill_value=False)
    return anomalos, score, "score de aislamiento"
