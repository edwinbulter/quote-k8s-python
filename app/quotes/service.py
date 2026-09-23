import logging
import random

from sqlalchemy import func

from app.extensions import db
from app.models import Quote, UserLike, UserProgress
from app.services import zen_quotes

logger = logging.getLogger(__name__)

MIN_POOL_SIZE = 5


def _max_quote_id() -> int:
    return db.session.query(func.max(Quote.quote_id)).scalar() or 0


def _fetch_more_quotes_if_needed() -> int:
    """Pull a batch from ZenQuotes and append any not already present
    (deduped by exact quote text, matching the reference quote-serving
    dedup rule). Never raises - degrades to "added nothing" on failure."""
    fetched = zen_quotes.fetch_many()
    if not fetched:
        logger.info("ZenQuotes returned no quotes; continuing with existing pool")
        return 0

    existing_texts = {q.quote_text for q in Quote.query.all()}
    added = 0
    for item in fetched:
        text = item.get("q")
        author = item.get("a") or "Unknown"
        if not text or text in existing_texts:
            continue
        db.session.add(Quote(quote_text=text, author=author, source="ZenQuotes"))
        existing_texts.add(text)
        added += 1

    if added:
        db.session.commit()
    return added


def get_random_quote(exclude_ids: set[int]) -> Quote | None:
    max_id = _max_quote_id()
    if max_id < MIN_POOL_SIZE or max_id <= len(exclude_ids):
        _fetch_more_quotes_if_needed()
        max_id = _max_quote_id()

    if max_id == 0:
        return None

    max_attempts = min(100, max_id)
    attempted: set[int] = set()
    for _ in range(max_attempts):
        candidate = random.randint(1, max_id)
        if candidate in exclude_ids or candidate in attempted:
            continue
        attempted.add(candidate)
        quote = db.session.get(Quote, candidate)
        if quote is not None:
            return quote

    query = Quote.query
    if exclude_ids:
        query = query.filter(~Quote.quote_id.in_(exclude_ids))
    candidates = query.all()
    if not candidates:
        return None
    return random.choice(candidates)


def _find_next_available_quote(start_id: int, max_id: int) -> Quote | None:
    for quote_id in range(start_id, max_id + 1):
        quote = db.session.get(Quote, quote_id)
        if quote is not None:
            return quote
    return None


def _update_user_progress(username: str, quote_id: int, existing: UserProgress | None) -> None:
    if existing is None:
        db.session.add(UserProgress(username=username, last_quote_id=quote_id))
    else:
        existing.last_quote_id = quote_id
    db.session.commit()


def get_next_quote_for_user(username: str) -> Quote | None:
    progress = db.session.get(UserProgress, username)
    next_id = (progress.last_quote_id + 1) if progress else 1

    max_id = _max_quote_id()
    if next_id > max_id:
        _fetch_more_quotes_if_needed()
        max_id = _max_quote_id()

    quote = db.session.get(Quote, next_id)
    if quote is None:
        quote = _find_next_available_quote(next_id, max_id)
    if quote is None:
        return None

    _update_user_progress(username, quote.quote_id, progress)
    return quote


def get_quote_by_id(quote_id: int) -> Quote | None:
    return db.session.get(Quote, quote_id)


def get_viewed_quotes_for_user(username: str) -> list[Quote]:
    progress = db.session.get(UserProgress, username)
    if progress is None or progress.last_quote_id <= 0:
        return []
    quotes = (
        Quote.query.filter(Quote.quote_id <= progress.last_quote_id)
        .order_by(Quote.quote_id)
        .all()
    )
    return quotes


def get_user_progress(username: str) -> UserProgress | None:
    return db.session.get(UserProgress, username)


def like_quote(username: str, quote_id: int) -> Quote | None:
    quote = db.session.get(Quote, quote_id)
    if quote is None:
        return None

    existing = UserLike.query.filter_by(username=username, quote_id=quote_id).first()
    if existing is not None:
        return quote

    max_order = (
        db.session.query(func.max(UserLike.order)).filter_by(username=username).scalar() or 0
    )
    db.session.add(UserLike(username=username, quote_id=quote_id, order=max_order + 1))
    quote.like_count = (quote.like_count or 0) + 1
    db.session.commit()
    return quote


def unlike_quote(username: str, quote_id: int) -> Quote | None:
    quote = db.session.get(Quote, quote_id)
    if quote is None:
        return None

    existing = UserLike.query.filter_by(username=username, quote_id=quote_id).first()
    if existing is not None:
        db.session.delete(existing)
        quote.like_count = max((quote.like_count or 0) - 1, 0)
        db.session.commit()
    return quote


def get_liked_quotes_for_user(username: str) -> list[Quote]:
    likes = UserLike.query.filter_by(username=username).order_by(UserLike.order).all()
    quotes = []
    for like in likes:
        quote = db.session.get(Quote, like.quote_id)
        if quote is not None:
            quotes.append(quote)
    return quotes


def is_liked(username: str, quote_id: int) -> bool:
    return (
        UserLike.query.filter_by(username=username, quote_id=quote_id).first() is not None
    )


def move_favourite(username: str, quote_id: int, direction: str) -> bool:
    """Swap the order of a liked quote with its immediate neighbor."""
    likes = UserLike.query.filter_by(username=username).order_by(UserLike.order).all()
    index = next((i for i, like in enumerate(likes) if like.quote_id == quote_id), None)
    if index is None:
        return False

    if direction == "up" and index > 0:
        likes[index].order, likes[index - 1].order = likes[index - 1].order, likes[index].order
    elif direction == "down" and index < len(likes) - 1:
        likes[index].order, likes[index + 1].order = likes[index + 1].order, likes[index].order
    else:
        return False

    db.session.commit()
    return True


def delete_all_viewed_and_liked(username: str) -> None:
    UserLike.query.filter_by(username=username).delete()
    progress = db.session.get(UserProgress, username)
    if progress is not None:
        progress.last_quote_id = 0
    else:
        db.session.add(UserProgress(username=username, last_quote_id=0))
    db.session.commit()
