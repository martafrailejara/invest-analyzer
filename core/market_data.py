"""Ingesta de datos de mercado (precios y dividendos) con caché local en parquet.

Los precios se descargan de yfinance y se guardan por ticker en ``data/market/``,
junto a un sidecar ``.meta.json`` con el rango de fechas ya cubierto. Si una
petición cae dentro del rango cubierto se sirve desde disco; si lo desborda, se
descarga la unión de ambos rangos y se reemplaza la caché.

Todas las funciones aceptan un ``downloader`` inyectable para testear sin red.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path
from typing import Callable, Iterable

import pandas as pd

DEFAULT_CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "market"

# (ticker, start, end) -> serie de precios de cierre ajustados
PriceDownloader = Callable[[str, pd.Timestamp, pd.Timestamp], pd.Series]
# ticker -> serie de dividendos por acción (histórico completo)
DividendDownloader = Callable[[str], pd.Series]


FX_EURUSD = "EURUSD=X"  # dólares por euro

SUFIJOS_EUR = (".DE", ".AS", ".PA", ".MC", ".MI", ".BR", ".LS", ".VI", ".HE", "-EUR")
INDICES_USD = {"^GSPC", "^DJI", "^IXIC", "^NDX"}


def currency_of(ticker: str) -> str:
    """Divisa de cotización estimada por el sufijo del ticker: 'EUR' o 'USD'."""
    t = ticker.upper()
    if t.endswith(SUFIJOS_EUR) or t in ("^IBEX", "^STOXX50E") or t == FX_EURUSD:
        return "EUR"
    if t in INDICES_USD or ("." not in t and "^" not in t) or t.endswith("-USD"):
        return "USD"  # tickers sin sufijo: bolsas americanas
    return "EUR"  # sufijos europeos no listados: se asume EUR


def get_prices(
    tickers: Iterable[str],
    start,
    end,
    *,
    cache_dir: Path | str | None = None,
    downloader: PriceDownloader | None = None,
    convert_to_eur: bool = True,
) -> pd.DataFrame:
    """Precios de cierre ajustados: índice de fechas, una columna por ticker.

    Los tickers que cotizan en USD se convierten a EUR con el cruce
    ``EURUSD=X`` (alineado por fecha), para no sumar divisas distintas.
    """
    start_ts, end_ts = _parse_range(start, end)
    hoy = pd.Timestamp.today().normalize()
    if start_ts > hoy:
        raise ValueError(f"El rango empieza en el futuro ({start_ts.date()}): no hay datos que consultar")
    # no existen precios futuros: recortar evita registrar cobertura falsa en caché
    end_ts = min(end_ts, hoy)
    cache = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    fetch = downloader or _yf_download_prices

    fx = None
    series = []
    for ticker in tickers:
        serie = _cached_prices(ticker, start_ts, end_ts, cache, fetch)
        recorte = serie.loc[start_ts:end_ts]
        if recorte.empty:
            raise ValueError(
                f"Sin datos de precios para '{ticker}' entre {start_ts.date()} "
                f"y {end_ts.date()}. ¿Es un ticker válido de yfinance? "
                "(ver core/isin_map.py)"
            )
        if (end_ts - recorte.index.max()).days > 5:
            warnings.warn(
                f"'{ticker}' solo tiene datos hasta {recorte.index.max().date()} "
                f"(se pidió hasta {end_ts.date()})"
            )
        if convert_to_eur and currency_of(ticker) == "USD":
            if fx is None:
                fx = _cached_prices(FX_EURUSD, start_ts, end_ts, cache, fetch)
            tasa = fx.reindex(recorte.index).ffill().bfill()
            recorte = recorte / tasa
            recorte.name = ticker
            warnings.warn(f"'{ticker}' cotiza en USD: convertido a EUR con {FX_EURUSD}")
        series.append(recorte)
    return pd.concat(series, axis=1).sort_index()


def get_dividends(
    ticker: str,
    *,
    cache_dir: Path | str | None = None,
    downloader: DividendDownloader | None = None,
    refresh: bool = False,
) -> pd.Series:
    """Histórico completo de dividendos por acción del ticker.

    Una serie vacía es un resultado válido (ETFs de acumulación, cripto).
    La caché no caduca sola: usa ``refresh=True`` para forzar la descarga.
    """
    cache = Path(cache_dir) if cache_dir else DEFAULT_CACHE_DIR
    fetch = downloader or _yf_download_dividends
    fichero = cache / f"{_safe_filename(ticker)}.dividends.parquet"

    if fichero.exists() and not refresh:
        return pd.read_parquet(fichero)[ticker]

    serie = fetch(ticker)
    serie = serie.astype("float64")
    serie.name = ticker
    cache.mkdir(parents=True, exist_ok=True)
    serie.to_frame().to_parquet(fichero)
    return serie


def _cached_prices(
    ticker: str,
    start: pd.Timestamp,
    end: pd.Timestamp,
    cache_dir: Path,
    fetch: PriceDownloader,
) -> pd.Series:
    fichero = cache_dir / f"{_safe_filename(ticker)}.parquet"
    meta = cache_dir / f"{_safe_filename(ticker)}.meta.json"

    hoy = pd.Timestamp.today().normalize()
    if fichero.exists() and meta.exists():
        cubierto = json.loads(meta.read_text())
        cub_start = pd.Timestamp(cubierto["start"])
        cub_end = pd.Timestamp(cubierto["end"])
        if cub_end <= hoy:  # una cobertura futura es imposible: meta corrupto, se refresca
            if cub_start <= start and end <= cub_end:
                return pd.read_parquet(fichero)[ticker]
            start = min(start, cub_start)
            end = max(end, cub_end)

    serie = fetch(ticker, start, end)
    if serie.empty:
        raise ValueError(
            f"yfinance no devolvió datos para '{ticker}' entre {start.date()} "
            f"y {end.date()}. ¿Es un ticker válido? (ver core/isin_map.py)"
        )
    serie = serie.astype("float64")
    serie.name = ticker
    cache_dir.mkdir(parents=True, exist_ok=True)
    serie.to_frame().to_parquet(fichero)
    end_cubierto = min(end, hoy)  # nunca registrar cobertura futura: dejaría la caché estancada
    meta.write_text(json.dumps({"start": str(start.date()), "end": str(end_cubierto.date())}))
    return serie


def _yf_download_prices(ticker: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.Series:
    import yfinance as yf

    hist = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    if hist.empty:
        return pd.Series(dtype="float64")
    serie = hist["Close"]
    serie.index = serie.index.tz_localize(None).normalize()
    return serie


def _yf_download_dividends(ticker: str) -> pd.Series:
    import yfinance as yf

    serie = yf.Ticker(ticker).dividends
    if serie.empty:
        return pd.Series(dtype="float64")
    serie.index = serie.index.tz_localize(None).normalize()
    return serie


def _parse_range(start, end) -> tuple[pd.Timestamp, pd.Timestamp]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end)
    if start_ts >= end_ts:
        raise ValueError(f"Rango de fechas inválido: start={start_ts.date()} >= end={end_ts.date()}")
    return start_ts, end_ts


def _safe_filename(ticker: str) -> str:
    return "".join(c if c.isalnum() or c in ".-^" else "_" for c in ticker)
