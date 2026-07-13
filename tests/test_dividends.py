"""Agregador de dividendos verificado contra un caso calculado a mano."""

from pathlib import Path

import pandas as pd
import pytest

from core import isin_map
from modules import dividends

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture()
def isin_de_prueba(monkeypatch):
    monkeypatch.setitem(isin_map.ISIN_TO_TICKER, "XX0000000001", "DIVTEST.XX")


def dividendos_conocidos(ticker):
    """Tres ex-fechas: la primera entre las dos compras del fixture, la segunda
    después de ambas, la tercera tras la venta de 5 unidades."""
    assert ticker == "DIVTEST.XX"
    return pd.Series(
        [0.50, 0.50, 1.00],
        index=pd.DatetimeIndex(["2025-02-14", "2025-03-20", "2025-06-16"]),
    )


def test_cobrado_cuadra_a_mano(tmp_path, isin_de_prueba):
    """Fixture sintético: compra 10 uds (ene), compra 10 más (mar-03), vende 5 (may-06).

    - ex 2025-02-14: 10 uds × 0.50 = 5.00 €
    - ex 2025-03-20: 20 uds × 0.50 = 10.00 €
    - ex 2025-06-16: 15 uds × 1.00 = 15.00 €   → total 30.00 €
    """
    res = dividends.run(FIXTURES / "transacciones_sintetico.csv",
                        cache_dir=tmp_path, downloader=dividendos_conocidos)

    etf = next(p for p in res["posiciones"] if p["symbol"] == "XX0000000001")
    assert etf["cobrado_total"] == pytest.approx(30.0)
    assert etf["cobrado_por_anio"] == {2025: pytest.approx(30.0)}
    assert res["por_anio"][2025] == pytest.approx(30.0)
    assert res["cobrado_total"] == pytest.approx(30.0)


def test_proyeccion_y_yield_on_cost(tmp_path, isin_de_prueba, monkeypatch):
    """La proyección es el dps de los últimos 12 meses × unidades actuales."""
    # fijar "hoy" no es trivial sin congelar el reloj; usamos ex-fechas recientes
    hoy = pd.Timestamp.today().normalize()
    recientes = pd.Series(
        [0.50, 1.00],
        index=pd.DatetimeIndex([hoy - pd.Timedelta(days=200), hoy - pd.Timedelta(days=30)]),
    )
    res = dividends.run(FIXTURES / "transacciones_sintetico.csv",
                        cache_dir=tmp_path, downloader=lambda t: recientes)

    etf = next(p for p in res["posiciones"] if p["symbol"] == "XX0000000001")
    # quedan 15 unidades; dps 12m = 1.50 → proyección 22.50 €
    assert etf["dps_12m"] == pytest.approx(1.50)
    assert etf["proyeccion"] == pytest.approx(22.50)
    # coste tras la venta: 301 × 0.75 = 225.75 → yoc = 22.50 / 225.75
    assert etf["yoc"] == pytest.approx(22.50 / 225.75)
    assert res["proyeccion_total"] == pytest.approx(22.50)


def test_cripto_fila_a_cero_sin_llamar_a_yfinance(tmp_path, isin_de_prueba):
    llamadas = []

    def downloader(ticker):
        llamadas.append(ticker)
        return pd.Series(dtype="float64")

    res = dividends.run(FIXTURES / "transacciones_sintetico.csv",
                        cache_dir=tmp_path, downloader=downloader)
    btc = next(p for p in res["posiciones"] if p["symbol"] == "BTC")
    assert btc["cobrado_total"] == 0.0 and btc["proyeccion"] == 0.0
    assert "BTC-EUR" not in llamadas


def test_isin_sin_mapear_se_reporta(tmp_path, monkeypatch):
    monkeypatch.delitem(isin_map.ISIN_TO_TICKER, "XX0000000001", raising=False)
    res = dividends.run(FIXTURES / "transacciones_sintetico.csv",
                        cache_dir=tmp_path, downloader=lambda t: pd.Series(dtype="float64"))
    assert res["sin_mapear"] == ["XX0000000001"]
