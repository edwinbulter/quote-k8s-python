import pytest

from app import create_app
from app.extensions import db
from app.models import Quote


@pytest.fixture
def app():
    application = create_app("test")
    yield application


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def seed_quotes(app):
    """Insert a small deterministic pool of quotes, bypassing ZenQuotes."""
    with app.app_context():
        for i in range(1, 11):
            db.session.add(
                Quote(quote_text=f"Test quote {i}", author=f"Author {i}", source="Local")
            )
        db.session.commit()
    return app


def register(client, username="alice", email="alice@example.com", password="Password123!"):
    return client.post(
        "/auth/register",
        data={
            "username": username,
            "email": email,
            "password": password,
            "confirm_password": password,
        },
    )


def login(client, username, password):
    return client.post("/auth/login", data={"username": username, "password": password})


def login_as(client, username="alice", password="Password123!", email="alice@example.com"):
    register(client, username=username, email=email, password=password)
    return login(client, username, password)
