"""Rangos con fechas futuras: recorte, caché no envenenada y auto-reparación."""

import json

import pandas as pd
import pytest

from core import market_data


def downloader_contado(contador):
    def descargar(ticker, start, end):
        contador[ticker] = contador.get(ticker, 0) + 1
        fechas = pd.bdate_range(start, min(end, pd.Timestamp.today().normalize()))
        return pd.Series([100.0 + i for i in range(len(fechas))], index=fechas)

    return descargar


def test_end_futuro_no_registra_cobertura_futura(tmp_path):
    futuro = (pd.Timestamp.today() + pd.Timedelta(days=365 * 30)).date().isoformat()
    market_data.get_prices(["AAA.DE"], "2024-01-01", futuro,
                           cache_dir=tmp_path, downloader=downloader_contado({}))
    meta = json.loads((tmp_path / "AAA.DE.meta.json").read_text())
    assert pd.Timestamp(meta["end"]) <= pd.Timestamp.today().normalize()


def test_end_futuro_se_sirve_de_cache(tmp_path):
    contador = {}
    args = dict(cache_dir=tmp_path, downloader=downloader_contado(contador))
    futuro = (pd.Timestamp.today() + pd.Timedelta(days=365)).date().isoformat()
    market_data.get_prices(["AAA.DE"], "2024-01-01", futuro, **args)
    market_data.get_prices(["AAA.DE"], "2024-01-01", futuro, **args)
    assert contador == {"AAA.DE": 1}  # el recorte a hoy hace la petición cacheable


def test_meta_corrupto_con_cobertura_futura_se_repara(tmp_path):
    """Una caché envenenada por el bug (end en 2056) se refresca sola."""
    contador = {}
    args = dict(cache_dir=tmp_path, downloader=downloader_contado(contador))
    market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-06-01", **args)

    # simular el meta envenenado que dejaba la versión anterior
    (tmp_path / "AAA.DE.meta.json").write_text(json.dumps({"start": "2024-01-01", "end": "2056-07-13"}))

    market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-06-01", **args)
    assert contador == {"AAA.DE": 2}  # no se fía del meta imposible: re-descarga
    meta = json.loads((tmp_path / "AAA.DE.meta.json").read_text())
    assert pd.Timestamp(meta["end"]) <= pd.Timestamp.today().normalize()


def test_start_futuro_error(tmp_path):
    futuro = (pd.Timestamp.today() + pd.Timedelta(days=30)).date().isoformat()
    fin = (pd.Timestamp.today() + pd.Timedelta(days=60)).date().isoformat()
    with pytest.raises(ValueError, match="empieza en el futuro"):
        market_data.get_prices(["AAA.DE"], futuro, fin,
                               cache_dir=tmp_path, downloader=downloader_contado({}))


def test_avisa_si_los_datos_acaban_antes_del_rango(tmp_path):
    def datos_viejos(ticker, start, end):
        fechas = pd.bdate_range("2024-01-01", "2024-03-01")
        return pd.Series([100.0] * len(fechas), index=fechas)

    with pytest.warns(UserWarning, match="solo tiene datos hasta 2024-03-01"):
        market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-12-31",
                               cache_dir=tmp_path, downloader=datos_viejos)


def test_red_caida_sirve_cache_con_aviso(tmp_path):
    """Si la descarga falla pero hay caché, se sirve la caché avisando."""
    contador = {}
    market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-03-01",
                           cache_dir=tmp_path, downloader=downloader_contado(contador))

    def caido(ticker, start, end):
        raise RuntimeError("red caída")

    with pytest.warns(UserWarning, match="usando la caché local"):
        px = market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-06-01",
                                    cache_dir=tmp_path, downloader=caido)
    assert not px["AAA.DE"].dropna().empty


def test_red_caida_sin_cache_error_legible(tmp_path):
    def caido(ticker, start, end):
        raise RuntimeError("red caída")

    with pytest.raises(ValueError, match="no hay caché local"):
        market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-06-01",
                               cache_dir=tmp_path, downloader=caido)
