"""Portada del dashboard: la cartera real valorada a precio de mercado."""

from __future__ import annotations

import math
import warnings
from pathlib import Path

from flask import Blueprint, render_template

from app.form_utils import eur, pct
from modules import holdings as motor

holdings = Blueprint("holdings", __name__)

RAIZ = Path(__file__).resolve().parents[1]
CSV_REAL = RAIZ / "data" / "transacciones.csv"


def _prepara(res: dict) -> dict:
    curva = res["curva"]
    meses = sorted(res["flujo_mensual"])
    return {
        "valor_total": eur(res["valor_total"]),
        "valor_total_raw": round(res["valor_total"], 2),
        "aportado": eur(res["aportado_neto"]),
        "pnl": eur(res["pnl_total"]),
        "pnl_negativo": res["pnl_total"] < 0,
        "pnl_pct": pct(res["pnl_pct"]),
        "cagr": "—" if math.isnan(res["cagr"]) else pct(res["cagr"]),
        "drawdown": pct(res["max_drawdown"]),
        "var_dia": eur(res["variacion_dia"]),
        "var_dia_pct": pct(res["variacion_dia_pct"]),
        "var_dia_negativa": res["variacion_dia"] < 0,
        "aportado_30d": eur(res["aportado_30d"]),
        "desde": res["desde"].strftime("%d-%m-%Y"),
        "chart": {
            "labels": [d.strftime("%Y-%m-%d") for d in curva["valor"].index],
            "value": [round(v, 2) for v in curva["valor"].tolist()],
            "invested": [round(v, 2) for v in curva["invertido"].tolist()],
            "gain": [round(v, 2) for v in curva["ganancia"].tolist()],
            "meses": [str(m) for m in meses],
            "flujo_mes": [round(res["flujo_mensual"][m], 2) for m in meses],
        },
        "transacciones": [
            {
                "fecha": t["fecha"].strftime("%d-%m-%Y"),
                "tipo": t["tipo"],
                "name": t["name"],
                "shares": f"{t['shares']:.6f}".rstrip("0").rstrip(".").replace(".", ","),
                "price": eur(t["price"]),
                "caja": eur(t["caja"]),
                "salida": t["caja"] < 0,
            }
            for t in res["transacciones"]
        ],
        "posiciones": [
            {
                "ticker": p["ticker"],
                "name": p["name"],
                "var_dia": pct(p["var_dia"]),
                "var_dia_negativa": p["var_dia"] < 0,
                "shares": f"{p['shares']:.6f}".rstrip("0").rstrip(".").replace(".", ","),
                "avg_cost": eur(p["avg_cost"]),
                "precio": eur(p["precio_actual"]),
                "valor": eur(p["valor"]),
                "pnl": eur(p["pnl"]),
                "pnl_pct": pct(p["pnl_pct"]),
                "pnl_negativo": p["pnl"] < 0,
                "peso": pct(p["peso"]),
            }
            for p in res["posiciones"]
        ],
        "sin_mapear": res["sin_mapear"],
    }


@holdings.route("/")
def page():
    if not CSV_REAL.exists():
        return render_template("cartera.html", resultado=None, errores=[], avisos=[], sin_csv=True)

    errores: list[str] = []
    avisos: list[str] = []
    resultado = None
    try:
        with warnings.catch_warnings(record=True) as capturados:
            warnings.simplefilter("always")
            res = motor.run(CSV_REAL)
        avisos = sorted({str(w.message) for w in capturados})
        resultado = _prepara(res)
        if res["sin_mapear"]:
            avisos.append(
                "ISINs sin mapear a yfinance (no se valoran): " + ", ".join(res["sin_mapear"])
            )
    except ValueError as exc:
        errores.append(str(exc))
    except Exception:
        errores.append("No se pudieron obtener los precios de mercado. Comprueba tu conexión.")

    return render_template("cartera.html", resultado=resultado, errores=errores,
                           avisos=avisos, sin_csv=False)
