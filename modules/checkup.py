"""Chequeo de cartera: reglas estadísticas sobre la cartera real.

Cada regla es mecánica y explicable; el resultado son hallazgos con severidad
("atencion" > "aviso" > "info") o confirmaciones ("ok"). No es asesoramiento
profesional: son comprobaciones estadísticas sobre datos históricos.
"""

from __future__ import annotations

import pandas as pd

from core import market_data, portfolio
from modules import anomalies, holdings, optimizer, risk

UMBRAL_DRIFT = 0.05          # 5 puntos de desviación sobre el peso objetivo
UMBRAL_CONCENTRACION = 0.60  # un activo no debería superar el 60 %
UMBRAL_CORRELACION = 0.85
UMBRAL_EFICIENCIA = 0.01     # 1 pp de retorno dejado sobre la frontera
UMBRAL_FEE = 0.01            # comisión > 1 % del importe
DIAS_ANOMALIA = 14


def run(csv_path, *, objetivos: dict | None = None, cache_dir=None, downloader=None) -> dict:
    """Reúne los datos de la cartera real y aplica las reglas."""
    cartera = holdings.run(csv_path, cache_dir=cache_dir, downloader=downloader)
    txs = portfolio.load_transactions(csv_path)

    tickers = [p["ticker"] for p in cartera["posiciones"]]
    pesos = {p["ticker"]: p["peso"] for p in cartera["posiciones"]}
    hoy = pd.Timestamp.today().normalize()
    inicio = min(cartera["desde"], hoy - pd.Timedelta(days=365 * 3))
    prices = market_data.get_prices(tickers, inicio, hoy,
                                    cache_dir=cache_dir, downloader=downloader)

    analisis = risk.analyze(prices, pesos, benchmark=None)
    frontera_objetivo = None
    if len(tickers) >= 2:
        res_front = optimizer.efficient_frontier(
            prices, n_points=5, target_vol=analisis["cartera"]["volatilidad"]
        )
        frontera_objetivo = res_front["objetivo_riesgo"]

    eventos_recientes = {}
    for t in tickers:
        try:
            det = anomalies.detect(prices[t].dropna(), window=60, threshold=3.0)
            recientes = [e for e in det["eventos"]
                         if e["fecha"] >= hoy - pd.Timedelta(days=DIAS_ANOMALIA)]
            if recientes:
                eventos_recientes[t] = recientes
        except ValueError:
            pass  # histórico corto: sin señal

    datos = {
        "posiciones": cartera["posiciones"],
        "valor_total": cartera["valor_total"],
        "objetivos": objetivos or {},
        "correlaciones": analisis["correlaciones"],
        "cartera_ret": analisis["cartera"]["ret_anual"],
        "cartera_vol": analisis["cartera"]["volatilidad"],
        "frontera_objetivo": frontera_objetivo,
        "transacciones": txs,
        "eventos_recientes": eventos_recientes,
    }
    hallazgos, correctos = evaluar(datos)
    return {"hallazgos": hallazgos, "correctos": correctos,
            "posiciones": cartera["posiciones"], "valor_total": cartera["valor_total"]}


def evaluar(datos: dict) -> tuple[list[dict], list[str]]:
    """Aplica las reglas sobre datos ya preparados (función pura, testeable)."""
    hallazgos: list[dict] = []
    correctos: list[str] = []

    _regla_objetivos(datos, hallazgos, correctos)
    _regla_concentracion(datos, hallazgos, correctos)
    _regla_correlacion(datos, hallazgos, correctos)
    _regla_eficiencia(datos, hallazgos, correctos)
    _regla_comisiones(datos, hallazgos, correctos)
    _regla_ritmo(datos, hallazgos, correctos)
    _regla_anomalias(datos, hallazgos, correctos)

    orden = {"atencion": 0, "aviso": 1, "info": 2}
    hallazgos.sort(key=lambda h: orden[h["severidad"]])
    return hallazgos, correctos


def _regla_objetivos(d, hallazgos, correctos):
    objetivos = d["objetivos"]
    if not objetivos:
        hallazgos.append({
            "severidad": "info", "regla": "Pesos objetivo",
            "titulo": "Sin pesos objetivo definidos",
            "detalle": "Define tu asignación deseada para que el chequeo pueda "
                       "medir la desviación y sugerir el rebalanceo.",
        })
        return
    desviadas = []
    for p in d["posiciones"]:
        obj = objetivos.get(p["symbol"])
        if obj is None:
            continue
        drift = p["peso"] - obj
        if abs(drift) > UMBRAL_DRIFT:
            importe = drift * d["valor_total"]
            accion = "reducir" if drift > 0 else "aumentar"
            desviadas.append(
                f"{p['ticker']}: {p['peso'] * 100:.1f} % frente al objetivo "
                f"{obj * 100:.0f} % → {accion} ~{abs(importe):.0f} €"
            )
    if desviadas:
        hallazgos.append({
            "severidad": "aviso", "regla": "Pesos objetivo",
            "titulo": f"{len(desviadas)} posición(es) desviadas más de {UMBRAL_DRIFT * 100:.0f} pp",
            "detalle": " · ".join(desviadas),
        })
    else:
        correctos.append("Los pesos actuales están dentro del margen de tus objetivos.")


