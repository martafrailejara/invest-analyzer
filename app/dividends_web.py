"""Página de dividendos: lo cobrado por la cartera y la proyección a 12 meses."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, render_template, request

from app.form_utils import eur, pct
from modules import dividends as motor

dividends = Blueprint("dividends", __name__)

RAIZ = Path(__file__).resolve().parents[1]
CSV_REAL = RAIZ / "data" / "transacciones.csv"
CSV_EJEMPLO = RAIZ / "samples" / "transacciones_ejemplo.csv"


def _prepara(res: dict) -> dict:
    anios = sorted(res["por_anio"])
    return {
        "este_anio": eur(res["este_anio"]),
        "este_anio_raw": round(res["este_anio"], 2),
        "cobrado_total": eur(res["cobrado_total"]),
        "proyeccion_total": eur(res["proyeccion_total"]),
        "todo_cero": res["cobrado_total"] == 0 and res["proyeccion_total"] == 0,
        "chart": {
            "labels": [str(a) for a in anios],
            "totales": [round(res["por_anio"][a], 2) for a in anios],
        },
        "posiciones": [
            {
                "ticker": p["ticker"] if not isinstance(p["ticker"], float) else p["symbol"],
                "name": p["name"],
                "shares": f"{p['shares']:.4f}".rstrip("0").rstrip(".").replace(".", ","),
                "cobrado_total": eur(p["cobrado_total"]),
                "dps_12m": eur(p["dps_12m"]),
                "yoc": pct(p["yoc"]) if p["yoc"] else "—",
                "proyeccion": eur(p["proyeccion"]),
            }
            for p in res["posiciones"]
        ],
        "sin_mapear": res["sin_mapear"],
    }


@dividends.route("/dividendos")
def page():
    usar_ejemplo = request.args.get("cartera") == "ejemplo"
    csv = CSV_EJEMPLO if usar_ejemplo else CSV_REAL

    if not csv.exists():
        return render_template("dividendos.html", resultado=None, errores=[], ejemplo=usar_ejemplo,
                               sin_csv=True)

    errores: list[str] = []
    resultado = None
    try:
        resultado = _prepara(motor.run(csv))
    except ValueError as exc:
        errores.append(str(exc))
    except Exception:
        errores.append("No se pudo obtener el histórico de dividendos. Comprueba tu conexión.")

    return render_template("dividendos.html", resultado=resultado, errores=errores,
                           ejemplo=usar_ejemplo, sin_csv=False)
