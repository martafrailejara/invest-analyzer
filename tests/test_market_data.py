import pandas as pd
import pytest

from core import market_data


def downloader_contado(contador):
    """Downloader falso y determinista que cuenta las descargas por ticker."""

    def descargar(ticker, start, end):
        contador[ticker] = contador.get(ticker, 0) + 1
        fechas = pd.bdate_range(start, end)
        return pd.Series([100.0 + i for i in range(len(fechas))], index=fechas)

    return descargar


def dividendos_contados(contador, serie):
    def descargar(ticker):
        contador[ticker] = contador.get(ticker, 0) + 1
        return serie

    return descargar


def test_get_prices_estructura(tmp_path):
    df = market_data.get_prices(
        ["AAA.DE", "BBB.DE"], "2024-01-01", "2024-02-01",
        cache_dir=tmp_path, downloader=downloader_contado({}),
    )
    assert list(df.columns) == ["AAA.DE", "BBB.DE"]
    assert isinstance(df.index, pd.DatetimeIndex)
    assert df.index.min() >= pd.Timestamp("2024-01-01")
    assert df.index.max() <= pd.Timestamp("2024-02-01")
    assert not df.isna().any().any()


def test_get_prices_segunda_llamada_sale_de_cache(tmp_path):
    contador = {}
    args = dict(cache_dir=tmp_path, downloader=downloader_contado(contador))

    df1 = market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-02-01", **args)
    assert contador == {"AAA.DE": 1}

    df2 = market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-02-01", **args)
    assert contador == {"AAA.DE": 1}  # sin descargas nuevas
    pd.testing.assert_frame_equal(df1, df2, check_freq=False)

    # un subrango tambien se sirve de cache
    market_data.get_prices(["AAA.DE"], "2024-01-10", "2024-01-20", **args)
    assert contador == {"AAA.DE": 1}


def test_get_prices_amplia_cache_si_desborda_rango(tmp_path):
    contador = {}
    args = dict(cache_dir=tmp_path, downloader=downloader_contado(contador))

    market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-02-01", **args)
    df = market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-06-01", **args)
    assert contador == {"AAA.DE": 2}
    assert df.index.max() > pd.Timestamp("2024-05-01")

    # tras ampliar, el rango grande ya esta cubierto
    market_data.get_prices(["AAA.DE"], "2024-01-01", "2024-06-01", **args)
    assert contador == {"AAA.DE": 2}


def test_get_prices_ticker_sin_datos(tmp_path):
    def vacio(ticker, start, end):
        return pd.Series(dtype="float64")

    with pytest.raises(ValueError, match="no devolvió datos"):
        market_data.get_prices(["MALO.DE"], "2024-01-01", "2024-02-01",
                               cache_dir=tmp_path, downloader=vacio)


def test_get_prices_rango_invalido(tmp_path):
    with pytest.raises(ValueError, match="Rango de fechas inválido"):
        market_data.get_prices(["AAA.DE"], "2024-02-01", "2024-01-01",
                               cache_dir=tmp_path, downloader=downloader_contado({}))


def test_get_dividends_cachea_y_refresca(tmp_path):
    contador = {}
    serie = pd.Series(
        [0.5, 0.6],
        index=pd.DatetimeIndex(["2024-03-15", "2024-09-15"]),
    )
    descargar = dividendos_contados(contador, serie)

    div1 = market_data.get_dividends("DIST", cache_dir=tmp_path, downloader=descargar)
    assert contador == {"DIST": 1}
    assert div1.tolist() == [0.5, 0.6]

    market_data.get_dividends("DIST", cache_dir=tmp_path, downloader=descargar)
    assert contador == {"DIST": 1}  # servido de cache

    market_data.get_dividends("DIST", cache_dir=tmp_path, downloader=descargar, refresh=True)
    assert contador == {"DIST": 2}


def test_get_dividends_serie_vacia_es_valida(tmp_path):
    """Un ETF de acumulacion no paga dividendos: serie vacia, sin error."""
    contador = {}
    vacia = pd.Series(dtype="float64")
    div = market_data.get_dividends("ACC", cache_dir=tmp_path,
                                    downloader=dividendos_contados(contador, vacia))
    assert div.empty
    # y la serie vacia tambien queda cacheada
    market_data.get_dividends("ACC", cache_dir=tmp_path,
                              downloader=dividendos_contados(contador, vacia))
    assert contador == {"ACC": 1}
