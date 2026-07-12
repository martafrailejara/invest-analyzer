from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    from app.backtester_web import backtester
    from app.views import pages

    app.register_blueprint(pages)
    app.register_blueprint(backtester)
    return app
