"""Rutas generales: la portada redirige al primer módulo."""

from flask import Blueprint, redirect, url_for

pages = Blueprint("pages", __name__)


@pages.route("/")
def index():
    return redirect(url_for("backtester.page"))
