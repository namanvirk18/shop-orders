from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from . import models, schemas
from .database import Base, SessionLocal, engine, get_db


def seed(db: Session) -> None:
    """Insert demo data if the orders table is empty."""
    if db.scalar(select(models.Order.id).limit(1)) is not None:
        return
    data = {
        1: (1, [("Mechanical keyboard", 1, 8900), ("USB-C cable", 2, 1200)]),
        2: (1, [("Desk lamp", 1, 3500), ("Notebook", 3, 450)]),
        3: (2, [("Headphones", 1, 12900), ("Phone stand", 1, 1800)]),
    }
    for order_id, (user_id, items) in data.items():
        db.add(
            models.Order(
                id=order_id,
                user_id=user_id,
                items=[
                    models.OrderItem(product_name=n, quantity=q, unit_price_cents=p)
                    for n, q, p in items
                ],
            )
        )
    db.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed(db)
    yield


app = FastAPI(title="Orders Service", lifespan=lifespan)


def current_user_id(x_user_id: Annotated[str | None, Header()] = None) -> int:
    """User id set by the API gateway. Reject missing/malformed values."""
    if x_user_id is None:
        raise HTTPException(401, "Missing X-User-Id header")
    try:
        uid = int(x_user_id)
    except ValueError:
        raise HTTPException(401, "Invalid X-User-Id header") from None
    if uid <= 0:
        raise HTTPException(401, "Invalid X-User-Id header")
    return uid


UserId = Annotated[int, Depends(current_user_id)]
DB = Annotated[Session, Depends(get_db)]


def to_out(order: models.Order) -> schemas.OrderOut:
    return schemas.OrderOut(
        id=order.id,
        user_id=order.user_id,
        created_at=order.created_at,
        total_cents=sum(i.quantity * i.unit_price_cents for i in order.items),
        items=[schemas.ItemOut.model_validate(i) for i in order.items],
    )


@app.get("/orders", response_model=list[schemas.OrderOut])
def list_orders(user_id: UserId, db: DB):
    stmt = (
        select(models.Order)
        .where(models.Order.user_id == user_id)
        .options(selectinload(models.Order.items))
        .order_by(models.Order.id)
    )
    return [to_out(o) for o in db.scalars(stmt)]


@app.post("/orders", response_model=schemas.OrderOut, status_code=201)
def create_order(body: schemas.OrderIn, user_id: UserId, db: DB):
    order = models.Order(
        user_id=user_id,
        items=[models.OrderItem(**i.model_dump()) for i in body.items],
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    return to_out(order)


@app.get("/orders/{order_id}", response_model=schemas.OrderOut)
def get_order(order_id: int, user_id: UserId, db: DB):
    order = db.scalar(
        select(models.Order)
        .where(models.Order.id == order_id, models.Order.user_id == user_id)
        .options(selectinload(models.Order.items))
    )
    if order is None:
        raise HTTPException(404, "Order not found")
    return to_out(order)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8001)