def _regla_concentracion(d, hallazgos, correctos):
    if len(d["posiciones"]) == 1:
        hallazgos.append({
            "severidad": "aviso", "regla": "Concentración",
            "titulo": "Toda la cartera en un único activo",
            "detalle": "Sin diversificación, el riesgo específico de ese activo es el de toda la cartera.",
        })
        return
    mayor = max(d["posiciones"], key=lambda p: p["peso"])
    if mayor["peso"] > UMBRAL_CONCENTRACION:
        hallazgos.append({
            "severidad": "aviso", "regla": "Concentración",
            "titulo": f"{mayor['ticker']} concentra el {mayor['peso'] * 100:.1f} % de la cartera",
            "detalle": f"Por encima del umbral del {UMBRAL_CONCENTRACION * 100:.0f} %: su riesgo específico domina el conjunto.",
        })
    else:
        correctos.append(f"Ninguna posición supera el {UMBRAL_CONCENTRACION * 100:.0f} % de la cartera.")


def _regla_correlacion(d, hallazgos, correctos):
    corr = d["correlaciones"]
    tickers = corr["tickers"]
    pares = [
        (tickers[i], tickers[j], corr["valores"][i][j])
        for i in range(len(tickers)) for j in range(i + 1, len(tickers))
        if corr["valores"][i][j] > UMBRAL_CORRELACION
    ]
    if pares:
        detalle = " · ".join(f"{a} y {b} correlan {c:.2f}" for a, b, c in pares)
        hallazgos.append({
            "severidad": "aviso", "regla": "Correlación",
            "titulo": "Diversificación ilusoria entre activos",
            "detalle": detalle + ". Se mueven casi a la vez: diversifican menos de lo que parece.",
        })
    elif len(tickers) > 1:
        correctos.append(f"Ningún par de activos correla por encima de {UMBRAL_CORRELACION:.2f}.")


def _regla_eficiencia(d, hallazgos, correctos):
    obj = d["frontera_objetivo"]
    if not obj or not obj.get("alcanzable"):
        return
    gap = obj["ret"] - d["cartera_ret"]
    if gap > UMBRAL_EFICIENCIA:
        pesos = " · ".join(f"{t} {w * 100:.0f} %" for t, w in
                           sorted(obj["weights"].items(), key=lambda kv: -kv[1]))
        hallazgos.append({
            "severidad": "info", "regla": "Eficiencia (frontera)",
            "titulo": f"Con tu mismo riesgo, la frontera histórica daba +{gap * 100:.1f} pp anuales",
            "detalle": f"La combinación de tus propios activos con volatilidad ≤ "
                       f"{d['cartera_vol'] * 100:.1f} % que más rindió: {pesos}. Retorno pasado, no promesa.",
        })
    else:
        correctos.append("Tu cartera está pegada a la frontera eficiente de sus propios activos.")


def _regla_comisiones(d, hallazgos, correctos):
    txs = d["transacciones"]
    compras = txs[txs["type"] == "BUY"]
    caras = []
    for _, t in compras.iterrows():
        importe = -t["amount"]
        fee = -t["fee"]
        if importe > 0 and fee / importe > UMBRAL_FEE:
            caras.append((t["symbol"], fee / importe))
    if caras:
        peor = max(caras, key=lambda x: x[1])
        hallazgos.append({
            "severidad": "aviso", "regla": "Comisiones",
            "titulo": f"{len(caras)} compra(s) pagaron más del {UMBRAL_FEE * 100:.0f} % en comisiones",
            "detalle": f"La peor: {peor[0]} con un {peor[1] * 100:.1f} % del importe. "
                       "En compras pequeñas la comisión fija pesa mucho; los planes de "
                       "inversión periódicos suelen no tenerla.",
        })
    else:
        correctos.append("Ninguna compra pagó más del 1 % en comisiones.")


def _regla_ritmo(d, hallazgos, correctos):
    txs = d["transacciones"]
    compras = txs[txs["type"] == "BUY"]
    if compras.empty:
        return
    fechas = compras["datetime"].dt.tz_convert(None)
    hoy = pd.Timestamp.today()
    ultimos_6 = pd.period_range(end=hoy.to_period("M"), periods=6, freq="M")
    primera = fechas.min().to_period("M")
    evaluables = [m for m in ultimos_6 if m >= primera and m < hoy.to_period("M")]
    con_compra = set(fechas.dt.to_period("M"))
    huecos = [str(m) for m in evaluables if m not in con_compra]
    if huecos:
        hallazgos.append({
            "severidad": "info", "regla": "Ritmo de aportación",
            "titulo": f"{len(huecos)} mes(es) sin aportar en el último medio año",
            "detalle": "Sin compras en: " + ", ".join(huecos) +
                       ". La regularidad del DCA es el factor que más controla tu resultado a largo plazo.",
        })
    elif evaluables:
        correctos.append("Has aportado todos los meses del último medio año.")


def _regla_anomalias(d, hallazgos, correctos):
    eventos = d["eventos_recientes"]
    if eventos:
        partes = [f"{t}: {len(evs)} día(s), último {max(e['fecha'] for e in evs).date()}"
                  for t, evs in eventos.items()]
        hallazgos.append({
            "severidad": "atencion", "regla": "Anomalías",
            "titulo": "Movimientos estadísticamente inusuales en los últimos 14 días",
            "detalle": " · ".join(partes) + ". Revisa el detector de anomalías para el detalle.",
        })
    else:
        correctos.append("Ningún activo tuyo en régimen anómalo en los últimos 14 días.")
