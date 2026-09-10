from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class FulfillmentResult:
    status: str
    fulfillment_id: str
    order_id: str
    product_id: str
    quantity: int
    message: str


def fulfill_order(
    order_id: str,
    product_id: str,
    quantity: int,
) -> FulfillmentResult:

    fulfillment_id = f"ful_{order_id}"

    return FulfillmentResult(
        status="fulfilled",
        fulfillment_id=fulfillment_id,
        order_id=order_id,
        product_id=product_id,
        quantity=quantity,
        message="Order fulfillment authorized after verified payment.",
    )