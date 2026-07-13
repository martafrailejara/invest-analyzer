"""Conversión automática de tickers USD a EUR en la capa de datos."""

import pandas as pd
import pytest

from core import market_data


def test_deteccion_de_divisa():
    assert market_data.currency_of("SXR8.DE") == "EUR"
    assert market_data.currency_of("LYXIB.MC") == "EUR"
    assert market_data.currency_of("BTC-EUR") == "EUR"
    assert market_data.currency_of("^IBEX") == "EUR"
    assert market_data.currency_of("AAPL") == "USD"
    assert market_data.currency_of("^GSPC") == "USD"
    assert market_data.currency_of("BTC-USD") == "USD"


def downloader(ticker, start, end):
    fechas = pd.bdate_range(start, end)
    if ticker == market_data.FX_EURUSD:
        return pd.Series([1.25] * len(fechas), index=fechas)  # 1 EUR = 1.25 USD
    return pd.Series([100.0] * len(fechas), index=fechas)


def test_ticker_usd_se_convierte_a_eur(tmp_path):
    """AAPL a 100 USD con EURUSD=1.25 son 80 EUR, con aviso de conversión."""
    with pytest.warns(UserWarning, match="cotiza en USD"):
        px = market_data.get_prices(["AAPL", "SXR8.DE"], "2024-01-01", "2024-02-01",
                                    cache_dir=tmp_path, downloader=downloader)
    assert px["AAPL"].iloc[-1] == pytest.approx(80.0)
    assert px["SXR8.DE"].iloc[-1] == pytest.approx(100.0)  # EUR intacto


def test_conversion_desactivable(tmp_path):
    px = market_data.get_prices(["AAPL"], "2024-01-01", "2024-02-01",
                                cache_dir=tmp_path, downloader=downloader,
                                convert_to_eur=False)
    assert px["AAPL"].iloc[-1] == pytest.approx(100.0)
