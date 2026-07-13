"""Página Monte Carlo: proyección probabilística de la cartera a futuro."""

from __future__ import annotations

import warnings
from datetime import date

from flask import Blueprint, render_template, request

from app.form_utils import eur, parsea_activos, parsea_importe, pct
from modules import montecarlo as motor

montecarlo = Blueprint("montecarlo", __name__)

FORM_POR_DEFECTO = {
    "ticker_0": "SXR8.DE", "peso_0": "80",
    "ticker_1": "LYXIB.MC", "peso_1": "20",
    "ticker_2": "", "peso_2": "",
    "ticker_3": "", "peso_3": "",
    "inicial": "5000",
    "mensual": "200",
    "years": "20",
    "start": "2010-01-01",
    "end": date.today().isoformat(),
}


def _parsea(form) -> tuple[dict, list[str]]:
    errores: list[str] = []
    weights = parsea_activos(
        [(form.get(f"ticker_{i}", ""), form.get(f"peso_{i}", "")) for i in range(4)], errores
    )
    inicial = parsea_importe(form.get("inicial", ""), "aportación inicial", errores)
    mensual = parsea_importe(form.get("mensual", ""), "aportación mensual", errores)
    if not errores and inicial == 0 and mensual == 0:
        errores.append("Alguna aportación (inicial o mensual) debe ser mayor que 0.")
    try:
        years = int(form.get("years", ""))
        if not 1 <= years <= 50:
            errores.append("El horizonte debe estar entre 1 y 50 años.")
    except ValueError:
        errores.append("El horizonte no es un número entero.")
        years = 20
    params = {
        "weights": weights,
        "start": form.get("start", ""),
        "end": form.get("end", ""),
        "initial": inicial,
        "monthly_contribution": mensual,
        "years": years,
    }
    return params, errores


def _prepara(res: dict) -> dict:
    # etiquetas: un punto por año para el eje (los meses son demasiados)
    etiquetas = [f"Año {i}" if i else "Hoy" for i in range(res["meses"] // 12 + 1)]
    idx_anual = list(range(0, res["meses"] + 1, 12))
    bandas = {p: [res["bandas"][p][i] for i in idx_anual] for p in motor.PERCENTILES}
    return {
        "aportado": eur(res["aportado"]),
        "prob_ganancia": pct(res["prob_ganancia"]),
        "prob_doblar": pct(res["prob_doblar"]),
        "n_sims": res["n_sims"],
        "meses_historico": res["meses_historico"],
        "terminal": {
            "p10": eur(res["terminal"][10]),
            "p50": eur(res["terminal"][50]),
            "p50_raw": round(res["terminal"][50], 2),
            "p90": eur(res["terminal"][90]),
        },
        "chart": {
            "labels": etiquetas,
            "p10": bandas[10], "p25": bandas[25], "p50": bandas[50],
            "p75": bandas[75], "p90": bandas[90],
        },
    }


@montecarlo.route("/montecarlo", methods=["GET", "POST"])
def page():
    if request.method == "GET":
        return render_template("montecarlo.html", form=FORM_POR_DEFECTO, resultado=None, errores=[], avisos=[])

    form = {campo: request.form.get(campo, "") for campo in FORM_POR_DEFECTO}
    params, errores = _parsea(request.form)
    resultado, avisos = None, []
    if not errores:
        try:
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                res = motor.run(**params)
            avisos = sorted({str(w.message) for w in capturados})
            resultado = _prepara(res)
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append("No se pudieron obtener los datos de mercado. Comprueba los tickers y tu conexión.")

    return render_template("montecarlo.html", form=form, resultado=resultado, errores=errores, avisos=avisos)
