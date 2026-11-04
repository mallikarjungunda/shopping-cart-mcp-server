"""Structured tool results. Kept small so the model sees only what it needs."""
from typing import Literal

from pydantic import BaseModel


class ProductSummary(BaseModel):
    product_id: str
    name: str
    category: str
    price: float
    in_stock: bool


class ProductDetail(ProductSummary):
    manufacturer: str
    description: str
    stock: int


class CartItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: float
    line_total: float


class Cart(BaseModel):
    cart_id: str
    version: int
    currency: str
    items: list[CartItem]
    subtotal: float


class CheckoutResult(BaseModel):
    stage: Literal["preview", "placed"]
    cart_id: str
    cart_version: int
    items: list[CartItem]
    total: float
    currency: str
    order_id: str | None = None
    status: str | None = None
    message: str


class OrderSummary(BaseModel):
    order_id: str
    status: str
    total: float
    created_at: str


class OrderDetail(OrderSummary):
    items: list[CartItem]
    message: str
