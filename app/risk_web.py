"""Página de riesgo: métricas avanzadas y matriz de correlación."""

from __future__ import annotations

import math
import warnings
from datetime import date

from flask import Blueprint, render_template, request

from app.form_utils import parsea_activos, pct
from modules import risk as motor

risk = Blueprint("risk", __name__)

FORM_POR_DEFECTO = {
    "ticker_0": "SXR8.DE", "peso_0": "50",
    "ticker_1": "LYXIB.MC", "peso_1": "30",
    "ticker_2": "BTC-EUR", "peso_2": "20",
    "ticker_3": "", "peso_3": "",
    "benchmark": "EUNL.DE",
    "start": "2020-01-01",
    "end": date.today().isoformat(),
}


def _parsea(form):
    errores: list[str] = []
    weights = parsea_activos(
        [(form.get(f"ticker_{i}", ""), form.get(f"peso_{i}", "")) for i in range(4)], errores
    )
    benchmark = (form.get("benchmark", "") or "").strip().upper() or None
    return weights, benchmark, form.get("start", ""), form.get("end", ""), errores


def _num(v, dec=2):
    return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:.{dec}f}".replace(".", ",")


def _fila(nombre, b):
    return {
        "nombre": nombre,
        "ret_anual": pct(b["ret_anual"]),
        "volatilidad": pct(b["volatilidad"]),
        "sharpe": _num(b["sharpe"]),
        "sortino": _num(b["sortino"]),
        "var_95": pct(b["var_95"]),
        "cvar_95": pct(b["cvar_95"]),
        "max_drawdown": pct(b["max_drawdown"]),
        "beta": _num(b["beta"]) if b["beta"] is not None else "—",
    }


def _bucket(c: float) -> int:
    """Correlación -> bucket -3..+3 para colorear el heatmap."""
    umbrales = [0.66, 0.33, 0.05, -0.05, -0.33, -0.66]
    for i, u in enumerate(umbrales):
        if c >= u:
            return 3 - i
    return -3


def _prepara(res: dict) -> dict:
    corr = res["correlaciones"]
    heatmap = [
        [{"v": _num(corr["valores"][i][j], 2), "bucket": _bucket(corr["valores"][i][j])}
         for j in range(len(corr["tickers"]))]
        for i in range(len(corr["tickers"]))
    ]
    filas = [_fila("Cartera", res["cartera"])]
    if res["benchmark"]:
        filas.append(_fila(res["benchmark"]["nombre"], res["benchmark"]))
    return {
        "filas": filas,
        "metricas": [
            ("ret_anual", "Retorno anual"), ("volatilidad", "Volatilidad"),
            ("sharpe", "Sharpe"), ("sortino", "Sortino"),
            ("var_95", "VaR 95% (diario)"), ("cvar_95", "CVaR 95% (diario)"),
            ("max_drawdown", "Máx. drawdown"), ("beta", "Beta vs índice"),
        ],
        "tickers": corr["tickers"],
        "heatmap": heatmap,
        "sesiones": res["sesiones"],
    }


@risk.route("/riesgo", methods=["GET", "POST"])
def page():
    if request.method == "GET":
        return render_template("riesgo.html", form=FORM_POR_DEFECTO, resultado=None, errores=[], avisos=[])

    form = {campo: request.form.get(campo, "") for campo in FORM_POR_DEFECTO}
    weights, benchmark, start, end, errores = _parsea(request.form)
    resultado, avisos = None, []
    if not errores:
        try:
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                res = motor.run(weights, benchmark, start, end)
            avisos = sorted({str(w.message) for w in capturados})
            resultado = _prepara(res)
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append("No se pudieron obtener los datos de mercado. Comprueba los tickers y tu conexión.")

    return render_template("riesgo.html", form=form, resultado=resultado, errores=errores, avisos=avisos)
