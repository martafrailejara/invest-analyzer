"""Catálogo de tickers frecuentes con su nombre completo.

Alimenta el autocompletado de los formularios (datalist) y el helper que
muestra el nombre del activo al pasar el ratón. Tickers de yfinance,
priorizando líneas europeas en EUR. Amplíalo libremente: es solo una ayuda
de escritura, cualquier ticker válido de yfinance funciona aunque no esté.
"""

CATALOGO = {
    # ETFs indexados (EUR)
    "SXR8.DE": "iShares Core S&P 500 UCITS ETF (Acc) — Xetra",
    "EUNL.DE": "iShares Core MSCI World UCITS ETF (Acc) — Xetra",
    "VWCE.DE": "Vanguard FTSE All-World UCITS ETF (Acc) — Xetra",
    "VUSA.AS": "Vanguard S&P 500 UCITS ETF (Dist) — Ámsterdam",
    "SXRV.DE": "iShares Nasdaq 100 UCITS ETF (Acc) — Xetra",
    "EXS1.DE": "iShares Core DAX UCITS ETF (Acc) — Xetra",
    "CS1.PA": "Amundi IBEX 35 UCITS ETF (Acc) — París",
    "LYXIB.MC": "Amundi IBEX 35 UCITS ETF (Dist) — Madrid",
    "EIMI.DE": "iShares Core MSCI EM IMI UCITS ETF (Acc) — Xetra",
    "IUSN.DE": "iShares MSCI World Small Cap UCITS ETF (Acc) — Xetra",
    "VAGF.DE": "Vanguard Global Aggregate Bond EUR Hedged (Acc) — Xetra",
    # Acciones España
    "TEF.MC": "Telefónica — Madrid",
    "SAN.MC": "Banco Santander — Madrid",
    "BBVA.MC": "BBVA — Madrid",
    "ITX.MC": "Inditex — Madrid",
    "IBE.MC": "Iberdrola — Madrid",
    "REP.MC": "Repsol — Madrid",
    # Acciones EEUU (cotizan en USD)
    "AAPL": "Apple — Nasdaq (USD)",
    "MSFT": "Microsoft — Nasdaq (USD)",
    "NVDA": "NVIDIA — Nasdaq (USD)",
    "AMZN": "Amazon — Nasdaq (USD)",
    "GOOGL": "Alphabet — Nasdaq (USD)",
    # Índices (no invertibles directamente)
    "^GSPC": "S&P 500 — índice (USD)",
    "^IBEX": "IBEX 35 — índice",
    # Cripto
    "BTC-EUR": "Bitcoin en euros",
    "ETH-EUR": "Ethereum en euros",
}
