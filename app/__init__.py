from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    from app.backtester_web import backtester
    from app.simulator_web import simulator
    from app.views import pages

    app.register_blueprint(pages)
    app.register_blueprint(backtester)
    app.register_blueprint(simulator)
    return app
