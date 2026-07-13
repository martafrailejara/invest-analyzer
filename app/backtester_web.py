"""Página del backtester: formulario de estrategia → motor → gráfico y métricas."""

from __future__ import annotations

import math
import warnings
from datetime import date

from flask import Blueprint, render_template, request

from app.form_utils import eur, parsea_activos, parsea_fechas, parsea_importe, parsea_rebalanceo, pct
from modules import backtester as motor

backtester = Blueprint("backtester", __name__)

FORM_POR_DEFECTO = {
    "ticker_0": "SXR8.DE", "peso_0": "80",
    "ticker_1": "LYXIB.MC", "peso_1": "20",
    "ticker_2": "", "peso_2": "",
    "ticker_3": "", "peso_3": "",
    "inicial": "0",
    "mensual": "200",
    "start": "2015-01-01",
    "end": date.today().isoformat(),
    "rebalance": "Y",
    "benchmark": "",
}


def _parsea(form) -> tuple[dict, list[str], list[str]]:
    """Valida el formulario; devuelve (parámetros, errores, avisos)."""
    errores: list[str] = []
    avisos: list[str] = []
    weights = parsea_activos(
        [(form.get(f"ticker_{i}", ""), form.get(f"peso_{i}", "")) for i in range(4)],
        errores,
    )
    inicial = parsea_importe(form.get("inicial", ""), "aportación inicial", errores)
    mensual = parsea_importe(form.get("mensual", ""), "aportación mensual", errores)
    if not errores and inicial == 0 and mensual == 0:
        errores.append("Alguna aportación (inicial o mensual) debe ser mayor que 0.")
    end = parsea_fechas(form.get("start", ""), form.get("end", ""), errores, avisos)
    rebalance = parsea_rebalanceo(form.get("rebalance", ""), errores)
    benchmark = (form.get("benchmark", "") or "").strip().upper() or None

    params = {
        "weights": weights,
        "start": form.get("start", ""),
        "end": end,
        "initial_investment": inicial,
        "monthly_contribution": mensual,
        "rebalance_freq": rebalance,
    }
    return params, benchmark, errores, avisos


def _prepara_resultado(res) -> dict:
    m = res.metrics()
    cierre_anual = res.value.groupby(res.value.index.year).last()
    aportado_anual = res.invested.groupby(res.invested.index.year).last()
    return {
        "final": eur(m["final_value"]),
        "final_raw": round(m["final_value"], 2),
        "fecha_final": res.value.index[-1].strftime("%d-%m-%Y"),
        "aportado": eur(m["total_invested"]),
        "ganancia": eur(m["profit"]),
        "profit_raw": m["profit"],
        "cagr": pct(m["cagr"]),
        "cagr_raw": m["cagr"],
        "volatilidad": pct(m["volatility"]),
        "sharpe": "—" if math.isnan(m["sharpe"]) else f"{m['sharpe']:.2f}".replace(".", ","),
        "drawdown": pct(m["max_drawdown"]),
        "chart": {
            "labels": [d.strftime("%Y-%m-%d") for d in res.value.index],
            "value": [round(v, 2) for v in res.value.tolist()],
            "invested": [round(v, 2) for v in res.invested.tolist()],
        },
        "tabla_anual": [
            {"anio": int(anio), "valor": eur(cierre_anual[anio]), "aportado": eur(aportado_anual[anio])}
            for anio in cierre_anual.index
        ],
    }


@backtester.route("/backtester", methods=["GET", "POST"])
def page():
    if request.method == "GET":
        return render_template("backtester.html", form=FORM_POR_DEFECTO, resultado=None, errores=[], avisos=[])

    form = {campo: request.form.get(campo, "") for campo in FORM_POR_DEFECTO}
    params, benchmark, errores, avisos = _parsea(request.form)
    resultado = None
    if not errores:
        try:
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                res = motor.run(**params)
                res_bench = None
                if benchmark:
                    res_bench = motor.run(**{**params, "weights": {benchmark: 1.0}})
            avisos = avisos + sorted({str(w.message) for w in capturados})
            resultado = _prepara_resultado(res)
            if res_bench is not None:
                m_bench = res_bench.metrics()
                valores = res_bench.value.reindex(res.value.index).ffill()
                resultado["benchmark"] = {
                    "nombre": benchmark,
                    "final": eur(m_bench["final_value"]),
                    "cagr": pct(m_bench["cagr"]),
                }
                resultado["chart"]["benchmark"] = {
                    "nombre": benchmark,
                    "values": [None if math.isnan(v) else round(v, 2) for v in valores.tolist()],
                }
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append(
                "No se pudieron obtener los datos de mercado. Comprueba los tickers y tu conexión."
            )

    return render_template(
        "backtester.html", form=form, resultado=resultado, errores=errores, avisos=avisos
    )
