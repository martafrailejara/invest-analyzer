"""Fiscalidad verificada contra casos FIFO y tramos calculados a mano."""

from pathlib import Path

import pytest

from modules import taxes

FIXTURES = Path(__file__).parent / "fixtures"
SINTETICO = FIXTURES / "transacciones_sintetico.csv"


def test_cuota_ahorro_por_tramos():
    # 10.000 €: 6.000×19% + 4.000×21% = 1.140 + 840 = 1.980 (a mano)
    assert taxes.cuota_ahorro(10_000) == pytest.approx(1_980.0)
    # dentro del primer tramo
    assert taxes.cuota_ahorro(1_000) == pytest.approx(190.0)
    # 60.000: 1.140 + 44.000×21% + 10.000×23% = 1.140 + 9.240 + 2.300
    assert taxes.cuota_ahorro(60_000) == pytest.approx(12_680.0)
    assert taxes.cuota_ahorro(0) == 0.0


def test_fifo_del_fixture_cuadra_a_mano():
    """Fixture: compra 10 uds (coste 101 → 10,10/ud), compra 10 (coste 200 →
    20,00/ud), vende 5 a 22 (neto 109 → 21,80/ud).

    FIFO: las 5 salen del primer lote → coste 50,50 → plusvalía 58,50.
    """
    res = taxes.run(SINTETICO)

    venta = res["realizadas"][0]
    assert venta["coste"] == pytest.approx(50.50)
    assert venta["importe"] == pytest.approx(109.0)
    assert venta["plusvalia"] == pytest.approx(58.50)
    assert res["por_anio"][2025] == pytest.approx(58.50)
    assert res["cuota_por_anio"][2025] == pytest.approx(58.50 * 0.19)

    # lotes vivos: 5 uds a 10,10 + 10 uds a 20,00 + 0.5 BTC
    etf = [l for l in res["lotes"] if l["symbol"] == "XX0000000001"]
    assert [round(l["unidades"], 4) for l in etf] == [5.0, 10.0]
    assert etf[0]["coste_unitario"] == pytest.approx(10.10)


def test_simulador_de_venta_fifo():
    """Vender 8 uds a 30 €: consume las 5 restantes del lote 1 y 3 del lote 2.

    Coste = 5×10,10 + 3×20,00 = 110,50 → plusvalía = 240 − 110,50 = 129,50.
    """
    res = taxes.simulate_sale(SINTETICO, "XX0000000001", 8, 30.0)
    assert res["importe"] == pytest.approx(240.0)
    assert res["coste_fifo"] == pytest.approx(110.50)
    assert res["plusvalia"] == pytest.approx(129.50)
    assert res["cuota"] == pytest.approx(129.50 * 0.19)
    assert len(res["lotes_consumidos"]) == 2


def test_simulador_valida_unidades():
    with pytest.raises(ValueError, match="Solo hay"):
        taxes.simulate_sale(SINTETICO, "XX0000000001", 999, 30.0)
    with pytest.raises(ValueError, match="No hay unidades"):
        taxes.simulate_sale(SINTETICO, "NOEXISTE", 1, 30.0)
    with pytest.raises(ValueError, match="mayores que 0"):
        taxes.simulate_sale(SINTETICO, "XX0000000001", 0, 30.0)


def test_perdida_no_genera_cuota():
    # vender 5 uds a 5 € (por debajo del coste): plusvalía negativa, cuota 0
    res = taxes.simulate_sale(SINTETICO, "XX0000000001", 5, 5.0)
    assert res["plusvalia"] < 0
    assert res["cuota"] == 0.0
