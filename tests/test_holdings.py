"""Mi cartera verificada contra un caso calculado a mano con precios constantes."""

from pathlib import Path

import pandas as pd
import pytest

from core import isin_map
from modules import holdings

FIXTURES = Path(__file__).parent / "fixtures"
SINTETICO = FIXTURES / "transacciones_sintetico.csv"

PRECIOS = {"ETF.XX": 30.0, "BTC-EUR": 22000.0}


@pytest.fixture()
def isin_de_prueba(monkeypatch):
    monkeypatch.setitem(isin_map.ISIN_TO_TICKER, "XX0000000001", "ETF.XX")


def downloader_constante(ticker, start, end):
    fechas = pd.bdate_range(start, end) if ticker != "BTC-EUR" else pd.date_range(start, end)
    return pd.Series([PRECIOS[ticker]] * len(fechas), index=fechas)


def test_valoracion_cuadra_a_mano(tmp_path, isin_de_prueba):
    """Fixture: quedan 15 uds del ETF (coste 225.75) y 0.5 BTC (coste 10001).

    A precios constantes 30 / 22000:
    - ETF: 15 × 30 = 450 → P&L = 450 − 225.75 = +224.25
    - BTC: 0.5 × 22000 = 11000 → P&L = 11000 − 10001 = +999
    - aportado neto = 101 + 200 + 10001 − 109 (venta) = 10193
    - valor total 11450 → P&L total 1257
    """
    res = holdings.run(SINTETICO, cache_dir=tmp_path, downloader=downloader_constante)

    assert res["valor_total"] == pytest.approx(11450.0)
    assert res["aportado_neto"] == pytest.approx(10193.0)
    assert res["pnl_total"] == pytest.approx(1257.0)

    etf = next(p for p in res["posiciones"] if p["ticker"] == "ETF.XX")
    assert etf["valor"] == pytest.approx(450.0)
    assert etf["pnl"] == pytest.approx(224.25)
    assert etf["peso"] == pytest.approx(450 / 11450)

    btc = next(p for p in res["posiciones"] if p["ticker"] == "BTC-EUR")
    assert btc["pnl"] == pytest.approx(999.0)


def test_curva_termina_en_el_valor_total(tmp_path, isin_de_prueba):
    res = holdings.run(SINTETICO, cache_dir=tmp_path, downloader=downloader_constante)
    assert res["curva"]["valor"].iloc[-1] == pytest.approx(res["valor_total"])
    assert res["curva"]["invertido"].iloc[-1] == pytest.approx(res["aportado_neto"])
    # la curva de valor arranca en la primera compra, no en cero perpetuo
    assert res["curva"]["valor"].iloc[0] > 0


def test_ganancia_y_flujos_mensuales(tmp_path, isin_de_prueba):
    """La ganancia aísla la parte de la curva que no es aportación, y el flujo
    mensual refleja las compras (ene 101, mar 200+10001) y la venta (may −109)."""
    res = holdings.run(SINTETICO, cache_dir=tmp_path, downloader=downloader_constante)

    assert res["curva"]["ganancia"].iloc[-1] == pytest.approx(res["pnl_total"])
    assert res["flujo_mensual"]["2025-01"] == pytest.approx(101.0)
    assert res["flujo_mensual"]["2025-03"] == pytest.approx(10201.0)
    assert res["flujo_mensual"]["2025-05"] == pytest.approx(-109.0)

    # precios constantes: sin variación diaria; fixture antiguo: sin aportes recientes
    assert res["variacion_dia"] == pytest.approx(0.0)
    assert res["aportado_30d"] == pytest.approx(0.0)
    for p in res["posiciones"]:
        assert p["var_dia"] == pytest.approx(0.0)

    # historial de transacciones: 4 de trading, la más reciente primero
    assert len(res["transacciones"]) == 4
    assert res["transacciones"][0]["tipo"] == "Venta"
    assert res["transacciones"][0]["caja"] == pytest.approx(109.0)
    assert res["transacciones"][-1]["caja"] == pytest.approx(-101.0)


def test_sin_posiciones_mapeadas(tmp_path, monkeypatch):
    monkeypatch.delitem(isin_map.ISIN_TO_TICKER, "XX0000000001", raising=False)

    def downloader(ticker, start, end):
        fechas = pd.date_range(start, end)
        return pd.Series([22000.0] * len(fechas), index=fechas)

    # solo BTC queda mapeada: no lanza; sin_mapear informa del ISIN ausente
    res = holdings.run(SINTETICO, cache_dir=tmp_path, downloader=downloader)
    assert res["sin_mapear"] == ["XX0000000001"]
    assert len(res["posiciones"]) == 1
