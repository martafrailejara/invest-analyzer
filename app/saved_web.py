"""Página de análisis guardados: lista, recarga y borrado."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from core import store

saved = Blueprint("saved", __name__)

# cómo recargar cada tipo de análisis guardado
CARGADORES = {"backtester": "backtester.page"}


@saved.route("/guardados")
def page():
    analisis = store.list_all()
    for a in analisis:
        a["cargar_url"] = (
            url_for(CARGADORES[a["kind"]], cargar=a["id"]) if a["kind"] in CARGADORES else None
        )
    return render_template("guardados.html", analisis=analisis)


@saved.route("/guardados/borrar/<int:analysis_id>", methods=["POST"])
def borrar(analysis_id: int):
    if store.delete(analysis_id):
        flash("Análisis borrado.")
    return redirect(url_for("saved.page"))
