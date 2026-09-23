from unittest.mock import patch

from app.extensions import db
from app.models import Quote, UserProgress
from tests.conftest import login_as


def test_anon_new_quote_never_repeats_excluded(client, seed_quotes):
    excluded = []
    for _ in range(5):
        response = client.post("/quote/new", data={"excluded_ids": ",".join(excluded)})
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        start = html.index('data-quote-id="') + len('data-quote-id="')
        end = html.index('"', start)
        quote_id = html[start:end]
        assert quote_id not in excluded
        excluded.append(quote_id)


def test_authenticated_new_quote_advances_progress(app, client, seed_quotes):
    login_as(client)

    r1 = client.post("/quote/new")
    assert r1.status_code == 200
    r2 = client.post("/quote/new")
    assert r2.status_code == 200

    with app.app_context():
        progress = db.session.get(UserProgress, "alice")
        assert progress.last_quote_id == 2


def test_authenticated_new_quote_skips_missing_ids(app, client, seed_quotes):
    login_as(client)
    with app.app_context():
        db.session.delete(db.session.get(Quote, 1))
        db.session.commit()

    response = client.post("/quote/new")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'data-quote-id="2"' in html


def test_get_quote_by_id_does_not_advance_progress(app, client, seed_quotes):
    login_as(client)
    client.post("/quote/new")  # advances to 1
    client.post("/quote/new")  # advances to 2

    response = client.get("/quote/1")
    assert response.status_code == 200

    with app.app_context():
        progress = db.session.get(UserProgress, "alice")
        assert progress.last_quote_id == 2


def test_low_pool_triggers_zenquotes_fetch(app, client):
    with patch("app.quotes.service.zen_quotes.fetch_many") as mocked:
        mocked.return_value = [{"q": "Mocked quote", "a": "Mocked Author"}]
        response = client.post("/quote/new")
        assert response.status_code == 200
        mocked.assert_called_once()

    with app.app_context():
        assert Quote.query.count() == 1


def test_like_unlike_idempotent_and_order(app, client, seed_quotes):
    login_as(client)

    r1 = client.post("/quote/1/like")
    r2 = client.post("/quote/1/like")  # no-op
    assert r1.status_code == 200
    assert r2.status_code == 200

    r3 = client.post("/quote/2/like")
    assert r3.status_code == 200

    with app.app_context():
        from app.models import UserLike

        likes = UserLike.query.filter_by(username="alice").order_by(UserLike.order).all()
        assert len(likes) == 2
        assert likes[0].quote_id == 1
        assert likes[0].order == 1
        assert likes[1].quote_id == 2
        assert likes[1].order == 2

    d1 = client.delete("/quote/1/unlike")
    d2 = client.delete("/quote/1/unlike")  # no-op, already unliked
    assert d1.status_code == 200
    assert d2.status_code == 200

    with app.app_context():
        from app.models import UserLike

        remaining = UserLike.query.filter_by(username="alice").all()
        assert len(remaining) == 1
        assert remaining[0].quote_id == 2
