from datetime import date

from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)

    @app.context_processor
    def _globales():
        return {"hoy": date.today().isoformat()}

    from app.anomalies_web import anomalies
    from app.backtester_web import backtester
    from app.dividends_web import dividends
    from app.holdings_web import holdings
    from app.optimizer_web import optimizer
    from app.simulator_web import simulator

    app.register_blueprint(holdings)
    app.register_blueprint(backtester)
    app.register_blueprint(simulator)
    app.register_blueprint(optimizer)
    app.register_blueprint(dividends)
    app.register_blueprint(anomalies)
    return app
