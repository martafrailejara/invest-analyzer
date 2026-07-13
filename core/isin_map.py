"""Mapeo de símbolos del export de Trade Republic a tickers de yfinance.

Trade Republic identifica los fondos/acciones por ISIN, pero yfinance no
resuelve ISINs de forma fiable, así que el mapeo se mantiene a mano aquí.
Al añadir una posición nueva a la cartera, añade su ISIN a esta tabla
(preferiblemente la cotización en EUR de una bolsa europea).
"""

from __future__ import annotations

ISIN_TO_TICKER = {
    # iShares Core S&P 500 UCITS ETF USD (Acc) — Xetra, EUR
    "IE00B5BMR087": "SXR8.DE",
    # Amundi IBEX 35 UCITS ETF Acc — Euronext París, EUR
    "FR0010655746": "CS1.PA",
    # Vanguard S&P 500 UCITS ETF (Dist) — Ámsterdam, EUR (cartera de ejemplo)
    "IE00B3XXRP09": "VUSA.AS",
    # Telefónica — Bolsa de Madrid, EUR (cartera de ejemplo)
    "ES0178430E18": "TEF.MC",
}


def to_yf_ticker(symbol: str, asset_class: str) -> str | None:
    """Ticker de yfinance para un símbolo del export, o None si no está mapeado.

    Las criptos vienen con símbolo corto (BTC, ETH…) y en yfinance cotizan
    como pares; usamos el par contra EUR, la divisa de la cuenta.
    """
    if asset_class == "CRYPTO":
        return f"{symbol}-EUR"
    return ISIN_TO_TICKER.get(symbol)
