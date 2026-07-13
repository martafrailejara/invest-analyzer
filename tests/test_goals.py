"""Metas: probabilidad de alcanzar un objetivo, verificada con casos deterministas."""

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from core import isin_map
from modules import goals

FIXTURES = Path(__file__).parent / "fixtures"
SINTETICO = FIXTURES / "transacciones_sintetico.csv"


@pytest.fixture()
def isin_de_prueba(monkeypatch):
    monkeypatch.setitem(isin_map.ISIN_TO_TICKER, "XX0000000001", "ETF.XX")


def downloader_mensual_constante(ticker, start, end):
    """Precio que crece exactamente un 1 % cada mes de calendario (sin varianza)."""
    fechas = pd.date_range(start, end, freq="MS")
    if ticker == "BTC-EUR":
        base = 22000.0
    else:
        base = 30.0
    serie = pd.Series([base * (1.01 ** i) for i in range(len(fechas))], index=fechas)
    return serie


def test_meta_determinista(tmp_path, isin_de_prueba):
    """Con retorno mensual constante, la probabilidad es 0 o 1 según el objetivo."""
    anio = date.today().year + 5
    facil = goals.run(SINTETICO, importe_objetivo=1000, anio_objetivo=anio,
                      aportacion_mensual=100, n_sims=100, seed=1,
                      cache_dir=tmp_path, downloader=downloader_mensual_constante)
    # el valor actual ya supera con mucho un objetivo de 1000 €
    assert facil["progreso"] == 1.0
    base = next(v for v in facil["variantes"] if v["factor"] == 1.0)
    assert base["prob"] == pytest.approx(1.0)

    imposible = goals.run(SINTETICO, importe_objetivo=10_000_000, anio_objetivo=anio,
                          aportacion_mensual=100, n_sims=100, seed=1,
                          cache_dir=tmp_path, downloader=downloader_mensual_constante)
    base = next(v for v in imposible["variantes"] if v["factor"] == 1.0)
    assert base["prob"] == pytest.approx(0.0)


def test_aportar_mas_nunca_reduce_la_probabilidad(tmp_path, isin_de_prueba):
    anio = date.today().year + 10
    res = goals.run(SINTETICO, importe_objetivo=100_000, anio_objetivo=anio,
                    aportacion_mensual=200, n_sims=300, seed=3,
                    cache_dir=tmp_path, downloader=downloader_mensual_constante)
    probs = [v["prob"] for v in sorted(res["variantes"], key=lambda v: v["factor"])]
    assert probs == sorted(probs)  # monótona con la aportación
    assert len(res["variantes"]) == 4


def test_validaciones(tmp_path, isin_de_prueba):
    anio = date.today().year + 5
    with pytest.raises(ValueError, match="importe objetivo"):
        goals.run(SINTETICO, importe_objetivo=0, anio_objetivo=anio, aportacion_mensual=100)
    with pytest.raises(ValueError, match="año objetivo"):
        goals.run(SINTETICO, importe_objetivo=1000, anio_objetivo=date.today().year,
                  aportacion_mensual=100)
