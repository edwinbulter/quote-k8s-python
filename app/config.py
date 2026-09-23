import os
from datetime import timedelta


def _bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.environ.get("DATABASE_PATH", "quotes.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 15}}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool_env("SESSION_COOKIE_SECURE", False)
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)

    SEED_USERS_ENABLED = _bool_env("SEED_USERS_ENABLED", True)

    ZEN_QUOTES_TIMEOUT = float(os.environ.get("ZEN_QUOTES_TIMEOUT", "5"))
    ZEN_QUOTES_RETRIES = int(os.environ.get("ZEN_QUOTES_RETRIES", "2"))


class DevConfig(BaseConfig):
    DEBUG = True


class TestConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SECRET_KEY = "test-secret-key"
    SEED_USERS_ENABLED = True


class ProdConfig(BaseConfig):
    DEBUG = False


CONFIG_BY_NAME = {
    "dev": DevConfig,
    "test": TestConfig,
    "prod": ProdConfig,
}
