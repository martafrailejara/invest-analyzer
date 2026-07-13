"""Reglas del chequeo verificadas una a una con datos preparados a mano."""

import pandas as pd
import pytest

from modules import checkup


def txs(filas):
    """DataFrame mínimo de transacciones: (type, symbol, amount, fee, fecha)."""
    return pd.DataFrame({
        "type": [f[0] for f in filas],
        "symbol": [f[1] for f in filas],
        "amount": [f[2] for f in filas],
        "fee": [f[3] for f in filas],
        "datetime": pd.to_datetime([f[4] for f in filas], utc=True),
    })


def datos_base(**cambios):
    base = {
        "posiciones": [
            {"symbol": "ISIN1", "ticker": "AAA.DE", "peso": 0.5, "valor": 500.0},
            {"symbol": "ISIN2", "ticker": "BBB.DE", "peso": 0.5, "valor": 500.0},
        ],
        "valor_total": 1000.0,
        "objetivos": {"ISIN1": 0.5, "ISIN2": 0.5},
        "correlaciones": {"tickers": ["AAA.DE", "BBB.DE"],
                          "valores": [[1.0, 0.3], [0.3, 1.0]]},
        "cartera_ret": 0.08,
        "cartera_vol": 0.12,
        "frontera_objetivo": {"alcanzable": True, "ret": 0.085, "vol": 0.12,
                              "weights": {"AAA.DE": 0.6, "BBB.DE": 0.4}},
        "transacciones": txs([("BUY", "ISIN1", -100.0, -0.5,
                               pd.Timestamp.today() - pd.Timedelta(days=10))]),
        "eventos_recientes": {},
    }
    base.update(cambios)
    return base


def reglas_disparadas(hallazgos):
    return {h["regla"] for h in hallazgos}


def test_cartera_sana_no_dispara_avisos():
    hallazgos, correctos = checkup.evaluar(datos_base())
    assert not [h for h in hallazgos if h["severidad"] != "info"]
    assert len(correctos) >= 4


def test_drift_de_pesos_objetivo():
    d = datos_base(objetivos={"ISIN1": 0.8, "ISIN2": 0.2})  # actual 50/50
    hallazgos, _ = checkup.evaluar(d)
    drift = next(h for h in hallazgos if h["regla"] == "Pesos objetivo")
    assert drift["severidad"] == "aviso"
    assert "AAA.DE" in drift["detalle"] and "aumentar" in drift["detalle"]
    # desviación del 30% sobre 1000 € -> mover ~300 €
    assert "300 €" in drift["detalle"]


def test_sin_objetivos_es_info():
    hallazgos, _ = checkup.evaluar(datos_base(objetivos={}))
    h = next(h for h in hallazgos if h["regla"] == "Pesos objetivo")
    assert h["severidad"] == "info"


def test_concentracion():
    d = datos_base(posiciones=[
        {"symbol": "ISIN1", "ticker": "AAA.DE", "peso": 0.75, "valor": 750.0},
        {"symbol": "ISIN2", "ticker": "BBB.DE", "peso": 0.25, "valor": 250.0},
    ], objetivos={})
    hallazgos, _ = checkup.evaluar(d)
    assert "Concentración" in reglas_disparadas(hallazgos)


def test_correlacion_alta():
    d = datos_base(correlaciones={"tickers": ["AAA.DE", "BBB.DE"],
                                  "valores": [[1.0, 0.92], [0.92, 1.0]]})
    hallazgos, _ = checkup.evaluar(d)
    corr = next(h for h in hallazgos if h["regla"] == "Correlación")
    assert "0.92" in corr["detalle"] or "0,92" in corr["detalle"]


def test_eficiencia_frente_a_frontera():
    d = datos_base(frontera_objetivo={"alcanzable": True, "ret": 0.11, "vol": 0.12,
                                      "weights": {"AAA.DE": 0.9, "BBB.DE": 0.1}})
    hallazgos, _ = checkup.evaluar(d)
    ef = next(h for h in hallazgos if h["regla"] == "Eficiencia (frontera)")
    assert "+3.0 pp" in ef["titulo"] or "+3,0 pp" in ef["titulo"]


def test_comisiones_caras():
    d = datos_base(transacciones=txs([
        ("BUY", "BTC", -50.0, -1.0, "2026-03-04"),   # 2 %
        ("BUY", "ISIN1", -100.0, 0.0, "2026-07-02"),
    ]))
    hallazgos, _ = checkup.evaluar(d)
    com = next(h for h in hallazgos if h["regla"] == "Comisiones")
    assert "2.0 %" in com["detalle"] or "2,0 %" in com["detalle"]


def test_meses_sin_aportar():
    hace_5m = pd.Timestamp.today() - pd.DateOffset(months=5)
    d = datos_base(transacciones=txs([("BUY", "ISIN1", -100.0, 0.0, hace_5m)]))
    hallazgos, _ = checkup.evaluar(d)
    ritmo = next(h for h in hallazgos if h["regla"] == "Ritmo de aportación")
    assert "sin aportar" in ritmo["titulo"]


def test_anomalias_recientes_son_atencion():
    d = datos_base(eventos_recientes={
        "AAA.DE": [{"fecha": pd.Timestamp.today() - pd.Timedelta(days=2),
                    "retorno": -0.06, "score": -4.2, "precio": 90.0}],
    })
    hallazgos, _ = checkup.evaluar(d)
    assert hallazgos[0]["severidad"] == "atencion"  # ordenado primero
    assert hallazgos[0]["regla"] == "Anomalías"
