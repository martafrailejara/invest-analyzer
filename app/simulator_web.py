"""Página del simulador: N escenarios lado a lado sobre el mismo rango de fechas."""

from __future__ import annotations

import math
import warnings
from datetime import date, timedelta

import pandas as pd
from flask import Blueprint, render_template, request

from app.form_utils import eur, parsea_activos, parsea_fechas, parsea_importe, parsea_rebalanceo, pct
from modules import simulator as motor
from modules.simulator import Scenario

simulator = Blueprint("simulator", __name__)

LETRAS = ("a", "b", "c")

FORM_POR_DEFECTO = {
    "start": (date.today() - timedelta(days=365)).isoformat(),
    "end": date.today().isoformat(),
    # Escenario A — el caso del documento: 10.000 € de golpe…
    "nombre_a": "Aportación única", "ticker_a_0": "SXR8.DE", "peso_a_0": "100",
    "ticker_a_1": "", "peso_a_1": "", "inicial_a": "10000", "mensual_a": "0", "meses_a": "", "rebalance_a": "",
    # …frente a repartirlos en DCA durante 12 meses
    "nombre_b": "DCA 12 meses", "ticker_b_0": "SXR8.DE", "peso_b_0": "100",
    "ticker_b_1": "", "peso_b_1": "", "inicial_b": "0", "mensual_b": "833,33", "meses_b": "12", "rebalance_b": "",
    # Escenario C opcional (vacío = no se ejecuta)
    "nombre_c": "", "ticker_c_0": "", "peso_c_0": "",
    "ticker_c_1": "", "peso_c_1": "", "inicial_c": "", "mensual_c": "", "meses_c": "", "rebalance_c": "",
}


def _escenario_vacio(form, letra: str) -> bool:
    campos = (f"nombre_{letra}", f"ticker_{letra}_0", f"peso_{letra}_0",
              f"ticker_{letra}_1", f"peso_{letra}_1", f"inicial_{letra}", f"mensual_{letra}")
    return not any((form.get(c, "") or "").strip() for c in campos)


def _parsea(form) -> tuple[list[Scenario], str, str, list[str], list[str]]:
    errores: list[str] = []
    avisos: list[str] = []
    escenarios: list[Scenario] = []

    for letra in LETRAS:
        if letra == "c" and _escenario_vacio(form, letra):
            continue
        etiqueta = letra.upper()
        contexto = f"Escenario {etiqueta}: "
        nombre = (form.get(f"nombre_{letra}", "") or "").strip() or f"Escenario {etiqueta}"
        weights = parsea_activos(
            [(form.get(f"ticker_{letra}_{i}", ""), form.get(f"peso_{letra}_{i}", "")) for i in range(2)],
            errores, contexto,
        )
        inicial = parsea_importe(form.get(f"inicial_{letra}", ""), f"aportación inicial del escenario {etiqueta}", errores)
        mensual = parsea_importe(form.get(f"mensual_{letra}", ""), f"aportación mensual del escenario {etiqueta}", errores)
        if not errores and inicial == 0 and mensual == 0:
            errores.append(f"{contexto}alguna aportación debe ser mayor que 0.")
        rebalance = parsea_rebalanceo(form.get(f"rebalance_{letra}", ""), errores)
        meses_txt = (form.get(f"meses_{letra}", "") or "").strip()
        meses = None
        if meses_txt:
            try:
                meses = int(meses_txt)
                if meses < 1:
                    errores.append(f"{contexto}los meses de aportación deben ser al menos 1.")
            except ValueError:
                errores.append(f"{contexto}los meses de aportación no son un número entero.")
        escenarios.append(Scenario(
            name=nombre, weights=weights,
            initial_investment=inicial, monthly_contribution=mensual,
            contribution_months=meses, rebalance_freq=rebalance,
        ))

    start = form.get("start", "")
    end = parsea_fechas(start, form.get("end", ""), errores, avisos)
    return escenarios, start, end, errores, avisos


def _prepara(resultados) -> dict:
    """Series alineadas a un índice común y tabla de métricas enfrentadas."""
    indice_comun = None
    for _, res in resultados:
        indice_comun = res.value.index if indice_comun is None else indice_comun.union(res.value.index)

    series = []
    columnas = []
    for i, (sc, res) in enumerate(resultados):
        m = res.metrics()
        alineada = res.value.reindex(indice_comun).ffill()
        series.append({
            "nombre": sc.name,
            "token": f"--chart-esc-{LETRAS[i]}",
            "values": [None if pd.isna(v) else round(v, 2) for v in alineada.tolist()],
        })
        columnas.append({
            "nombre": sc.name,
            "letra": LETRAS[i],
            "final": eur(m["final_value"]),
            "aportado": eur(m["total_invested"]),
            "ganancia": eur(m["profit"]),
            "cagr": pct(m["cagr"]),
            "volatilidad": pct(m["volatility"]),
            "sharpe": "—" if math.isnan(m["sharpe"]) else f"{m['sharpe']:.2f}".replace(".", ","),
            "drawdown": pct(m["max_drawdown"]),
        })

    return {
        "chart": {"labels": [d.strftime("%Y-%m-%d") for d in indice_comun], "series": series},
        "columnas": columnas,
        "metricas": [
            ("final", "Valor final"), ("aportado", "Total aportado"), ("ganancia", "Ganancia"),
            ("cagr", "CAGR"), ("volatilidad", "Volatilidad anual"), ("sharpe", "Sharpe"),
            ("drawdown", "Máx. drawdown"),
        ],
    }


@simulator.route("/simulador", methods=["GET", "POST"])
def page():
    if request.method == "GET":
        return render_template("simulador.html", form=FORM_POR_DEFECTO, resultado=None, errores=[], avisos=[])

    form = {campo: request.form.get(campo, "") for campo in FORM_POR_DEFECTO}
    escenarios, start, end, errores, avisos = _parsea(request.form)
    resultado = None
    if not errores:
        try:
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                resultados = motor.run(escenarios, start, end)
            avisos = avisos + sorted({str(w.message) for w in capturados})
            resultado = _prepara(resultados)
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append(
                "No se pudieron obtener los datos de mercado. Comprueba los tickers y tu conexión."
            )

    return render_template(
        "simulador.html", form=form, resultado=resultado, errores=errores, avisos=avisos
    )
