from pathlib import Path

import pandas as pd
import pytest

from core import portfolio

FIXTURES = Path(__file__).parent / "fixtures"
SINTETICO = FIXTURES / "transacciones_sintetico.csv"


def test_load_transactions_filtra_ruido_de_cash():
    txs = portfolio.load_transactions(SINTETICO)
    # el fixture tiene 7 filas: 3 de cash (top-up, tarjeta, transferencia) y 4 de trading
    assert len(txs) == 4
    assert set(txs["type"]) == {"BUY", "SELL"}
    assert txs["datetime"].is_monotonic_increasing


def test_load_transactions_normaliza_numericos():
    txs = portfolio.load_transactions(SINTETICO)
    primera = txs.iloc[0]
    assert primera["shares"] == 10.0
    assert primera["price"] == 10.0
    assert primera["amount"] == -100.0
    assert primera["fee"] == -1.0
    # fee vacía en el CSV pasa a 0.0, no NaN
    assert txs.iloc[1]["fee"] == 0.0


def test_load_transactions_columnas_incorrectas(tmp_path):
    malo = tmp_path / "malo.csv"
    malo.write_text("a,b,c\n1,2,3\n")
    with pytest.raises(ValueError, match="faltan las columnas"):
        portfolio.load_transactions(malo)


def test_load_transactions_avisa_de_tipos_desconocidos():
    with pytest.warns(UserWarning, match="DIVIDEND"):
        txs = portfolio.load_transactions(FIXTURES / "transacciones_tipo_desconocido.csv")
    # la fila DIVIDEND se descarta, la BUY se conserva
    assert len(txs) == 1
    assert txs.iloc[0]["type"] == "BUY"


def test_positions_acumula_compras_y_ventas():
    pos = portfolio.load_positions(SINTETICO)
    assert len(pos) == 2

    etf = pos[pos["symbol"] == "XX0000000001"].iloc[0]
    # compras: 10@10 (fee 1) + 10@20 = coste 301; venta de 5/20 -> queda 75%
    assert etf["shares"] == pytest.approx(15.0)
    assert etf["cost_total"] == pytest.approx(301 * 0.75)
    assert etf["avg_cost"] == pytest.approx(301 * 0.75 / 15)
    assert etf["first_buy"] == pd.Timestamp("2025-01-03T10:00:00Z")

    btc = pos[pos["symbol"] == "BTC"].iloc[0]
    assert btc["shares"] == pytest.approx(0.5)
    assert btc["cost_total"] == pytest.approx(10001.0)


def test_positions_mapea_tickers_yfinance():
    pos = portfolio.load_positions(SINTETICO)
    btc = pos[pos["symbol"] == "BTC"].iloc[0]
    assert btc["yf_ticker"] == "BTC-EUR"
    # ISIN ficticio sin entrada en isin_map -> valor nulo
    etf = pos[pos["symbol"] == "XX0000000001"].iloc[0]
    assert pd.isna(etf["yf_ticker"])


def test_positions_venta_sin_unidades_suficientes(tmp_path):
    txs = portfolio.load_transactions(SINTETICO)
    venta_excesiva = txs.copy()
    venta_excesiva.loc[venta_excesiva["type"] == "SELL", "shares"] = 999.0
    with pytest.raises(ValueError, match="solo hay"):
        portfolio.positions(venta_excesiva)
