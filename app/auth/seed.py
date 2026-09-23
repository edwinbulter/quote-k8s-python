from flask import Blueprint, current_app, jsonify
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User, UserRole

seed_bp = Blueprint("seed", __name__)


def _delete_existing_admin() -> None:
    # Cascades likes/progress/roles too (not just roles) so re-seeding
    # doesn't trip the FK constraints those tables hold on users.username.
    from app.auth.routes import _delete_user_data

    _delete_user_data("admin")


@seed_bp.route("/seed-users", methods=["POST"])
def seed_users():
    """Dev-only convenience endpoint that seeds demo accounts.

    Unauthenticated by design (mirrors the reference app) so the kind
    setup script can call it right after rollout. Gated by
    SEED_USERS_ENABLED so it can be disabled outright for any
    production-facing deployment.
    """
    if not current_app.config.get("SEED_USERS_ENABLED"):
        return jsonify({"error": "not found"}), 404

    if db.session.get(User, "admin") is not None:
        _delete_existing_admin()

    admin = User(
        username="admin",
        email="admin@quote-app.local",
        password_hash=generate_password_hash("Admin123!"),
    )
    db.session.add(admin)
    db.session.add(UserRole(username="admin", role="ADMIN", created_by="System"))
    db.session.commit()

    if db.session.get(User, "user-1") is None:
        test_user = User(
            username="user-1",
            email="user-1@outlook.com",
            password_hash=generate_password_hash("Hello-user-1"),
        )
        db.session.add(test_user)
        db.session.add(UserRole(username="user-1", role="USER", created_by="System"))
        db.session.commit()

    return jsonify({"message": "Users seeded successfully"}), 200
