import os

from flask import Flask, g, session
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import StaticPool

from app.config import CONFIG_BY_NAME
from app.extensions import db, migrate


def create_app(config_name: str | None = None) -> Flask:
    app = Flask(__name__)

    config_name = config_name or os.environ.get("FLASK_CONFIG", "dev")
    config_class = CONFIG_BY_NAME[config_name]
    app.config.from_object(config_class)

    if config_name == "prod" and not os.environ.get("SECRET_KEY"):
        raise RuntimeError("SECRET_KEY environment variable is required in production")

    # In-memory SQLite (used by the test suite) needs a StaticPool so every
    # connection shares the same in-memory database instead of each getting
    # its own empty one.
    if app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite://":
        app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
            "connect_args": {"check_same_thread": False},
            "poolclass": StaticPool,
        }

    db.init_app(app)
    migrate.init_app(app, db)

    @event.listens_for(Engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    from app.admin.routes import admin_bp
    from app.auth.routes import auth_bp
    from app.auth.seed import seed_bp
    from app.favourites.routes import favourites_bp
    from app.health.routes import health_bp
    from app.pages.routes import pages_bp
    from app.quotes.routes import quotes_bp
    from app.viewed.routes import viewed_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(seed_bp)
    app.register_blueprint(quotes_bp)
    app.register_blueprint(favourites_bp)
    app.register_blueprint(viewed_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(health_bp)

    @app.before_request
    def load_current_user():
        from app.models import User, UserRole

        g.user = None
        g.roles = set()
        username = session.get("username")
        if not username:
            return
        user = db.session.get(User, username)
        if user is None or not user.is_active:
            session.clear()
            return
        g.user = user
        g.roles = {
            r.role
            for r in db.session.query(UserRole).filter_by(username=username).all()
        }

    @app.context_processor
    def inject_globals():
        return {"current_user": g.get("user"), "current_roles": g.get("roles", set())}

    with app.app_context():
        db.create_all()

    return app
