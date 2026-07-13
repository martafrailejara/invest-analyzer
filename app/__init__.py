from datetime import date

from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    # solo para mensajes flash de sesión; app local sin datos sensibles en sesión
    app.secret_key = "invest-analyzer-local"

    from core.tickers import CATALOGO

    @app.context_processor
    def _globales():
        return {"hoy": date.today().isoformat(), "catalogo_tickers": CATALOGO}

    from app.anomalies_web import anomalies
    from app.backtester_web import backtester
    from app.checkup_web import checkup
    from app.dividends_web import dividends
    from app.goals_web import goals
    from app.holdings_web import holdings
    from app.landing_web import landing
    from app.montecarlo_web import montecarlo
    from app.optimizer_web import optimizer
    from app.risk_web import risk
    from app.saved_web import saved
    from app.simulator_web import simulator

    app.register_blueprint(landing)
    app.register_blueprint(holdings)
    app.register_blueprint(checkup)
    app.register_blueprint(goals)
    app.register_blueprint(backtester)
    app.register_blueprint(simulator)
    app.register_blueprint(optimizer)
    app.register_blueprint(risk)
    app.register_blueprint(montecarlo)
    app.register_blueprint(dividends)
    app.register_blueprint(anomalies)
    app.register_blueprint(saved)
    return app
