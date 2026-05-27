"""The app module, containing the app factory function."""

import datetime
import logging
import sys
from collections.abc import Sequence
from random import choice
from typing import Any

import flask.app
from flask import Flask, flash, redirect, send_from_directory, url_for

from registry import batch, commands, donor, public, user
from registry.extensions import (
    bcrypt,
    csrf_protect,
    db,
    login_manager,
    migrate,
)
from registry.utils import capitalize, format_postal_code, template_globals


def create_app(config_object: str = "registry.settings") -> flask.app.Flask:
    """Create application factory, as explained here:
    http://flask.pocoo.org/docs/patterns/appfactories/.

    :param config_object: The configuration object to use.
    """
    app = Flask(__name__.split(".")[0])
    app.config.from_object(config_object)
    app.context_processor(template_globals)
    register_extensions(app)
    register_blueprints(app)
    register_commands(app)
    configure_logger(app)

    @app.route("/favicon.ico")
    def favicon():
        return send_from_directory(app.static_folder or ".", "favicon.ico")

    @app.errorhandler(404)
    def page_not_found(e: Exception):
        flash("404 - Stránka, kterou hledáte, neexistuje.", "danger")
        return redirect(url_for("public.home", status_code=404))

    @app.errorhandler(401)
    def unauthorized(e: Exception):
        flash("401 - Nejste přihlášeni. Pro pokračování se prosím přihlaste.", "danger")
        return redirect(url_for("public.home", status_code=401))

    @app.template_filter("format_time")
    def format_time(date: datetime.datetime, format: str = "%d.%m.%Y %H:%M:%S") -> str:
        return date.strftime(format)

    @app.template_filter("translate")
    def translate(input: str, rodne_cislo: str) -> str:
        word_map: dict[str, str] = {
            "pracovník": "pracovnice",
            "p.": "pí",
            "ocenit jeho hluboce": "ocenit její hluboce",
            "využijete jeho příkladu": "využijete jejího příkladu",
            "Dárce": "Dárkyně",
            "držitelem": "držitelkou",
        }
        if rodne_cislo[2] in ("5", "6", "7", "8"):
            return word_map[input]
        else:
            return input

    app.template_filter("capitalize")(capitalize)

    @app.template_filter("postal_code")
    def postal_code(code: str) -> str:
        return format_postal_code(code)

    @app.template_filter("random_choice")
    def random_choice(iterable: Sequence) -> Any:
        return choice(iterable)  # nosec

    return app


def register_extensions(app: flask.app.Flask) -> None:
    """Register Flask extensions."""
    bcrypt.init_app(app)
    db.init_app(app)
    csrf_protect.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    if app.debug:
        from flask_debugtoolbar import DebugToolbarExtension

        debug_toolbar = DebugToolbarExtension()
        debug_toolbar.init_app(app)
    return None


def register_blueprints(app: flask.app.Flask) -> None:
    """Register Flask blueprints."""
    app.register_blueprint(public.views.blueprint)
    app.register_blueprint(user.views.blueprint)
    app.register_blueprint(donor.views.blueprint)
    app.register_blueprint(batch.views.blueprint)
    return None


def register_commands(app: flask.app.Flask) -> None:
    """Register Click commands."""
    app.cli.add_command(commands.create_user)
    app.cli.add_command(commands.install_test_data)
    app.cli.add_command(commands.refresh_overview)
    app.cli.add_command(commands.import_emails)


def configure_logger(app: flask.app.Flask) -> None:
    """Configure loggers."""
    handler = logging.StreamHandler(sys.stdout)
    if not app.logger.handlers:
        app.logger.addHandler(handler)
