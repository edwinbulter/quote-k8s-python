from app.extensions import db
from app.models import User, UserLike, UserProgress, UserRole
from tests.conftest import login, login_as, register


def _login_as_admin(client):
    client.post("/seed-users")
    return login(client, "admin", "Admin123!")


def test_grant_role_idempotent(app, client):
    _login_as_admin(client)
    register(client, username="target", email="target@example.com")

    r1 = client.post("/admin/users/target/roles/ADMIN")
    r2 = client.post("/admin/users/target/roles/ADMIN")
    assert r1.status_code == 200
    assert r2.status_code == 200

    with app.app_context():
        count = UserRole.query.filter_by(username="target", role="ADMIN").count()
        assert count == 1


def test_cannot_revoke_own_admin_role(client):
    _login_as_admin(client)
    response = client.delete("/admin/users/admin/roles/ADMIN")
    assert response.status_code == 200
    assert b"Cannot remove yourself" in response.data or b"error" in response.data.lower()


def test_cannot_delete_own_account(app, client):
    _login_as_admin(client)
    response = client.delete("/admin/users/admin")
    assert response.status_code == 200

    with app.app_context():
        assert db.session.get(User, "admin") is not None


def test_delete_other_user_cascades(app, client, seed_quotes):
    _login_as_admin(client)

    other_client = app.test_client()
    login_as(other_client, username="target2", email="target2@example.com")
    other_client.post("/quote/new")
    other_client.post("/quote/1/like")

    with app.app_context():
        assert db.session.get(User, "target2") is not None

    response = client.delete("/admin/users/target2")
    assert response.status_code == 200

    with app.app_context():
        assert db.session.get(User, "target2") is None
        assert UserLike.query.filter_by(username="target2").count() == 0
        assert db.session.get(UserProgress, "target2") is None
        assert UserRole.query.filter_by(username="target2").count() == 0


def test_non_admin_cannot_access_admin_routes(client):
    login_as(client, username="plain", email="plain@example.com")
    response = client.get("/admin/users/table")
    assert response.status_code == 403
