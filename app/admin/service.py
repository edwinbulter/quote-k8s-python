import math

from sqlalchemy import func

from app.extensions import db
from app.models import Quote, User, UserLike, UserRole
from app.services import zen_quotes

SORTABLE_COLUMNS = {
    "id": Quote.quote_id,
    "quotetext": Quote.quote_text,
    "author": Quote.author,
    "likes": Quote.like_count,
}


def list_users() -> list[dict]:
    users = User.query.order_by(User.username).all()
    result = []
    for user in users:
        roles = sorted(
            r.role for r in UserRole.query.filter_by(username=user.username).all()
        )
        result.append(
            {
                "username": user.username,
                "email": user.email,
                "roles": roles,
                "is_active": user.is_active,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
            }
        )
    return result


def grant_role(username: str, role: str, granted_by: str) -> bool:
    role = role.upper()
    if UserRole.query.filter_by(username=username, role=role).first() is not None:
        return False
    db.session.add(UserRole(username=username, role=role, created_by=granted_by))
    db.session.commit()
    return True


def revoke_role(username: str, role: str) -> bool:
    role = role.upper()
    existing = UserRole.query.filter_by(username=username, role=role).first()
    if existing is None:
        return False
    db.session.delete(existing)
    db.session.commit()
    return True


def get_quotes(
    page: int,
    page_size: int,
    quote_text: str | None,
    author: str | None,
    sort_by: str,
    sort_order: str,
) -> dict:
    query = Quote.query

    if quote_text:
        query = query.filter(Quote.quote_text.ilike(f"%{quote_text}%"))
    if author:
        query = query.filter(Quote.author.ilike(f"%{author}%"))

    sort_by = (sort_by or "id").lower()
    column = SORTABLE_COLUMNS.get(sort_by, Quote.quote_id)

    if sort_by == "likes":
        # Likes only supports descending sort, matching the reference UI.
        query = query.order_by(column.desc())
        sort_order = "desc"
    else:
        sort_order = (sort_order or "asc").lower()
        query = query.order_by(column.desc() if sort_order == "desc" else column.asc())

    total_count = query.count()
    total_pages = max(math.ceil(total_count / page_size), 1) if page_size else 1
    page = max(min(page, total_pages), 1)

    quotes = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "quotes": quotes,
        "total_count": total_count,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }


def fetch_and_add_new_quotes() -> int:
    fetched = zen_quotes.fetch_many()
    if not fetched:
        return 0

    existing = {
        (q.quote_text.lower(), (q.author or "").lower()) for q in Quote.query.all()
    }
    added = 0
    for item in fetched:
        text = item.get("q")
        author = item.get("a") or "Unknown"
        if not text:
            continue
        key = (text.lower(), author.lower())
        if key in existing:
            continue
        db.session.add(Quote(quote_text=text, author=author, source="ZenQuotes"))
        existing.add(key)
        added += 1

    if added:
        db.session.commit()
    return added


def get_total_likes() -> int:
    return db.session.query(func.count(UserLike.id)).scalar() or 0


def get_total_quotes() -> int:
    return db.session.query(func.count(Quote.quote_id)).scalar() or 0
