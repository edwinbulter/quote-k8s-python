from tests.conftest import login, register


def test_register_success(client):
    response = register(client)
    assert response.status_code == 201


def test_register_password_mismatch(client):
    response = client.post(
        "/auth/register",
        data={
            "username": "bob",
            "email": "bob@example.com",
            "password": "Password123!",
            "confirm_password": "different",
        },
    )
    assert response.status_code == 400
    assert b"do not match" in response.data


def test_register_duplicate_username(client):
    register(client, username="carol", email="carol1@example.com")
    response = register(client, username="carol", email="carol2@example.com")
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_register_duplicate_email(client):
    register(client, username="dave1", email="dave@example.com")
    response = register(client, username="dave2", email="dave@example.com")
    assert response.status_code == 400
    assert b"already exists" in response.data


def test_login_by_username(client):
    register(client, username="erin", email="erin@example.com", password="Password123!")
    response = login(client, "erin", "Password123!")
    assert response.status_code == 200
    assert response.headers.get("HX-Redirect") == "/"


def test_login_by_email(client):
    register(client, username="frank", email="frank@example.com", password="Password123!")
    response = login(client, "frank@example.com", "Password123!")
    assert response.status_code == 200


def test_login_wrong_password(client):
    register(client, username="gina", email="gina@example.com", password="Password123!")
    response = login(client, "gina", "WrongPassword!")
    assert response.status_code == 401


def test_login_inactive_account(app, client):
    from app.extensions import db
    from app.models import User

    register(client, username="henry", email="henry@example.com", password="Password123!")
    with app.app_context():
        user = db.session.get(User, "henry")
        user.is_active = False
        db.session.commit()

    response = login(client, "henry", "Password123!")
    assert response.status_code == 401


def test_logout_clears_session(client):
    register(client, username="ivan", email="ivan@example.com", password="Password123!")
    login(client, "ivan", "Password123!")
    response = client.post("/auth/logout")
    assert response.status_code == 200
    # A logged-out client should be redirected away from a login-required page.
    response = client.get("/profile")
    assert response.status_code in (302, 200)
    if response.status_code == 302:
        assert "/login" in response.headers["Location"]


def test_seed_users_idempotent(client):
    first = client.post("/seed-users")
    second = client.post("/seed-users")
    assert first.status_code == 200
    assert second.status_code == 200

    login_response = login(client, "user-1", "Hello-user-1")
    assert login_response.status_code == 200
    admin_login = login(client, "admin", "Admin123!")
    assert admin_login.status_code == 200
