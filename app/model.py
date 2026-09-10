from pydantic import BaseModel


class Product(BaseModel):
    product_id: str
    name: str
    price: float
    currency: str = "INR"


class CartItem(BaseModel):
    product_id: str
    name: str
    quantity: int
    unit_price: float
    line_total: float
    currency: str = "INR"


class Cart(BaseModel):
    items: list[CartItem]
    total: float
    currency: str = "INR"