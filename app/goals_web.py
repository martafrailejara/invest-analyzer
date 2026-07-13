"""Página de metas: probabilidad estadística de alcanzar tu objetivo."""

from __future__ import annotations

import warnings
from datetime import date
from pathlib import Path

from flask import Blueprint, render_template, request

from app.form_utils import eur, parsea_importe, pct
from core import config
from modules import goals as motor

goals = Blueprint("goals", __name__)

RAIZ = Path(__file__).resolve().parents[1]
CSV_REAL = RAIZ / "data" / "transacciones.csv"


def _form_por_defecto() -> dict:
    meta = config.get("meta", {})
    return {
        "importe": str(meta.get("importe", "100000")),
        "anio": str(meta.get("anio", date.today().year + 15)),
        "mensual": str(meta.get("mensual", "200")),
    }


def _parsea(form) -> tuple[dict, list[str]]:
    errores: list[str] = []
    importe = parsea_importe(form.get("importe", ""), "meta de importe", errores)
    mensual = parsea_importe(form.get("mensual", ""), "aportación mensual", errores)
    try:
        anio = int(form.get("anio", ""))
    except ValueError:
        errores.append("El año objetivo no es un número entero.")
        anio = date.today().year + 15
    return {"importe_objetivo": importe, "anio_objetivo": anio, "aportacion_mensual": mensual}, errores


def _prepara(res: dict) -> dict:
    return {
        "valor_actual": eur(res["valor_actual"]),
        "objetivo": eur(res["importe_objetivo"]),
        "anio": res["anio_objetivo"],
        "anios": res["anios"],
        "progreso": pct(res["progreso"]),
        "progreso_raw": round(res["progreso"] * 100, 1),
        "meses_historico": res["meses_historico"],
        "prob_base": next((pct(v["prob"]) for v in res["variantes"] if v["factor"] == 1.0), "—"),
        "variantes": [
            {
                "aportacion": eur(v["aportacion"]) + "/mes",
                "factor": f"{v['factor']:g}×",
                "prob": pct(v["prob"]),
                "mediana": eur(v["mediana"]),
                "base": v["factor"] == 1.0,
            }
            for v in res["variantes"]
        ],
    }


@goals.route("/metas", methods=["GET", "POST"])
def page():
    if not CSV_REAL.exists():
        return render_template("metas.html", form=_form_por_defecto(), resultado=None,
                               errores=[], avisos=[], sin_csv=True)

    if request.method == "GET":
        return render_template("metas.html", form=_form_por_defecto(), resultado=None,
                               errores=[], avisos=[], sin_csv=False)

    form = {campo: request.form.get(campo, "") for campo in ("importe", "anio", "mensual")}
    params, errores = _parsea(request.form)
    resultado, avisos = None, []
    if not errores:
        try:
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                res = motor.run(CSV_REAL, **params)
            avisos = sorted({str(w.message) for w in capturados})
            resultado = _prepara(res)
            config.set("meta", {"importe": params["importe_objetivo"],
                                "anio": params["anio_objetivo"],
                                "mensual": params["aportacion_mensual"]})
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append("No se pudieron obtener los datos de mercado. Comprueba tu conexión.")

    return render_template("metas.html", form=form, resultado=resultado,
                           errores=errores, avisos=avisos, sin_csv=False)
