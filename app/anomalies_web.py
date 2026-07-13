"""Página del detector de anomalías: movimientos inusuales sobre el gráfico."""

from __future__ import annotations

import math
import warnings
from datetime import date

from flask import Blueprint, render_template, request

from app.form_utils import parsea_fechas, pct
from modules import anomalies as motor

anomalies = Blueprint("anomalies", __name__)

FORM_POR_DEFECTO = {
    "ticker": "SXR8.DE",
    "start": "2019-01-01",
    "end": date.today().isoformat(),
    "window": "60",
    "threshold": "3",
}


def _parsea(form) -> tuple[dict, list[str], list[str]]:
    errores: list[str] = []
    avisos: list[str] = []
    ticker = (form.get("ticker", "") or "").strip().upper()
    if not ticker:
        errores.append("Indica un ticker de yfinance.")

    def entero(campo, nombre, minimo):
        try:
            v = int(form.get(campo, ""))
        except ValueError:
            errores.append(f"{nombre} no es un número entero.")
            return minimo
        return v

    window = entero("window", "La ventana", 10)
    try:
        threshold = float((form.get("threshold", "") or "").replace(",", "."))
    except ValueError:
        errores.append("El umbral no es un número.")
        threshold = 3.0

    start = form.get("start", "")
    end = parsea_fechas(start, form.get("end", ""), errores, avisos)
    params = {"ticker": ticker, "start": start, "end": end,
              "window": window, "threshold": threshold}
    return params, errores, avisos


def _prepara(res: dict) -> dict:
    precios = res["precios"]
    banda = res["bollinger"]

    def lista(serie):
        return [None if (isinstance(v, float) and math.isnan(v)) else round(float(v), 4)
                for v in serie.tolist()]

    fechas_evento = {e["fecha"] for e in res["eventos"]}
    puntos_anomalia = [
        round(float(precios[f]), 4) if f in fechas_evento else None for f in precios.index
    ]
    return {
        "n_eventos": len(res["eventos"]),
        "dias_evaluados": res["dias_evaluados"],
        "tasa": pct(res["tasa_anomalias"]),
        "window": res["window"],
        "threshold": f"{res['threshold']:g}".replace(".", ","),
        "chart": {
            "labels": [d.strftime("%Y-%m-%d") for d in precios.index],
            "precio": lista(precios),
            "banda_sup": lista(banda["superior"]),
            "banda_inf": lista(banda["inferior"]),
            "anomalias": puntos_anomalia,
        },
        "eventos": [
            {
                "fecha": e["fecha"].strftime("%d-%m-%Y"),
                "retorno": pct(e["retorno"]),
                "negativo": e["retorno"] < 0,
                "z": f"{e['z']:+.1f}".replace(".", ","),
                "precio": f"{e['precio']:.2f}".replace(".", ",") + " €",
            }
            for e in sorted(res["eventos"], key=lambda e: e["fecha"], reverse=True)
        ],
    }


@anomalies.route("/anomalias", methods=["GET", "POST"])
def page():
    if request.method == "GET":
        return render_template("anomalias.html", form=FORM_POR_DEFECTO, resultado=None, errores=[], avisos=[])

    form = {campo: request.form.get(campo, "") for campo in FORM_POR_DEFECTO}
    params, errores, avisos = _parsea(request.form)
    resultado = None
    if not errores:
        try:
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                res = motor.run(**params)
            avisos = avisos + sorted({str(w.message) for w in capturados})
            resultado = _prepara(res)
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append(
                "No se pudieron obtener los datos de mercado. Comprueba el ticker y tu conexión."
            )

    return render_template(
        "anomalias.html", form=form, resultado=resultado, errores=errores, avisos=avisos
    )
