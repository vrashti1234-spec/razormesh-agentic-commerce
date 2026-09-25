from pydantic import BaseModel, Field
from datetime import datetime


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


class PurchaseIntent(BaseModel):
    """
    Exact purchase request that the agent wants to execute.
    This is the structured object that will later be authorized
    by the RAZORMESH Trust Boundary.
    """

    product_id: str
    product_name: str
    merchant: str
    product_url: str

    quantity: int = Field(gt=0)

    amount: float = Field(gt=0)
    currency: str = "INR"

    spending_limit: float = Field(gt=0)

    user_authorized: bool = False

    created_at: datetime
    expires_at: datetime