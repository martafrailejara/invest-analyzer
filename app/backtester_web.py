"""Página del backtester: formulario de estrategia → motor → gráfico y métricas."""

from __future__ import annotations

import math
import warnings
from datetime import date

from flask import Blueprint, render_template, request

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
}


def _eur(v: float) -> str:
    entero, decimales = f"{v:,.2f}".split(".")
    return entero.replace(",", ".") + "," + decimales + " €"


def _pct(v: float) -> str:
    if math.isnan(v):
        return "—"
    return f"{v * 100:.2f}".replace(".", ",") + " %"


def _parsea(form) -> tuple[dict, list[str]]:
    """Valida el formulario; devuelve (parámetros, errores). Sin excepciones a medias."""
    errores: list[str] = []
    pesos: dict[str, float] = {}
    for i in range(4):
        ticker = form.get(f"ticker_{i}", "").strip().upper()
        peso_txt = form.get(f"peso_{i}", "").strip()
        if not ticker and not peso_txt:
            continue
        if not ticker or not peso_txt:
            errores.append(f"La fila {i + 1} de activos necesita ticker y peso.")
            continue
        try:
            peso = float(peso_txt.replace(",", "."))
        except ValueError:
            errores.append(f"El peso de {ticker} no es un número.")
            continue
        if peso <= 0:
            errores.append(f"El peso de {ticker} debe ser mayor que 0.")
            continue
        pesos[ticker] = pesos.get(ticker, 0) + peso

    if not pesos:
        errores.append("Indica al menos un activo con su peso.")
    elif abs(sum(pesos.values()) - 100) > 0.01:
        errores.append(f"Los pesos deben sumar 100 (suman {sum(pesos.values()):g}).")

    def _importe(campo: str, nombre: str) -> float:
        txt = form.get(campo, "").strip() or "0"
        try:
            v = float(txt.replace(",", "."))
        except ValueError:
            errores.append(f"La {nombre} no es un número.")
            return 0.0
        if v < 0:
            errores.append(f"La {nombre} no puede ser negativa.")
        return v

    inicial = _importe("inicial", "aportación inicial")
    mensual = _importe("mensual", "aportación mensual")
    if not errores and inicial == 0 and mensual == 0:
        errores.append("Alguna aportación (inicial o mensual) debe ser mayor que 0.")

    start, end = form.get("start", ""), form.get("end", "")
    try:
        if date.fromisoformat(start) >= date.fromisoformat(end):
            errores.append("La fecha inicial debe ser anterior a la final.")
    except ValueError:
        errores.append("Fechas incompletas o con formato incorrecto.")

    rebalance = form.get("rebalance", "") or None
    if rebalance not in (None, "M", "Q", "Y"):
        errores.append("Frecuencia de rebalanceo no reconocida.")

    params = {
        "weights": {t: p / 100 for t, p in pesos.items()},
        "start": start,
        "end": end,
        "initial_investment": inicial,
        "monthly_contribution": mensual,
        "rebalance_freq": rebalance,
    }
    return params, errores


def _prepara_resultado(res) -> dict:
    m = res.metrics()
    cierre_anual = res.value.groupby(res.value.index.year).last()
    aportado_anual = res.invested.groupby(res.invested.index.year).last()
    return {
        "final": _eur(m["final_value"]),
        "final_raw": round(m["final_value"], 2),
        "fecha_final": res.value.index[-1].strftime("%d-%m-%Y"),
        "aportado": _eur(m["total_invested"]),
        "ganancia": _eur(m["profit"]),
        "profit_raw": m["profit"],
        "cagr": _pct(m["cagr"]),
        "cagr_raw": m["cagr"],
        "volatilidad": _pct(m["volatility"]),
        "sharpe": "—" if math.isnan(m["sharpe"]) else f"{m['sharpe']:.2f}".replace(".", ","),
        "drawdown": _pct(m["max_drawdown"]),
        "chart": {
            "labels": [d.strftime("%Y-%m-%d") for d in res.value.index],
            "value": [round(v, 2) for v in res.value.tolist()],
            "invested": [round(v, 2) for v in res.invested.tolist()],
        },
        "tabla_anual": [
            {"anio": int(anio), "valor": _eur(cierre_anual[anio]), "aportado": _eur(aportado_anual[anio])}
            for anio in cierre_anual.index
        ],
    }


@backtester.route("/backtester", methods=["GET", "POST"])
def page():
    if request.method == "GET":
        return render_template("backtester.html", form=FORM_POR_DEFECTO, resultado=None, errores=[], avisos=[])

    form = {campo: request.form.get(campo, "") for campo in FORM_POR_DEFECTO}
    params, errores = _parsea(request.form)
    resultado, avisos = None, []
    if not errores:
        try:
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                res = motor.run(**params)
            avisos = [str(w.message) for w in capturados]
            resultado = _prepara_resultado(res)
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append(
                "No se pudieron obtener los datos de mercado. Comprueba los tickers y tu conexión."
            )

    return render_template(
        "backtester.html", form=form, resultado=resultado, errores=errores, avisos=avisos
    )
