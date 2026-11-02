from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ItemIn(BaseModel):
    product_name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0, le=10_000)
    unit_price_cents: int = Field(ge=0, le=100_000_000)


class OrderIn(BaseModel):
    items: list[ItemIn] = Field(min_length=1, max_length=100)


class ItemOut(ItemIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    user_id: int
    created_at: datetime
    total_cents: int
    items: list[ItemOut]
