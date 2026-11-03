import pytest
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app import main, models
from app.database import Base


def h(uid):
    return {"X-User-Id": str(uid)}


def test_list_only_own_orders(client):
    r = client.get("/orders", headers=h(1))
    assert r.status_code == 200
    assert [o["id"] for o in r.json()] == [1, 2]
    assert all(len(o["items"]) >= 2 for o in r.json())
    assert [o["id"] for o in client.get("/orders", headers=h(2)).json()] == [3]
    assert client.get("/orders", headers=h(99)).json() == []


def test_get_own_order(client):
    r = client.get("/orders/1", headers=h(1))
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == 1
    assert body["total_cents"] == 8900 + 2 * 1200


@pytest.mark.parametrize("user_id, order_id", [(1, 3), (2, 1), (99, 1)])
def test_get_other_users_order_returns_not_found(client, user_id, order_id):
    response = client.get(f"/orders/{order_id}", headers=h(user_id))
    missing = client.get("/orders/999", headers=h(user_id))
    assert response.status_code == missing.status_code == 404
    assert response.json() == missing.json() == {"detail": "Order not found"}


@pytest.mark.parametrize("headers", [{}, {"X-User-Id": "abc"}, {"X-User-Id": "0"}, {"X-User-Id": "-1"}])
def test_auth_header_required(client, headers):
    for method, path in [("get", "/orders"), ("get", "/orders/1")]:
        assert getattr(client, method)(path, headers=headers).status_code == 401
    r = client.post("/orders", json={"items": [{"product_name": "x", "quantity": 1, "unit_price_cents": 1}]}, headers=headers)
    assert r.status_code == 401


def test_create_order_uses_header_user(client):
    payload = {"items": [{"product_name": "Pen", "quantity": 2, "unit_price_cents": 150}]}
    r = client.post("/orders", json=payload, headers=h(2))
    assert r.status_code == 201
    body = r.json()
    assert body["user_id"] == 2 and body["total_cents"] == 300
    assert client.get(f"/orders/{body['id']}", headers=h(2)).status_code == 200


def test_create_ignores_client_supplied_user_id(client):
    payload = {"user_id": 1, "items": [{"product_name": "Pen", "quantity": 1, "unit_price_cents": 1}]}
    r = client.post("/orders", json=payload, headers=h(2))
    assert r.json()["user_id"] == 2


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"product_name": "", "quantity": 1, "unit_price_cents": 1}],
        [{"product_name": "x", "quantity": 0, "unit_price_cents": 1}],
        [{"product_name": "x", "quantity": -1, "unit_price_cents": 1}],
        [{"product_name": "x", "quantity": 1, "unit_price_cents": -5}],
    ],
)
def test_create_validation(client, items):
    assert client.post("/orders", json={"items": items}, headers=h(1)).status_code == 422


def test_seed_is_idempotent():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        main.seed(db)
        main.seed(db)
        assert db.scalar(select(func.count()).select_from(models.Order)) == 3


def test_reorder_copies_items_into_new_order(client):
    original = client.get("/orders/1", headers=h(1)).json()
    r = client.post("/orders/1/reorder", headers=h(1))
    assert r.status_code == 201
    new = r.json()
    assert new["id"] not in (1, 2, 3)
    assert new["user_id"] == 1
    assert new["total_cents"] == original["total_cents"]
    strip = lambda items: [(i["product_name"], i["quantity"], i["unit_price_cents"]) for i in items]
    assert strip(new["items"]) == strip(original["items"])
    assert {i["id"] for i in new["items"]}.isdisjoint({i["id"] for i in original["items"]})
    assert client.get("/orders/1", headers=h(1)).json() == original
    assert [o["id"] for o in client.get("/orders", headers=h(1)).json()] == [1, 2, new["id"]]


@pytest.mark.parametrize("user_id, order_id", [(1, 3), (2, 1), (99, 1), (1, 999)])
def test_reorder_other_or_missing_order_returns_not_found(client, user_id, order_id):
    r = client.post(f"/orders/{order_id}/reorder", headers=h(user_id))
    assert r.status_code == 404
    assert r.json() == {"detail": "Order not found"}
    # no order was created for anyone
    assert [o["id"] for o in client.get("/orders", headers=h(1)).json()] == [1, 2]
    assert [o["id"] for o in client.get("/orders", headers=h(2)).json()] == [3]


@pytest.mark.parametrize("headers", [{}, {"X-User-Id": "abc"}, {"X-User-Id": "0"}])
def test_reorder_requires_auth(client, headers):
    assert client.post("/orders/1/reorder", headers=headers).status_code == 401
