"""Página de fiscalidad: plusvalías realizadas y simulador de venta (estimación)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd
from flask import Blueprint, render_template, request

from app.form_utils import eur
from core import market_data, portfolio
from modules import taxes as motor

taxes = Blueprint("taxes", __name__)

RAIZ = Path(__file__).resolve().parents[1]
CSV_REAL = RAIZ / "data" / "transacciones.csv"


def _precio_actual(symbol: str) -> float | None:
    posiciones = portfolio.positions(portfolio.load_transactions(CSV_REAL))
    fila = posiciones[posiciones["symbol"] == symbol]
    if fila.empty or pd.isna(fila.iloc[0]["yf_ticker"]):
        return None
    ticker = fila.iloc[0]["yf_ticker"]
    hoy = pd.Timestamp.today().normalize()
    px = market_data.get_prices([ticker], hoy - pd.Timedelta(days=14), hoy)
    return float(px[ticker].dropna().iloc[-1])


def _prepara_base(res: dict) -> dict:
    return {
        "lotes": [
            {"symbol": l["symbol"], "name": l["name"],
             "fecha": l["fecha"].strftime("%d-%m-%Y"),
             "unidades": f"{l['unidades']:.6f}".rstrip("0").rstrip(".").replace(".", ","),
             "coste_unitario": eur(l["coste_unitario"])}
            for l in res["lotes"]
        ],
        "simbolos": sorted({l["symbol"] for l in res["lotes"]}),
        "realizadas": [
            {"fecha": r["fecha"].strftime("%d-%m-%Y"), "symbol": r["symbol"],
             "unidades": f"{r['unidades']:g}".replace(".", ","),
             "importe": eur(r["importe"]), "coste": eur(r["coste"]),
             "plusvalia": eur(r["plusvalia"]), "negativa": r["plusvalia"] < 0}
            for r in res["realizadas"]
        ],
        "por_anio": [
            {"anio": a, "plusvalia": eur(g), "cuota": eur(res["cuota_por_anio"][a]),
             "negativa": g < 0}
            for a, g in res["por_anio"].items()
        ],
    }


@taxes.route("/fiscalidad", methods=["GET", "POST"])
def page():
    if not CSV_REAL.exists():
        return render_template("fiscalidad.html", resultado=None, venta=None,
                               form={}, errores=[], avisos=[], sin_csv=True)

    errores: list[str] = []
    avisos: list[str] = []
    venta = None
    form = {"symbol": request.form.get("symbol", ""),
            "unidades": request.form.get("unidades", ""),
            "precio": request.form.get("precio", "")}

    try:
        resultado = _prepara_base(motor.run(CSV_REAL))
    except ValueError as exc:
        return render_template("fiscalidad.html", resultado=None, venta=None,
                               form=form, errores=[str(exc)], avisos=[], sin_csv=False)

    if request.method == "POST":
        try:
            unidades = float((form["unidades"] or "0").replace(",", "."))
            precio_txt = (form["precio"] or "").strip()
            with warnings.catch_warnings(record=True) as capturados:
                warnings.simplefilter("always")
                if precio_txt:
                    precio = float(precio_txt.replace(",", "."))
                else:
                    precio = _precio_actual(form["symbol"])
                    if precio is None:
                        raise ValueError(
                            f"No sé el precio actual de {form['symbol']}: indícalo a mano."
                        )
                    form["precio"] = f"{precio:.2f}"
                res_venta = motor.simulate_sale(CSV_REAL, form["symbol"], unidades, precio)
            avisos = sorted({str(w.message) for w in capturados})
            venta = {
                "symbol": res_venta["symbol"],
                "unidades": f"{res_venta['unidades']:g}".replace(".", ","),
                "importe": eur(res_venta["importe"]),
                "coste_fifo": eur(res_venta["coste_fifo"]),
                "plusvalia": eur(res_venta["plusvalia"]),
                "negativa": res_venta["plusvalia"] < 0,
                "cuota": eur(res_venta["cuota"]),
                "neto": eur(res_venta["importe"] - res_venta["cuota"]),
                "lotes": [
                    {"fecha": l["fecha"].strftime("%d-%m-%Y"),
                     "unidades": f"{l['unidades']:g}".replace(".", ","),
                     "coste_unitario": eur(l["coste_unitario"])}
                    for l in res_venta["lotes_consumidos"]
                ],
            }
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            errores.append("No se pudo obtener el precio de mercado. Indícalo a mano.")

    return render_template("fiscalidad.html", resultado=resultado, venta=venta,
                           form=form, errores=errores, avisos=avisos, sin_csv=False)
