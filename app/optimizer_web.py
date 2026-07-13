"""Página del optimizador: frontera eficiente de Markowitz sobre activos elegidos."""

from __future__ import annotations

import warnings
from datetime import date

from flask import Blueprint, render_template, request

from app.form_utils import parsea_fechas, pct
from modules import optimizer as motor

optimizer = Blueprint("optimizer", __name__)

N_TICKERS = 4

FORM_POR_DEFECTO = {
    "ticker_0": "SXR8.DE",
    "ticker_1": "LYXIB.MC",
    "ticker_2": "BTC-EUR",
    "ticker_3": "",
    "start": "2020-01-01",
    "end": date.today().isoformat(),
}


def _parsea(form) -> tuple[list[str], str, str, list[str], list[str]]:
    errores: list[str] = []
    avisos: list[str] = []
    tickers: list[str] = []
    for i in range(N_TICKERS):
        ticker = (form.get(f"ticker_{i}", "") or "").strip().upper()
        if ticker and ticker not in tickers:
            tickers.append(ticker)
    if len(tickers) < 2:
        errores.append("Indica al menos dos activos distintos para optimizar.")
    start = form.get("start", "")
    end = parsea_fechas(start, form.get("end", ""), errores, avisos)
    return tickers, start, end, errores, avisos


def _pesos_texto(weights: dict) -> str:
    partes = [t + " " + f"{p * 100:.1f}".replace(".", ",") + " %" for t, p in
              sorted(weights.items(), key=lambda kv: -kv[1])]
    return " · ".join(partes)


def _prepara(res: dict) -> dict:
    def punto(p):
        return {"x": p["vol"] * 100, "y": p["ret"] * 100, "pesos": _pesos_texto(p["weights"])}

    tickers = [a["ticker"] for a in res["activos"]]
    carteras = [("min_var", "Mínima varianza"), ("max_sharpe", "Máximo Sharpe")]
    tabla = {
        "tickers": tickers,
        "columnas": [
            {
                "nombre": nombre,
                "clave": clave,
                "pesos": [pct(res[clave]["weights"].get(t, 0.0)) for t in tickers],
                "ret": pct(res[clave]["ret"]),
                "vol": pct(res[clave]["vol"]),
            }
            for clave, nombre in carteras
            if res[clave] is not None
        ],
    }
    return {
        "chart": {
            "frontera": [punto(p) for p in res["frontera"]],
            "activos": [
                {"x": a["vol"] * 100, "y": a["ret"] * 100, "ticker": a["ticker"]}
                for a in res["activos"]
            ],
            "min_var": punto(res["min_var"]),
            "max_sharpe": punto(res["max_sharpe"]) if res["max_sharpe"] else None,
        },
        "tabla": tabla,
        "frontera_tabla": [
            {"ret": pct(p["ret"]), "vol": pct(p["vol"]), "pesos": _pesos_texto(p["weights"])}
            for p in res["frontera"]
        ],
        "sesiones": res["sesiones"],
    }


@optimizer.route("/optimizador", methods=["GET", "POST"])
def page():
    if request.method == "GET":
        return render_template("optimizador.html", form=FORM_POR_DEFECTO, resultado=None, errores=[], avisos=[])

    form = {campo: request.form.get(campo, "") for campo in FORM_POR_DEFECTO}
    tickers, start, end, errores, avisos = _parsea(request.form)
    resultado = None
    if not errores:
        try:
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                res = motor.run(tickers, start, end)
            avisos = avisos + sorted({str(w.message) for w in capturados})
            resultado = _prepara(res)
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append(
                "No se pudieron obtener los datos de mercado. Comprueba los tickers y tu conexión."
            )

    return render_template(
        "optimizador.html", form=form, resultado=resultado, errores=errores, avisos=avisos
    )
