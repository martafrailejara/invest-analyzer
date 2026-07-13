"""Metas financieras: probabilidad estadística de alcanzar un objetivo.

Parte de la cartera real (valor y pesos actuales) y proyecta con Monte Carlo
(bootstrap de retornos mensuales históricos) hasta el año objetivo. Devuelve
la probabilidad de llegar al importe deseado con la aportación prevista y con
variantes (0.5×, 1.5×, 2×) para ver cuánto mueve la aguja aportar más.

Estadístico y basado en el pasado: no es una predicción ni asesoramiento.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from core import market_data
from modules import holdings, montecarlo

VARIANTES = (0.5, 1.0, 1.5, 2.0)


def run(
    csv_path,
    *,
    importe_objetivo: float,
    anio_objetivo: int,
    aportacion_mensual: float,
    n_sims: int = 1000,
    seed: int | None = 0,
    cache_dir=None,
    downloader=None,
) -> dict:
    if importe_objetivo <= 0:
        raise ValueError("El importe objetivo debe ser mayor que 0")
    anios = anio_objetivo - date.today().year
    if not 1 <= anios <= 60:
        raise ValueError("El año objetivo debe quedar entre 1 y 60 años vista")
    if aportacion_mensual < 0:
        raise ValueError("La aportación mensual no puede ser negativa")

    cartera = holdings.run(csv_path, cache_dir=cache_dir, downloader=downloader)
    valor_actual = cartera["valor_total"]
    pesos = {p["ticker"]: p["peso"] for p in cartera["posiciones"]}

    hoy = pd.Timestamp.today().normalize()
    prices = market_data.get_prices(list(pesos), hoy - pd.Timedelta(days=365 * 10), hoy,
                                    cache_dir=cache_dir, downloader=downloader)

    variantes = []
    proyeccion_base = None
    for factor in VARIANTES:
        aportacion = aportacion_mensual * factor
        if valor_actual == 0 and aportacion == 0:
            continue
        proy = montecarlo.project(
            prices, pesos, years=anios, initial=valor_actual,
            monthly_contribution=aportacion, n_sims=n_sims, seed=seed,
            objetivo=importe_objetivo,
        )
        variantes.append({"factor": factor, "aportacion": aportacion,
                          "prob": proy["prob_objetivo"], "mediana": proy["terminal"][50]})
        if factor == 1.0:
            proyeccion_base = proy

    return {
        "valor_actual": valor_actual,
        "importe_objetivo": importe_objetivo,
        "anio_objetivo": anio_objetivo,
        "anios": anios,
        "aportacion_mensual": aportacion_mensual,
        "progreso": min(valor_actual / importe_objetivo, 1.0),
        "variantes": variantes,
        "proyeccion": proyeccion_base,
        "meses_historico": proyeccion_base["meses_historico"] if proyeccion_base else 0,
    }
