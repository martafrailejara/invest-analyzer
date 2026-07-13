"""Rutas generales: portada y páginas de los módulos aún no implementados."""

from flask import Blueprint, abort, redirect, render_template, url_for

pages = Blueprint("pages", __name__)

MODULOS_PENDIENTES = {
    "dividendos": (
        "Agregador de dividendos",
        "Cruzará el histórico de dividendos con las posiciones reales de la cartera para mostrar lo cobrado y proyectar el año siguiente.",
        "Fase 6",
    ),
    "anomalias": (
        "Detector de anomalías",
        "Marcará movimientos de precio estadísticamente inusuales (z-score y bandas de Bollinger) sobre el gráfico de cada activo.",
        "Fase 7",
    ),
}


@pages.route("/")
def index():
    return redirect(url_for("backtester.page"))


@pages.route("/<nombre>")
def modulo(nombre: str):
    if nombre not in MODULOS_PENDIENTES:
        abort(404)
    titulo, descripcion, fase = MODULOS_PENDIENTES[nombre]
    return render_template("pendiente.html", titulo=titulo, descripcion=descripcion, fase=fase)
