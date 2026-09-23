from app.models import UserLike
from tests.conftest import login_as


def _like_several(client, ids):
    for quote_id in ids:
        client.post(f"/quote/{quote_id}/like")


def test_reorder_swaps_only_neighbors(app, client, seed_quotes):
    login_as(client)
    _like_several(client, [1, 2, 3])

    response = client.put("/favourites/2/reorder", data={"direction": "up"})
    assert response.status_code == 200

    with app.app_context():
        likes = {
            like.quote_id: like.order
            for like in UserLike.query.filter_by(username="alice").all()
        }
        # quote 2 and quote 1 swapped; quote 3 untouched
        assert likes[2] < likes[1]
        assert likes[3] == max(likes.values())


def test_reorder_at_boundary_is_noop(app, client, seed_quotes):
    login_as(client)
    _like_several(client, [1, 2])

    with app.app_context():
        before = {
            like.quote_id: like.order
            for like in UserLike.query.filter_by(username="alice").all()
        }

    response = client.put("/favourites/1/reorder", data={"direction": "up"})
    assert response.status_code == 200

    with app.app_context():
        after = {
            like.quote_id: like.order
            for like in UserLike.query.filter_by(username="alice").all()
        }
    assert before == after


def test_delete_favourite(app, client, seed_quotes):
    login_as(client)
    _like_several(client, [1, 2])

    response = client.delete("/favourites/1")
    assert response.status_code == 200

    with app.app_context():
        remaining = UserLike.query.filter_by(username="alice").all()
        assert len(remaining) == 1
        assert remaining[0].quote_id == 2
