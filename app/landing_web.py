"""Landing: la portada que presenta la plataforma y organiza los módulos."""

from __future__ import annotations

from flask import Blueprint, render_template

landing = Blueprint("landing", __name__)

GRUPOS = [
    ("Tu dinero", [
        ("holdings.page", "Mi cartera",
         "Las posiciones reales de tu export de Trade Republic valoradas a mercado: valor, ganancia aislada de las aportaciones, P&L por posición."),
        ("checkup.page", "Chequeo de cartera",
         "Recomendaciones estadísticas sobre tu cartera: desviación de pesos objetivo, concentración, correlaciones, eficiencia y comisiones. No es asesoramiento profesional."),
        ("goals.page", "Metas financieras",
         "\"Quiero X € en el año Y\": progreso real y probabilidad Monte Carlo de llegar, con variantes de aportación."),
        ("dividends.page", "Dividendos",
         "Lo cobrado por año y posición, yield on cost y la proyección simple a 12 meses."),
    ]),
    ("Simular", [
        ("backtester.page", "Backtester",
         "¿Cómo habría rendido una estrategia? DCA, rebalanceo, benchmark y métricas time-weighted. Se puede guardar y revisitar."),
        ("simulator.page", "Simulador qué-pasaría-si",
         "Dos o tres escenarios lado a lado: aportación única frente a DCA, distintos activos o plazos."),
        ("montecarlo.page", "Proyección Monte Carlo",
         "Miles de futuros posibles por bootstrap de los meses reales del histórico: abanico de percentiles a X años."),
    ]),
    ("Optimizar y medir", [
        ("optimizer.page", "Optimizador de cartera",
         "Frontera eficiente de Markowitz: los pesos de menor riesgo histórico para cada retorno, incluida tu volatilidad objetivo."),
        ("risk.page", "Análisis de riesgo",
         "Sharpe, Sortino, VaR/CVaR, beta contra un índice y la matriz de correlación entre activos."),
    ]),
    ("Vigilar", [
        ("anomalies.page", "Detector de anomalías",
         "Días de movimiento inusual por z-score o por Isolation Forest (machine learning), sobre el gráfico del activo."),
    ]),
]


@landing.route("/")
def page():
    return render_template("landing.html", grupos=GRUPOS)
