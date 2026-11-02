# Orders Service

Small FastAPI + SQLite (SQLAlchemy) orders service. It runs behind the API
gateway, which authenticates users and sends their id in the `X-User-Id` header.

## Run

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.main        # serves on http://127.0.0.1:8001
```

Data is stored in `./orders.db` (override with `DATABASE_URL`). On startup, if
the orders table is empty, it is seeded: orders 1 and 2 belong to user 1,
order 3 to user 2.

## Endpoints

All require `X-User-Id` (positive integer); missing/invalid -> `401`.

| Method | Path | Description |
|---|---|---|
| GET | `/orders` | Current user's orders |
| POST | `/orders` | Create an order for the current user |
| GET | `/orders/{order_id}` | One order with items; `404` if it isn't yours |

```bash
curl -H 'X-User-Id: 1' http://127.0.0.1:8001/orders
curl -H 'X-User-Id: 1' -H 'Content-Type: application/json' \
  -d '{"items":[{"product_name":"Pen","quantity":2,"unit_price_cents":150}]}' \
  http://127.0.0.1:8001/orders
```

Prices are integer cents. The order owner always comes from the header, never
the request body.

## Security note

The service trusts `X-User-Id` unconditionally, so it must only be reachable
through the gateway (hence the loopback bind). Anything that can reach port
8001 directly can impersonate any user; keep it off public interfaces and
make sure the gateway strips client-supplied `X-User-Id` headers.

## Tests

```bash
pytest
```
