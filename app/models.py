from datetime import UTC, datetime

from app.extensions import db


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class Quote(db.Model):
    __tablename__ = "quotes"

    quote_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    quote_text = db.Column(db.Text, nullable=False)
    author = db.Column(db.String(255), nullable=False, default="Unknown")
    like_count = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    source = db.Column(db.String(20), nullable=False, default="Local")

    __table_args__ = (
        db.Index("ix_quotes_quote_text", "quote_text"),
        db.Index("ix_quotes_author", "author"),
    )

    def to_dict(self) -> dict:
        return {
            "id": self.quote_id,
            "quoteText": self.quote_text,
            "author": self.author,
            "likeCount": self.like_count,
        }


class User(db.Model):
    __tablename__ = "users"

    username = db.Column(db.String(50), primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    is_active = db.Column(db.Boolean, nullable=False, default=True)


class UserRole(db.Model):
    __tablename__ = "user_roles"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), db.ForeignKey("users.username"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    created_by = db.Column(db.String(50), nullable=True)

    __table_args__ = (db.UniqueConstraint("username", "role", name="uq_user_role"),)


class UserLike(db.Model):
    __tablename__ = "user_likes"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(50), db.ForeignKey("users.username"), nullable=False, index=True)
    quote_id = db.Column(db.Integer, db.ForeignKey("quotes.quote_id"), nullable=False, index=True)
    order = db.Column(db.Integer, nullable=False)
    liked_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    __table_args__ = (db.UniqueConstraint("username", "quote_id", name="uq_user_like"),)


class UserProgress(db.Model):
    __tablename__ = "user_progress"

    username = db.Column(db.String(50), db.ForeignKey("users.username"), primary_key=True)
    last_quote_id = db.Column(db.Integer, nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
