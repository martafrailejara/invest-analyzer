"""Página del chequeo: recomendaciones estadísticas sobre la cartera real."""

from __future__ import annotations

import warnings
from pathlib import Path

from flask import Blueprint, flash, redirect, render_template, request, url_for

from app.form_utils import eur, pct
from core import config
from modules import checkup as motor
from modules import rebalance

checkup = Blueprint("checkup", __name__)

RAIZ = Path(__file__).resolve().parents[1]
CSV_REAL = RAIZ / "data" / "transacciones.csv"


@checkup.route("/chequeo")
def page():
    if not CSV_REAL.exists():
        return render_template("chequeo.html", resultado=None, errores=[], avisos=[], sin_csv=True)

    objetivos = config.get("objetivos", {})
    errores: list[str] = []
    avisos: list[str] = []
    resultado = None
    try:
        with warnings.catch_warnings(record=True) as capturados:
            warnings.simplefilter("always")
            res = motor.run(CSV_REAL, objetivos=objetivos)
        avisos = sorted({str(w.message) for w in capturados})
        resultado = {
            "hallazgos": res["hallazgos"],
            "correctos": res["correctos"],
            "resumen": {
                "atencion": sum(1 for h in res["hallazgos"] if h["severidad"] == "atencion"),
                "aviso": sum(1 for h in res["hallazgos"] if h["severidad"] == "aviso"),
                "info": sum(1 for h in res["hallazgos"] if h["severidad"] == "info"),
                "ok": len(res["correctos"]),
            },
            "posiciones": [
                {"symbol": p["symbol"], "ticker": p["ticker"], "name": p["name"],
                 "peso_pct": round(p["peso"] * 100, 1),
                 "objetivo_pct": round(objetivos.get(p["symbol"], 0) * 100, 1) if objetivos.get(p["symbol"]) else ""}
                for p in res["posiciones"]
            ],
        }
    except ValueError as exc:
        errores.append(str(exc))
    except Exception:
        errores.append("No se pudieron obtener los datos de mercado. Comprueba tu conexión.")

    plan = None
    aportacion_txt = request.args.get("aportacion", "").strip()
    aportacion_defecto = config.get("meta", {}).get("mensual", 100)
    if resultado and objetivos:
        try:
            aportacion = float(aportacion_txt.replace(",", ".")) if aportacion_txt \
                else float(aportacion_defecto)
            res_plan = rebalance.run(CSV_REAL, objetivos, aportacion)
            plan = {
                "aportacion": f"{aportacion:g}".replace(".", ","),
                "dirigida": [
                    {"ticker": o["ticker"], "importe": eur(o["importe"]),
                     "peso_resultante": pct(o["peso_resultante"])}
                    for o in res_plan["dirigida"]
                ],
                "clasico": [
                    {"ticker": o["ticker"], "accion": o["accion"],
                     "importe": eur(o["importe"]),
                     "unidades": f"{o['unidades']:.4f}".replace(".", ","),
                     "cuota": eur(o["cuota"]) if "cuota" in o else None,
                     "vender": o["accion"] == "vender"}
                    for o in res_plan["clasico"]
                ],
                "cuota_total": eur(res_plan["cuota_total"]),
                "hay_ventas": any(o["accion"] == "vender" for o in res_plan["clasico"]),
            }
        except ValueError as exc:
            errores.append(str(exc))
        except Exception:
            pass  # el chequeo sigue siendo útil aunque el plan falle

    return render_template("chequeo.html", resultado=resultado, errores=errores,
                           avisos=avisos, sin_csv=False, plan=plan,
                           tiene_objetivos=bool(objetivos),
                           aportacion_form=aportacion_txt or f"{aportacion_defecto:g}")


@checkup.route("/chequeo/objetivos", methods=["POST"])
def objetivos():
    nuevos: dict[str, float] = {}
    errores: list[str] = []
    total = 0.0
    for clave, valor in request.form.items():
        if not clave.startswith("obj_") or not valor.strip():
            continue
        symbol = clave[4:]
        try:
            peso = float(valor.replace(",", "."))
        except ValueError:
            errores.append(f"El objetivo de {symbol} no es un número.")
            continue
        if peso < 0:
            errores.append(f"El objetivo de {symbol} no puede ser negativo.")
            continue
        if peso > 0:
            nuevos[symbol] = peso / 100
            total += peso

    if errores:
        for e in errores:
            flash(e)
    elif nuevos and abs(total - 100) > 0.5:
        flash(f"Los pesos objetivo deben sumar 100 (suman {total:g}). No se han guardado.")
    else:
        config.set("objetivos", nuevos)
        flash("Pesos objetivo guardados." if nuevos else "Pesos objetivo borrados.")
    return redirect(url_for("checkup.page"))
