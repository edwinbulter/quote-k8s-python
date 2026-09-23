from flask import Blueprint, Response, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from app.auth.decorators import login_required
from app.extensions import db
from app.models import User, UserLike, UserProgress, UserRole

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


def _render_form(mode: str, error: str | None = None, values: dict | None = None, status: int = 200):
    html = render_template(
        "partials/auth_form_fragment.html",
        mode=mode,
        error=error,
        values=values or {},
    )
    return Response(html, status=status)


@auth_bp.route("/form", methods=["GET"])
def form():
    mode = request.args.get("mode", "login")
    if mode not in ("login", "register"):
        mode = "login"
    return _render_form(mode)


@auth_bp.route("/register", methods=["POST"])
def register():
    username = (request.form.get("username") or "").strip()
    email = (request.form.get("email") or "").strip()
    password = request.form.get("password") or ""
    confirm_password = request.form.get("confirm_password") or ""
    values = {"username": username, "email": email}

    if not username or not email or not password:
        return _render_form("register", "All fields are required", values, status=400)
    if password != confirm_password:
        return _render_form("register", "Passwords do not match", values, status=400)
    if db.session.get(User, username) is not None:
        return _render_form("register", "Username already exists", values, status=400)
    if User.query.filter_by(email=email).first() is not None:
        return _render_form("register", "Email already exists", values, status=400)

    user = User(username=username, email=email, password_hash=generate_password_hash(password))
    db.session.add(user)
    db.session.add(UserRole(username=username, role="USER", created_by="System"))
    db.session.commit()

    html = render_template(
        "partials/auth_form_fragment.html",
        mode="login",
        error=None,
        values={"username": username},
        notice="Registration successful. Please sign in.",
    )
    return Response(html, status=201)


@auth_bp.route("/login", methods=["POST"])
def login():
    identifier = (request.form.get("username") or "").strip()
    password = request.form.get("password") or ""

    user = None
    if "@" in identifier:
        user = User.query.filter_by(email=identifier).first()
    else:
        user = db.session.get(User, identifier)

    if user is None or not check_password_hash(user.password_hash, password) or not user.is_active:
        return _render_form("login", "Invalid username or password", {"username": identifier}, status=401)

    session.clear()
    session["username"] = user.username
    session.permanent = True
    return Response(status=200, headers={"HX-Redirect": url_for("pages.index")})


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    session.clear()
    return Response(status=200, headers={"HX-Redirect": url_for("pages.index")})


@auth_bp.route("/change-password", methods=["POST"])
@login_required
def change_password():
    from flask import g

    current_password = request.form.get("current_password") or ""
    new_password = request.form.get("new_password") or ""
    confirm_password = request.form.get("confirm_password") or ""

    user = g.user
    error = None
    if not check_password_hash(user.password_hash, current_password):
        error = "Current password is incorrect"
    elif new_password != confirm_password:
        error = "New passwords do not match"
    elif not new_password:
        error = "New password is required"

    if error:
        html = render_template("partials/toast.html", message=error, toast_type="error")
        return Response(html, status=400)

    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    html = render_template("partials/toast.html", message="Password changed successfully", toast_type="success")
    return Response(html, status=200)


@auth_bp.route("/unregister", methods=["POST"])
@login_required
def unregister():
    from flask import g

    password = request.form.get("password") or ""
    user = g.user

    if not check_password_hash(user.password_hash, password):
        html = render_template("partials/toast.html", message="Invalid password", toast_type="error")
        return Response(html, status=401)

    _delete_user_data(user.username)
    session.clear()
    return Response(status=200, headers={"HX-Redirect": url_for("pages.index")})


def _delete_user_data(username: str) -> None:
    UserLike.query.filter_by(username=username).delete()
    UserProgress.query.filter_by(username=username).delete()
    UserRole.query.filter_by(username=username).delete()
    db.session.query(User).filter_by(username=username).delete()
    db.session.commit()
