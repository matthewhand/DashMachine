"""Application factory."""
from flask import Flask

from dashmachine.config import Config
from dashmachine.extensions import bcrypt, db, login_manager


def _security_headers(response):
    """Cheap, always-safe response headers."""
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    return response


def create_app(**overrides):
    context_path = overrides.pop("CONTEXT_PATH", Config.CONTEXT_PATH)

    app = Flask(
        __name__,
        static_url_path=f"{context_path}/static" if context_path else "/static",
    )
    app.config.from_object(Config)
    app.config.update(overrides)
    app.config["CONTEXT_PATH"] = context_path

    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "user_system.login"

    app.jinja_env.add_extension("jinja2.ext.loopcontrols")
    app.after_request(_security_headers)

    # Imported here rather than at module scope: the blueprints and models
    # import the extension objects above.
    from dashmachine import sources
    from dashmachine.error_pages.routes import error_pages
    from dashmachine.main.routes import main
    from dashmachine.rest_api.routes import rest_api
    from dashmachine.settings_system.routes import settings_system
    from dashmachine.user_system.routes import user_system

    for blueprint in (main, user_system, error_pages, settings_system, rest_api):
        app.register_blueprint(blueprint, url_prefix=context_path)

    app.context_processor(sources.context_processor)
    return app
