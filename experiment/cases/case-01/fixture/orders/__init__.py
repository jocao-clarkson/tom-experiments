from flask import Flask

from .api import bp
from .errors import AppError, error_response


def create_app(repo, payments_client, config=None):
    app = Flask(__name__)
    app.config.update(config or {})
    app.extensions["orders.repo"] = repo
    app.extensions["orders.payments"] = payments_client
    app.register_blueprint(bp)

    @app.errorhandler(AppError)
    def _handle_app_error(err):
        return error_response(err)

    return app
