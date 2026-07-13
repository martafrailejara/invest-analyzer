from datetime import date

from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    # solo para mensajes flash de sesión; app local sin datos sensibles en sesión
    app.secret_key = "invest-analyzer-local"

    @app.context_processor
    def _globales():
        return {"hoy": date.today().isoformat()}

    from app.anomalies_web import anomalies
    from app.backtester_web import backtester
    from app.dividends_web import dividends
    from app.holdings_web import holdings
    from app.montecarlo_web import montecarlo
    from app.optimizer_web import optimizer
    from app.risk_web import risk
    from app.saved_web import saved
    from app.simulator_web import simulator

    app.register_blueprint(holdings)
    app.register_blueprint(backtester)
    app.register_blueprint(simulator)
    app.register_blueprint(optimizer)
    app.register_blueprint(risk)
    app.register_blueprint(montecarlo)
    app.register_blueprint(dividends)
    app.register_blueprint(anomalies)
    app.register_blueprint(saved)
    return app
