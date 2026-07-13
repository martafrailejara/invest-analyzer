"""Detector de anomalías: anomalía inyectada se detecta, días normales no disparan."""

import pandas as pd
import pytest

from modules import anomalies


def serie_con_ruido(n: int, caida_en: int | None = None) -> pd.Series:
    """Precio con ruido alterno de ±0.5% y, opcionalmente, un desplome del 15%."""
    precios = [100.0]
    for i in range(1, n):
        r = 0.005 if i % 2 else -0.005
        if i == caida_en:
            r = -0.15
        precios.append(precios[-1] * (1 + r))
    return pd.Series(precios, index=pd.bdate_range("2024-01-01", periods=n))


def test_detecta_anomalia_inyectada():
    serie = serie_con_ruido(200, caida_en=150)
    res = anomalies.detect(serie, window=60, threshold=3.0)

    fechas = [e["fecha"] for e in res["eventos"]]
    assert serie.index[150] in fechas
    caida = next(e for e in res["eventos"] if e["fecha"] == serie.index[150])
    assert caida["retorno"] == pytest.approx(-0.15)
    assert abs(caida["score"]) > 3


def test_sin_anomalias_no_hay_falsos_positivos():
    res = anomalies.detect(serie_con_ruido(200), window=60, threshold=3.0)
    assert res["eventos"] == []
    assert res["tasa_anomalias"] == 0.0


def test_el_dia_anomalo_no_contamina_su_propia_referencia():
    """Los estadísticos se calculan sobre la ventana previa (shift): la caída
    del 15% no infla la desviación con la que se evalúa a sí misma."""
    serie = serie_con_ruido(200, caida_en=150)
    res = anomalies.detect(serie, window=60, threshold=3.0)
    caida = next(e for e in res["eventos"] if e["fecha"] == serie.index[150])
    # con σ previa de ~0.5% el z del -15% es enorme; si el día se incluyera
    # a sí mismo en la ventana, el z quedaría muy amortiguado
    assert abs(caida["score"]) > 10


def test_umbral_mas_bajo_detecta_igual_o_mas():
    serie = serie_con_ruido(300, caida_en=200)
    estricto = anomalies.detect(serie, window=60, threshold=4.0)
    laxo = anomalies.detect(serie, window=60, threshold=2.0)
    assert len(laxo["eventos"]) >= len(estricto["eventos"])


def test_bandas_de_bollinger_envuelven_el_precio():
    serie = serie_con_ruido(200)
    res = anomalies.detect(serie, window=60, threshold=3.0)
    banda = res["bollinger"]
    validas = banda["media"].dropna().index
    assert (banda["superior"][validas] >= banda["media"][validas]).all()
    assert (banda["inferior"][validas] <= banda["media"][validas]).all()


def test_validaciones():
    serie = serie_con_ruido(200)
    with pytest.raises(ValueError, match="al menos 10 sesiones"):
        anomalies.detect(serie, window=5)
    with pytest.raises(ValueError, match="mayor que 0"):
        anomalies.detect(serie, threshold=0)
    with pytest.raises(ValueError, match="Histórico insuficiente"):
        anomalies.detect(serie_con_ruido(50), window=60)


def test_run_con_downloader(tmp_path):
    def downloader(ticker, start, end):
        return serie_con_ruido(200, caida_en=150)

    res = anomalies.run("AAA.DE", "2024-01-01", "2024-12-31",
                        cache_dir=tmp_path, downloader=downloader)
    assert len(res["eventos"]) >= 1


def test_iforest_detecta_la_caida():
    """El Isolation Forest también marca el desplome inyectado como anomalía."""
    serie = serie_con_ruido(300, caida_en=200)
    res = anomalies.detect(serie, method="iforest", window=60, contamination=0.03)
    fechas = [e["fecha"] for e in res["eventos"]]
    assert serie.index[200] in fechas
    assert res["method"] == "iforest"
    assert res["score_label"] == "score de aislamiento"


def test_iforest_contaminacion_controla_cuantas_marca():
    serie = serie_con_ruido(400, caida_en=300)
    poco = anomalies.detect(serie, method="iforest", window=60, contamination=0.01)
    mucho = anomalies.detect(serie, method="iforest", window=60, contamination=0.10)
    assert len(mucho["eventos"]) > len(poco["eventos"])


def test_iforest_reproducible():
    serie = serie_con_ruido(300, caida_en=150)
    a = anomalies.detect(serie, method="iforest", window=60, contamination=0.02)
    b = anomalies.detect(serie, method="iforest", window=60, contamination=0.02)
    assert [e["fecha"] for e in a["eventos"]] == [e["fecha"] for e in b["eventos"]]


def test_method_invalido():
    with pytest.raises(ValueError, match="zscore.*iforest|method"):
        anomalies.detect(serie_con_ruido(200), method="otro")


def test_contaminacion_invalida():
    with pytest.raises(ValueError, match="contaminación"):
        anomalies.detect(serie_con_ruido(200), method="iforest", contamination=0.9)
